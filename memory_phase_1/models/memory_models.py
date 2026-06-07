from pydantic import BaseModel
from typing import Optional


class CandidateResult(BaseModel):
    embedding: list[float]
    memory_score: float
    novelty: float
    source_weight: float
    should_store: bool


class ClassificationResult(BaseModel):
    type: str  # episodic | semantic | procedural
    reason: str


class Entity(BaseModel):
    name: str
    type: str


class StoredMemory(BaseModel):
    memory_id: str
    collection: str
    memory_type: str
    memory_score: float
    entity_keys: list[str]


class RetrievedMemory(BaseModel):
    memory_id: str
    collection: str
    type: str
    text: str
    semantic_score: float = 0.0
    graph_score: float = 0.0
    final_score: float = 0.0
    source_system: Optional[str] = None
    source_document_id: Optional[str] = None
