import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from db.arango_client import get_db
from models.api_models import (
    AddMemoryRequest,
    AddMemoryResponse,
    EntityResponse,
    RetrieveMemoryRequest,
    RetrieveMemoryResponse,
    TemporalInfo,
)
from services.candidate_generator import score_candidate
from services.classifier import classify_memory
from services.consolidation_service import check_consolidation, merge_into_existing
from services.context_builder import build_context
from services.entity_extractor import extract_entities
from services.importance_scorer import score_importance
from services.confidence_scorer import score_confidence
from services.memory_retriever import retrieve_memories
from services.memory_writer import write_memory
from services.temporal_service import assign_temporal_metadata

router = APIRouter(prefix="/memory", tags=["memory"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/add", response_model=AddMemoryResponse)
def add_memory(req: AddMemoryRequest):
    db = get_db()

    # 1. Store raw event
    event_key = uuid.uuid4().hex[:16]
    db.collection("memory_events").insert({
        "_key": event_key,
        "tenant_id": req.tenant_id,
        "raw_text": req.text,
        "source": req.source,
        "created_at": _now(),
        "metadata": req.metadata or {},
    })

    # 2. Candidate scoring (includes embedding generation)
    try:
        candidate = score_candidate(req.text, req.source, req.tenant_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

    if not candidate["should_store"]:
        return AddMemoryResponse(
            status="not_stored",
            reason="memory_score_below_threshold",
            memory_score=candidate["memory_score"],
        )

    # 3. Classify
    classification = classify_memory(req.text)
    memory_type = classification.get("type", "semantic")

    # 4. Extract entities
    entities = extract_entities(req.text)

    # 5. Consolidation check — merge if near-duplicate
    match = check_consolidation(
        embedding=candidate["embedding"],
        entities=entities,
        memory_type=memory_type,
        tenant_id=req.tenant_id,
    )

    metadata = dict(req.metadata or {})
    metadata["event_key"] = event_key

    if match:
        result = merge_into_existing(
            candidate=match,
            new_text=req.text,
            new_source=req.source,
            new_metadata=metadata,
            tenant_id=req.tenant_id,
        )
        return AddMemoryResponse(**result)

    # 6. New memory path: importance + confidence + quality + temporal
    now = _now()

    imp = score_importance(
        source=req.source,
        memory_type=memory_type,
        duplicate_count=0,
        recorded_at=now,
        access_count=0,
    )
    conf = score_confidence(
        source=req.source,
        duplicate_count=0,
        recorded_at=now,
    )
    importance_score = imp["importance_score"]
    confidence_score = conf["confidence_score"]
    quality_score = round(0.60 * importance_score + 0.40 * confidence_score, 4)

    temporal = assign_temporal_metadata(memory_type, metadata)

    # 7. Store memory
    result = write_memory(
        tenant_id=req.tenant_id,
        text=req.text,
        memory_type=memory_type,
        source=req.source,
        memory_score=candidate["memory_score"],
        embedding=candidate["embedding"],
        entities=entities,
        metadata=metadata,
        importance_score=importance_score,
        confidence_score=confidence_score,
        quality_score=quality_score,
        temporal=temporal,
    )

    return AddMemoryResponse(
        status="stored",
        memory_id=result["memory_id"],
        memory_type=memory_type,
        memory_score=candidate["memory_score"],
        importance_score=importance_score,
        confidence_score=confidence_score,
        quality_score=quality_score,
        temporal=TemporalInfo(**temporal),
        entities=[EntityResponse(name=e["name"], type=e["type"]) for e in entities],
    )


@router.post("/retrieve", response_model=RetrieveMemoryResponse)
def retrieve_memory(req: RetrieveMemoryRequest):
    memories = retrieve_memories(req.query, req.tenant_id, req.top_k)
    context = build_context(memories)
    return RetrieveMemoryResponse(query=req.query, context=context)
