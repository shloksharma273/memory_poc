import re
from datetime import datetime, timezone

from db.arango_client import get_db
from db.queries import COSINE_SEARCH, GRAPH_TRAVERSAL, GET_PROVENANCE
from services.embedding_service import generate_embedding
from services.entity_extractor import extract_entities
from services.ranking_service import rank_memories, MEMORY_TYPE_BOOST
from services.reflection_retriever import search_reflections

_MEMORY_COLLECTIONS = [
    ("episodic_memories", "episodic", "text"),
    ("semantic_memories", "semantic", "fact"),
    ("procedural_memories", "procedural", "procedure"),
]


def _entity_key(tenant_id: str, name: str) -> str:
    raw = f"{tenant_id}_{name}"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", raw).lower()[:64]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _semantic_search(query_embedding: list[float], tenant_id: str, top_k: int) -> list[dict]:
    db = get_db()
    results: list[dict] = []
    per_col_k = max(top_k, 3)

    for col_name, mem_type, text_field in _MEMORY_COLLECTIONS:
        if not db.has_collection(col_name):
            continue
        try:
            cursor = db.aql.execute(
                COSINE_SEARCH,
                bind_vars={
                    "@collection": col_name,
                    "tenant_id": tenant_id,
                    "query_vec": query_embedding,
                    "top_k": per_col_k,
                },
            )
            for doc in cursor:
                text = (
                    doc.get(text_field)
                    or doc.get("text")
                    or doc.get("fact")
                    or doc.get("procedure")
                    or ""
                )
                results.append({
                    "memory_id": doc["_key"],
                    "collection": col_name,
                    "type": mem_type,
                    "text": text,
                    "semantic_score": doc.get("_similarity", 0.0),
                    "graph_score": 0.0,
                    "importance_score": doc.get("importance_score", 0.0),
                    "confidence_score": doc.get("confidence_score", 0.0),
                    "quality_score": doc.get("quality_score", 0.0),
                    "memory_type_boost": MEMORY_TYPE_BOOST.get(mem_type, 0.60),
                    "valid_from": doc.get("valid_from"),
                    "valid_to": doc.get("valid_to"),
                })
        except Exception:
            continue

    return results


def _graph_search(query_text: str, tenant_id: str) -> list[dict]:
    db = get_db()
    entities = extract_entities(query_text)
    if not entities:
        return []

    results: list[dict] = []
    for entity in entities:
        key = _entity_key(tenant_id, entity["name"])
        entity_id = f"entities/{key}"
        try:
            cursor = db.aql.execute(
                GRAPH_TRAVERSAL,
                bind_vars={"entity_id": entity_id, "tenant_id": tenant_id},
            )
            for doc in cursor:
                mem_type = doc.get("type", "episodic")
                results.append({
                    "memory_id": doc["memory_id"],
                    "collection": doc["collection"],
                    "type": mem_type,
                    "text": doc["text"],
                    "semantic_score": 0.0,
                    "graph_score": doc.get("memory_score", 0.5),
                    "importance_score": 0.0,
                    "confidence_score": 0.0,
                    "quality_score": 0.0,
                    "memory_type_boost": MEMORY_TYPE_BOOST.get(mem_type, 0.60),
                    "valid_from": None,
                    "valid_to": None,
                })
        except Exception:
            continue

    return results


def _get_provenance(memory_id: str, collection: str) -> dict:
    db = get_db()
    try:
        cursor = db.aql.execute(
            GET_PROVENANCE,
            bind_vars={"memory_id": f"{collection}/{memory_id}"},
        )
        docs = list(cursor)
        if docs:
            return docs[0]
    except Exception:
        pass
    return {}


def _increment_access(memories: list[dict]) -> None:
    db = get_db()
    now = _now()
    for m in memories:
        # Only track access on base memory collections, not reflections/summaries
        if m["collection"] in ("reflective_memories", "summary_memories"):
            continue
        try:
            db.aql.execute(
                """
                FOR doc IN @@collection
                  FILTER doc._key == @key
                  UPDATE doc WITH {
                    access_count    : (doc.access_count || 0) + 1,
                    last_accessed_at: @now
                  } IN @@collection
                """,
                bind_vars={"@collection": m["collection"], "key": m["memory_id"], "now": now},
            )
        except Exception:
            continue


def retrieve_memories(query: str, tenant_id: str, top_k: int = 5) -> list[dict]:
    query_embedding = generate_embedding(query)

    semantic_results = _semantic_search(query_embedding, tenant_id, top_k)
    graph_results = _graph_search(query, tenant_id)
    reflection_results = search_reflections(query_embedding, tenant_id, top_k)

    # Merge base memories by memory_id
    merged: dict[str, dict] = {r["memory_id"]: r.copy() for r in semantic_results}

    for r in graph_results:
        mid = r["memory_id"]
        if mid in merged:
            merged[mid]["graph_score"] = r["graph_score"]
        else:
            merged[mid] = r.copy()

    # Reflections and summaries are separate — don't merge with base memories
    all_candidates = list(merged.values()) + reflection_results

    # Phase 3 quality-aware ranking
    ranked = rank_memories(all_candidates, top_k=top_k)

    # Attach provenance to base memories
    for r in ranked:
        if r["type"] in ("reflective", "summary"):
            r["source_system"] = ""
            r["source_document_id"] = ""
        else:
            prov = _get_provenance(r["memory_id"], r["collection"])
            r["source_system"] = prov.get("source_system", "")
            r["source_document_id"] = prov.get("source_document_id", "")
        r["prov_confidence"] = r.get("confidence_score", 0.0)

    _increment_access(ranked)

    return ranked
