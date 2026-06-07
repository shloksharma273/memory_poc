"""Intelligence layer routes: reflect, summarize, list."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from db.arango_client import get_db
from services.phase_3_orchestrator import run_reflection_pipeline, run_summarization_pipeline

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class ReflectRequest(BaseModel):
    tenant_id: str = "default"
    time_window_days: int = 30
    min_quality_score: float = 0.60
    similarity_threshold: float = 0.75
    min_cluster_size: int = 3


class SummarizeRequest(BaseModel):
    tenant_id: str = "default"
    summary_level: str = "weekly"
    group_by: str = "time"
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@router.post("/reflect")
def trigger_reflection(req: ReflectRequest):
    return run_reflection_pipeline(
        tenant_id=req.tenant_id,
        time_window_days=req.time_window_days,
        min_quality_score=req.min_quality_score,
        similarity_threshold=req.similarity_threshold,
        min_cluster_size=req.min_cluster_size,
    )


@router.post("/summarize")
def trigger_summarization(req: SummarizeRequest):
    return run_summarization_pipeline(
        tenant_id=req.tenant_id,
        summary_level=req.summary_level,
        group_by=req.group_by,
        start_time=req.start_time,
        end_time=req.end_time,
    )


@router.get("/reflections")
def list_reflections(tenant_id: str = "default"):
    db = get_db()
    if not db.has_collection("reflective_memories"):
        return {"reflections": []}
    cursor = db.aql.execute(
        """
        FOR doc IN reflective_memories
          FILTER doc.tenant_id == @tenant_id
          SORT doc.quality_score DESC
          RETURN {
            reflection_id        : doc._key,
            reflection_text      : doc.reflection_text,
            pattern_type         : doc.pattern_type,
            support_count        : doc.support_count,
            quality_score        : doc.quality_score,
            importance_score     : doc.importance_score,
            confidence_score     : doc.confidence_score,
            supporting_memory_ids: doc.supporting_memory_ids,
            created_at           : doc.created_at
          }
        """,
        bind_vars={"tenant_id": tenant_id},
    )
    return {"reflections": list(cursor)}


@router.get("/summaries")
def list_summaries(tenant_id: str = "default"):
    db = get_db()
    if not db.has_collection("summary_memories"):
        return {"summaries": []}
    cursor = db.aql.execute(
        """
        FOR doc IN summary_memories
          FILTER doc.tenant_id == @tenant_id
          SORT doc.created_at DESC
          RETURN {
            summary_id   : doc._key,
            summary_text : doc.summary_text,
            summary_level: doc.summary_level,
            group_by     : doc.group_by,
            memory_count : doc.memory_count,
            quality_score: doc.quality_score,
            start_time   : doc.start_time,
            end_time     : doc.end_time,
            key_entities : doc.key_entities,
            main_topics  : doc.main_topics
          }
        """,
        bind_vars={"tenant_id": tenant_id},
    )
    return {"summaries": list(cursor)}
