"""Retrieve reflective and summary memories for a query."""
from db.arango_client import get_db
from db.queries import COSINE_SEARCH

MEMORY_TYPE_BOOST = {
    "reflective": 1.00,
    "summary": 0.85,
    "procedural": 0.80,
    "semantic": 0.70,
    "episodic": 0.60,
}

_REFLECTION_COLLECTIONS = [
    ("reflective_memories", "reflective", "reflection_text"),
    ("summary_memories", "summary", "summary_text"),
]


def search_reflections(query_embedding: list[float], tenant_id: str, top_k: int = 5) -> list[dict]:
    db = get_db()
    results = []

    for col_name, mem_type, text_field in _REFLECTION_COLLECTIONS:
        if not db.has_collection(col_name):
            continue
        try:
            cursor = db.aql.execute(
                COSINE_SEARCH,
                bind_vars={
                    "@collection": col_name,
                    "tenant_id": tenant_id,
                    "query_vec": query_embedding,
                    "top_k": top_k,
                },
            )
            for doc in cursor:
                text = doc.get(text_field) or ""
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
                    # Extra fields for context builder
                    "pattern_type": doc.get("pattern_type"),
                    "support_count": doc.get("support_count"),
                    "supporting_memory_ids": doc.get("supporting_memory_ids", []),
                    "summary_level": doc.get("summary_level"),
                    "memory_count": doc.get("memory_count"),
                })
        except Exception:
            continue

    return results
