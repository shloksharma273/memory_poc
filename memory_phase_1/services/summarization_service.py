"""Summarize groups of memories into compact rollups."""
import json
import re
import uuid
from datetime import datetime, timezone, timedelta

import httpx

from config.settings import settings
from db.arango_client import get_db
from services.embedding_service import generate_embedding

_SUMMARY_PROMPT = """You are a memory summarization engine.

Summarize the following memories into a compact memory summary.

Rules:
- Preserve important facts.
- Mention recurring issues.
- Mention key entities.
- Do not invent unsupported information.
- Keep the summary under 120 words.

Memories:
{memories}

Return ONLY valid JSON, no markdown.

JSON format:
{{"summary_text": "...", "key_entities": ["..."], "main_topics": ["..."], "risk_signals": ["..."]}}"""

_MEMORY_COLLECTIONS = [
    ("episodic_memories", "text"),
    ("semantic_memories", "fact"),
    ("procedural_memories", "procedure"),
]

_LEVEL_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_memories_by_time(db, tenant_id: str, start_time: str, end_time: str) -> list[dict]:
    results = []
    for col_name, text_field in _MEMORY_COLLECTIONS:
        if not db.has_collection(col_name):
            continue
        try:
            cursor = db.aql.execute(
                """
                FOR doc IN @@collection
                  FILTER doc.tenant_id == @tenant_id
                  FILTER doc.created_at >= @start_time
                  FILTER doc.created_at <= @end_time
                  RETURN doc
                """,
                bind_vars={"@collection": col_name, "tenant_id": tenant_id, "start_time": start_time, "end_time": end_time},
            )
            for doc in cursor:
                text = doc.get(text_field) or doc.get("text") or doc.get("fact") or doc.get("procedure") or ""
                results.append({
                    "_id": doc["_id"],
                    "text": text,
                    "importance_score": doc.get("importance_score", 0.0),
                    "confidence_score": doc.get("confidence_score", 0.0),
                })
        except Exception:
            continue
    return results


def _fetch_memories_by_entity(db, tenant_id: str, start_time: str, end_time: str) -> list[dict]:
    """Group by most-referenced entity — fetch all, then find common entity."""
    all_mems = _fetch_memories_by_time(db, tenant_id, start_time, end_time)
    if not all_mems:
        return all_mems
    # Find the entity key that appears in the most memories
    try:
        cursor = db.aql.execute(
            """
            LET counts = (
              FOR e IN entities
                FILTER e.tenant_id == @tenant_id
                LET refs = LENGTH(
                  FOR v, edge IN 1..1 INBOUND e._id memory_mentions_entity
                  RETURN 1
                )
                SORT refs DESC
                LIMIT 1
                RETURN e._id
            )
            RETURN counts[0]
            """,
            bind_vars={"tenant_id": tenant_id},
        )
        entity_id = list(cursor)[0]
        if not entity_id:
            return all_mems
        cursor2 = db.aql.execute(
            """
            FOR v, e IN 1..1 INBOUND @entity_id memory_mentions_entity
              FILTER v.tenant_id == @tenant_id
              RETURN {
                _id: v._id,
                text: v.text != null ? v.text : (v.fact != null ? v.fact : (v.procedure != null ? v.procedure : "")),
                importance_score: v.importance_score,
                confidence_score: v.confidence_score
              }
            """,
            bind_vars={"entity_id": entity_id, "tenant_id": tenant_id},
        )
        entity_mems = list(cursor2)
        return entity_mems if entity_mems else all_mems
    except Exception:
        return all_mems


def _llm_summarize(memories: list[dict]) -> dict:
    memory_lines = "\n".join(f"- {m['text']}" for m in memories[:30])  # cap at 30
    prompt = _SUMMARY_PROMPT.format(memories=memory_lines)
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"].strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    texts = " ".join(m["text"][:40] for m in memories[:5])
    return {"summary_text": f"Summary of {len(memories)} memories: {texts[:200]}", "key_entities": [], "main_topics": [], "risk_signals": []}


def _create_summary_edges(db, summary_key: str, memories: list[dict], tenant_id: str) -> None:
    now = _now()
    for m in memories:
        try:
            db.collection("summary_contains_memory").insert({
                "_from": f"summary_memories/{summary_key}",
                "_to": m["_id"],
                "tenant_id": tenant_id,
                "relation": "summarizes",
                "created_at": now,
            }, overwrite=True)
        except Exception:
            continue


def generate_summary(
    tenant_id: str,
    summary_level: str = "weekly",
    group_by: str = "time",
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    db = get_db()
    now = _now()

    days = _LEVEL_DAYS.get(summary_level, 7)
    if not end_time:
        end_time = now
    if not start_time:
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        start_time = (end_dt - timedelta(days=days)).isoformat()

    if group_by == "entity":
        memories = _fetch_memories_by_entity(db, tenant_id, start_time, end_time)
    else:
        memories = _fetch_memories_by_time(db, tenant_id, start_time, end_time)

    if not memories:
        return {"status": "skipped", "reason": "no_memories_in_window", "memory_count": 0}

    llm_result = _llm_summarize(memories)
    summary_text = llm_result.get("summary_text", "")

    avg_imp = sum(m.get("importance_score") or 0.0 for m in memories) / len(memories)
    avg_conf = sum(m.get("confidence_score") or 0.0 for m in memories) / len(memories)
    quality = round(0.60 * avg_imp + 0.40 * avg_conf, 4)

    embedding = generate_embedding(summary_text)
    key = uuid.uuid4().hex[:16]
    source_ids = [m["_id"] for m in memories]

    db.collection("summary_memories").insert({
        "_key": key,
        "tenant_id": tenant_id,
        "type": "summary",
        "summary_text": summary_text,
        "summary_level": summary_level,
        "group_by": group_by,
        "source_memory_ids": source_ids,
        "memory_count": len(memories),
        "start_time": start_time,
        "end_time": end_time,
        "key_entities": llm_result.get("key_entities", []),
        "main_topics": llm_result.get("main_topics", []),
        "risk_signals": llm_result.get("risk_signals", []),
        "embedding": embedding,
        "importance_score": round(avg_imp, 4),
        "confidence_score": round(avg_conf, 4),
        "quality_score": quality,
        "created_at": now,
    })

    _create_summary_edges(db, key, memories, tenant_id)

    return {
        "status": "completed",
        "summary_id": key,
        "summary_level": summary_level,
        "group_by": group_by,
        "memory_count": len(memories),
        "summary_text": summary_text,
        "importance_score": round(avg_imp, 4),
        "confidence_score": round(avg_conf, 4),
        "quality_score": quality,
    }
