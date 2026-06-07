from pydantic import BaseModel
from typing import Any, Optional


class AddMemoryRequest(BaseModel):
    tenant_id: str = "default"
    text: str
    source: str = "unknown"
    metadata: Optional[dict[str, Any]] = {}


class EntityResponse(BaseModel):
    name: str
    type: str


class TemporalInfo(BaseModel):
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    recorded_at: Optional[str] = None


class AddMemoryResponse(BaseModel):
    # Common fields
    status: str                          # stored | not_stored | merged

    # stored
    memory_id: Optional[str] = None
    memory_type: Optional[str] = None
    memory_score: Optional[float] = None
    importance_score: Optional[float] = None
    confidence_score: Optional[float] = None
    quality_score: Optional[float] = None
    temporal: Optional[TemporalInfo] = None
    entities: Optional[list[EntityResponse]] = None

    # not_stored
    reason: Optional[str] = None

    # merged
    target_memory_id: Optional[str] = None
    target_collection: Optional[str] = None
    consolidation_score: Optional[float] = None
    duplicate_count: Optional[int] = None


class RetrieveMemoryRequest(BaseModel):
    tenant_id: str
    query: str
    top_k: int = 5


class MemoryItem(BaseModel):
    memory_id: str
    text: str
    score: float
    importance_score: Optional[float] = None
    confidence_score: Optional[float] = None
    quality_score: Optional[float] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None


class Citation(BaseModel):
    memory_id: str
    source_system: Optional[str] = None
    source_document_id: Optional[str] = None
    confidence_score: Optional[float] = None


class ReflectionItem(BaseModel):
    memory_id: str
    text: str
    score: float
    pattern_type: Optional[str] = None
    support_count: Optional[int] = None
    confidence_score: Optional[float] = None
    supporting_memory_ids: list[str] = []


class SummaryItem(BaseModel):
    memory_id: str
    text: str
    score: float
    summary_level: Optional[str] = None
    memory_count: Optional[int] = None
    confidence_score: Optional[float] = None


class MemoryContext(BaseModel):
    facts: list[MemoryItem] = []
    events: list[MemoryItem] = []
    procedures: list[MemoryItem] = []
    reflections: list[ReflectionItem] = []
    summaries: list[SummaryItem] = []
    citations: list[Citation] = []


class RetrieveMemoryResponse(BaseModel):
    query: str
    context: MemoryContext
