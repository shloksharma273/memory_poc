"""Select memories suitable for reflection."""
from datetime import datetime, timezone, timedelta
from db.arango_client import get_db

_MEMORY_COLLECTIONS = [
    ("episodic_memories", "text"),
    ("semantic_memories", "fact"),
    ("procedural_memories", "procedure"),
]

def select_reflection_candidates(
    tenant_id: str,
    time_window_days: int = 30,
    min_quality_score: float = 0.60,
) -> list[dict]:
    db = get_db()
    start_time = (datetime.now(timezone.utc) - timedelta(days=time_window_days)).isoformat()
    results = []

    for col_name, text_field in _MEMORY_COLLECTIONS:
        if not db.has_collection(col_name):
            continue
        # AQL with inline entity subquery:
        # FOR doc IN @@collection
        #   FILTER doc.tenant_id == @tenant_id
        #   FILTER doc.quality_score >= @min_quality
        #   FILTER doc.created_at >= @start_time
        #   FILTER doc.embedding != null
        #   LET entity_names = (
        #     FOR v IN 1..1 OUTBOUND doc._id memory_mentions_entity
        #     RETURN LOWER(v.name)
        #   )
        #   RETURN MERGE(doc, {entity_names: entity_names, _col: @col_name})
        try:
            cursor = db.aql.execute(
                """
                FOR doc IN @@collection
                  FILTER doc.tenant_id == @tenant_id
                  FILTER (doc.quality_score != null ? doc.quality_score : 0) >= @min_quality
                  FILTER doc.created_at >= @start_time
                  FILTER doc.embedding != null
                  LET entity_names = (
                    FOR v IN 1..1 OUTBOUND doc._id memory_mentions_entity
                    RETURN LOWER(v.name)
                  )
                  RETURN MERGE(doc, {entity_names: entity_names})
                """,
                bind_vars={
                    "@collection": col_name,
                    "tenant_id": tenant_id,
                    "min_quality": min_quality_score,
                    "start_time": start_time,
                },
            )
            for doc in cursor:
                text = doc.get(text_field) or doc.get("text") or doc.get("fact") or doc.get("procedure") or ""
                results.append({
                    "_id": doc["_id"],
                    "_key": doc["_key"],
                    "collection": col_name,
                    "type": doc.get("type", "episodic"),
                    "text": text,
                    "entity_names": set(doc.get("entity_names") or []),
                    "embedding": doc["embedding"],
                    "quality_score": doc.get("quality_score", 0.0),
                    "importance_score": doc.get("importance_score", 0.0),
                    "confidence_score": doc.get("confidence_score", 0.0),
                    "created_at": doc.get("created_at", ""),
                })
        except Exception:
            continue

    return results
