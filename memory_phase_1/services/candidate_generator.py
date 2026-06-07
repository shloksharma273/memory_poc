from db.arango_client import get_db
from services.embedding_service import generate_embedding, cosine_similarity
from config.settings import settings

SOURCE_WEIGHTS: dict[str, float] = {
    "erp": 1.00,
    "crm": 0.90,
    "ticketing": 0.80,
    "docs": 0.70,
    "email": 0.60,
    "slack": 0.40,
    "chat": 0.40,
    "unknown": 0.30,
}

_MEMORY_COLLECTIONS = [
    "episodic_memories",
    "semantic_memories",
    "procedural_memories",
]


def _max_existing_similarity(embedding: list[float], tenant_id: str) -> float:
    db = get_db()
    max_sim = 0.0

    for col_name in _MEMORY_COLLECTIONS:
        if not db.has_collection(col_name):
            continue
        try:
            cursor = db.aql.execute(
                """
                FOR doc IN @@collection
                  FILTER doc.tenant_id == @tenant_id AND doc.embedding != null
                  RETURN doc.embedding
                """,
                bind_vars={"@collection": col_name, "tenant_id": tenant_id},
            )
            for existing in cursor:
                sim = cosine_similarity(embedding, existing)
                if sim > max_sim:
                    max_sim = sim
        except Exception:
            continue

    return max_sim


def score_candidate(text: str, source: str, tenant_id: str) -> dict:
    embedding = generate_embedding(text)

    source_weight = SOURCE_WEIGHTS.get(source.lower(), SOURCE_WEIGHTS["unknown"])

    max_sim = _max_existing_similarity(embedding, tenant_id)
    novelty = 1.0 if max_sim == 0.0 else 1.0 - max_sim

    memory_score = 0.60 * novelty + 0.40 * source_weight
    should_store = memory_score >= settings.memory_threshold

    return {
        "embedding": embedding,
        "memory_score": round(memory_score, 4),
        "novelty": round(novelty, 4),
        "source_weight": source_weight,
        "should_store": should_store,
    }
