"""
Consolidation service: detect and merge near-duplicate memories.

consolidation_score = 0.70 × embedding_similarity
                    + 0.20 × entity_overlap (Jaccard)
                    + 0.10 × type_match
"""
import uuid
from datetime import datetime, timezone

from db.arango_client import get_db
from db.queries import COSINE_SEARCH
from services.embedding_service import cosine_similarity
from services.importance_scorer import score_importance
from services.confidence_scorer import score_confidence
from config.settings import settings

CONSOLIDATION_THRESHOLD = 0.80

_MEMORY_COLLECTIONS = [
    ("episodic_memories", "text"),
    ("semantic_memories", "fact"),
    ("procedural_memories", "procedure"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_names_from_graph(db, collection: str, memory_key: str) -> set[str]:
    try:
        cursor = db.aql.execute(
            """
            FOR v, e IN 1..1 OUTBOUND @memory_id memory_mentions_entity
              RETURN LOWER(v.name)
            """,
            bind_vars={"memory_id": f"{collection}/{memory_key}"},
        )
        return set(cursor)
    except Exception:
        return set()


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _find_top_candidates(embedding: list[float], tenant_id: str, top_k: int = 10) -> list[dict]:
    db = get_db()
    candidates: list[dict] = []

    for col_name, text_field in _MEMORY_COLLECTIONS:
        if not db.has_collection(col_name):
            continue
        try:
            cursor = db.aql.execute(
                COSINE_SEARCH,
                bind_vars={
                    "@collection": col_name,
                    "tenant_id": tenant_id,
                    "query_vec": embedding,
                    "top_k": top_k,
                },
            )
            for doc in cursor:
                candidates.append({
                    "doc": doc,
                    "collection": col_name,
                    "text_field": text_field,
                    "embedding_similarity": doc.get("_similarity", 0.0),
                })
        except Exception:
            continue

    return candidates


def check_consolidation(
    embedding: list[float],
    entities: list[dict],
    memory_type: str,
    tenant_id: str,
) -> dict | None:
    """
    Returns the best candidate dict if consolidation_score >= threshold, else None.
    """
    candidates = _find_top_candidates(embedding, tenant_id)
    if not candidates:
        return None

    db = get_db()
    new_entity_names = {e["name"].lower() for e in entities if "name" in e}

    best_score = 0.0
    best_candidate: dict | None = None

    for c in candidates:
        doc = c["doc"]
        emb_sim = c["embedding_similarity"]
        if emb_sim < 0.70:  # skip obviously non-duplicate candidates
            continue

        existing_entities = _entity_names_from_graph(db, c["collection"], doc["_key"])
        entity_overlap = _jaccard(new_entity_names, existing_entities)

        type_match = 1.0 if doc.get("type") == memory_type else 0.0

        score = 0.70 * emb_sim + 0.20 * entity_overlap + 0.10 * type_match

        if score > best_score:
            best_score = score
            best_candidate = {**c, "consolidation_score": round(score, 4)}

    if best_candidate and best_score >= CONSOLIDATION_THRESHOLD:
        return best_candidate
    return None


def merge_into_existing(
    candidate: dict,
    new_text: str,
    new_source: str,
    new_metadata: dict,
    tenant_id: str,
) -> dict:
    db = get_db()
    now = _now()

    doc = candidate["doc"]
    col_name = candidate["collection"]
    memory_key = doc["_key"]

    new_duplicate_count = (doc.get("duplicate_count") or 0) + 1

    imp = score_importance(
        source=doc.get("source", "unknown"),
        memory_type=doc.get("type", "semantic"),
        duplicate_count=new_duplicate_count,
        recorded_at=doc.get("recorded_at"),
        access_count=doc.get("access_count", 0),
    )
    conf = score_confidence(
        source=doc.get("source", "unknown"),
        duplicate_count=new_duplicate_count,
        recorded_at=doc.get("recorded_at"),
    )
    importance_score = imp["importance_score"]
    confidence_score = conf["confidence_score"]
    quality_score = round(0.60 * importance_score + 0.40 * confidence_score, 4)

    new_source_entry = {"text": new_text, "source": new_source, "created_at": now}

    # Update the existing memory document
    db.aql.execute(
        """
        FOR doc IN @@collection
          FILTER doc._key == @memory_key
          UPDATE doc WITH {
            duplicate_count   : @dup_count,
            consolidated_from : PUSH(doc.consolidated_from != null ? doc.consolidated_from : [], @new_source),
            last_updated_at   : @now,
            importance_score  : @importance,
            confidence_score  : @confidence,
            quality_score     : @quality
          } IN @@collection
        """,
        bind_vars={
            "@collection": col_name,
            "memory_key": memory_key,
            "dup_count": new_duplicate_count,
            "new_source": new_source_entry,
            "now": now,
            "importance": importance_score,
            "confidence": confidence_score,
            "quality": quality_score,
        },
    )

    # New provenance record for the merged source
    prov_key = uuid.uuid4().hex[:16]
    db.collection("provenance_records").insert({
        "_key": prov_key,
        "tenant_id": tenant_id,
        "source_system": new_source,
        "source_document_id": new_metadata.get("source_document_id", ""),
        "extraction_model": settings.ollama_chat_model,
        "processing_time": now,
        "raw_event_key": new_metadata.get("event_key", ""),
    })
    db.collection("memory_has_provenance").insert({
        "_from": f"{col_name}/{memory_key}",
        "_to": f"provenance_records/{prov_key}",
        "tenant_id": tenant_id,
        "relation": "has_provenance",
        "created_at": now,
    }, overwrite=True)

    # Merge audit log
    db.collection("memory_merge_logs").insert({
        "_key": uuid.uuid4().hex[:16],
        "tenant_id": tenant_id,
        "source_memory_text": new_text,
        "target_memory_id": memory_key,
        "target_collection": col_name,
        "similarity_score": candidate["consolidation_score"],
        "merge_reason": "high_embedding_similarity_and_entity_overlap",
        "created_at": now,
    })

    return {
        "status": "merged",
        "target_memory_id": memory_key,
        "target_collection": col_name,
        "consolidation_score": candidate["consolidation_score"],
        "duplicate_count": new_duplicate_count,
        "importance_score": importance_score,
        "confidence_score": confidence_score,
        "quality_score": quality_score,
    }
