"""Generate and store reflective memories from detected patterns."""
import json
import re
import uuid
from datetime import datetime, timezone

import httpx

from config.settings import settings
from db.arango_client import get_db
from db.queries import COSINE_SEARCH
from services.embedding_service import generate_embedding

_REFLECT_PROMPT = """You are a reflective memory generator.

Create a concise reflective memory from the pattern and supporting memories.

The reflection should be:
- factual
- useful for future agents
- grounded in the supporting memories
- not overconfident
- one or two sentences only

Pattern:
{pattern}

Supporting memories:
{memories}

Return ONLY valid JSON, no markdown.

JSON format:
{{"reflection_text": "...", "confidence_reason": "...", "recommended_use": "..."}}"""

DUPLICATE_THRESHOLD = 0.88


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _llm_generate(pattern: dict, memories: list[dict]) -> str:
    memory_lines = "\n".join(f"- {m['text']}" for m in memories)
    prompt = _REFLECT_PROMPT.format(
        pattern=pattern.get("pattern_summary", ""),
        memories=memory_lines,
    )
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=90.0,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"].strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data.get("reflection_text", "")
    except Exception:
        pass
    return pattern.get("pattern_summary", "Recurring pattern detected.")


def _find_duplicate(db, embedding: list[float], tenant_id: str) -> dict | None:
    if not db.has_collection("reflective_memories"):
        return None
    try:
        cursor = db.aql.execute(
            COSINE_SEARCH,
            bind_vars={
                "@collection": "reflective_memories",
                "tenant_id": tenant_id,
                "query_vec": embedding,
                "top_k": 1,
            },
        )
        docs = list(cursor)
        if docs and docs[0].get("_similarity", 0.0) >= DUPLICATE_THRESHOLD:
            return docs[0]
    except Exception:
        pass
    return None


def _score(memories: list[dict], support_count: int) -> tuple[float, float, float]:
    avg_imp = sum(m.get("importance_score", 0.0) for m in memories) / max(len(memories), 1)
    avg_conf = sum(m.get("confidence_score", 0.0) for m in memories) / max(len(memories), 1)
    bonus = min(support_count / 10, 0.20)
    importance = min(avg_imp + bonus, 1.0)
    confidence = avg_conf
    quality = round(0.60 * importance + 0.40 * confidence, 4)
    return round(importance, 4), round(confidence, 4), quality


def _create_support_edges(db, reflection_key: str, memories: list[dict], tenant_id: str) -> None:
    now = _now()
    for m in memories:
        try:
            db.collection("reflection_supported_by_memory").insert({
                "_from": f"reflective_memories/{reflection_key}",
                "_to": m["_id"],
                "tenant_id": tenant_id,
                "relation": "supported_by",
                "created_at": now,
            }, overwrite=True)
        except Exception:
            continue


def generate_reflection(tenant_id: str, cluster: dict, pattern: dict) -> dict:
    db = get_db()
    memories = cluster.get("memories", [])
    support_count = len(memories)
    now = _now()

    reflection_text = _llm_generate(pattern, memories)
    if not reflection_text:
        return {"status": "skipped", "reason": "empty_reflection_text"}

    embedding = generate_embedding(reflection_text)
    importance, confidence, quality = _score(memories, support_count)
    supporting_ids = [m["_id"] for m in memories]

    # Duplicate check
    existing = _find_duplicate(db, embedding, tenant_id)
    if existing:
        key = existing["_key"]
        new_count = (existing.get("support_count") or 0) + support_count
        new_imp, new_conf, new_qual = _score(memories, new_count)
        existing_ids = existing.get("supporting_memory_ids") or []
        merged_ids = list(set(existing_ids) | set(supporting_ids))
        db.aql.execute(
            """
            FOR doc IN reflective_memories
              FILTER doc._key == @key
              UPDATE doc WITH {
                support_count          : @count,
                supporting_memory_ids  : @ids,
                importance_score       : @imp,
                confidence_score       : @conf,
                quality_score          : @qual,
                last_updated_at        : @now
              } IN reflective_memories
            """,
            bind_vars={"key": key, "count": new_count, "ids": merged_ids, "imp": new_imp, "conf": new_conf, "qual": new_qual, "now": now},
        )
        _create_support_edges(db, key, memories, tenant_id)
        return {
            "status": "updated",
            "reflection_id": key,
            "reflection_text": existing.get("reflection_text", reflection_text),
            "support_count": new_count,
            "importance_score": new_imp,
            "confidence_score": new_conf,
            "quality_score": new_qual,
        }

    # New reflection
    key = uuid.uuid4().hex[:16]
    db.collection("reflective_memories").insert({
        "_key": key,
        "tenant_id": tenant_id,
        "type": "reflective",
        "reflection_text": reflection_text,
        "pattern_type": pattern.get("pattern_type", "unknown"),
        "supporting_memory_ids": supporting_ids,
        "support_count": support_count,
        "confidence_score": confidence,
        "importance_score": importance,
        "quality_score": quality,
        "embedding": embedding,
        "created_at": now,
        "last_updated_at": now,
    })
    _create_support_edges(db, key, memories, tenant_id)

    return {
        "status": "stored",
        "reflection_id": key,
        "reflection_text": reflection_text,
        "support_count": support_count,
        "importance_score": importance,
        "confidence_score": confidence,
        "quality_score": quality,
    }
