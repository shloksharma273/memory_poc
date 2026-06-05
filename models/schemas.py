from pydantic import BaseModel
from typing import List, Optional


class MemoryAddRequest(BaseModel):
    """Request body for POST /memory/add"""
    user_id: str = "demo_user"
    message: str


class MemorySearchRequest(BaseModel):
    """Request body for POST /memory/search"""
    query: str
    user_id: str = "demo_user"


class Entity(BaseModel):
    """An extracted entity."""
    name: str
    type: str


class Relationship(BaseModel):
    """An extracted relationship between entities."""
    source: str
    relation: str
    target: str


class ExtractionResult(BaseModel):
    """Result of LLM entity/relationship extraction."""
    entities: List[Entity] = []
    relationships: List[Relationship] = []


class MemoryAddResponse(BaseModel):
    """Response for POST /memory/add"""
    status: str
    event_key: str
    entities_created: int
    relationships_created: int


class MemorySearchResponse(BaseModel):
    """Response for POST /memory/search"""
    semantic: List[dict]
    graph: List[dict]
    bm25: List[dict]
    merged: List[dict]


class GraphResponse(BaseModel):
    """Response for GET /graph/{user_id}"""
    user: str
    relationships: List[dict]
