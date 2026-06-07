import re
import uuid
from datetime import datetime, timezone

from db.arango_client import get_db
from services.graph_service import create_memory_entity_edge, create_memory_provenance_edge
from config.settings import settings

_COLLECTION_MAP = {
    "episodic": "episodic_memories",
    "semantic": "semantic_memories",
    "procedural": "procedural_memories",
}

# Each memory type stores its text under a distinct field name per the schema.
_TEXT_FIELD_MAP = {
    "episodic": "text",
    "semantic": "fact",
    "procedural": "procedure",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_key(tenant_id: str, name: str) -> str:
    raw = f"{tenant_id}_{name}"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", raw).lower()[:64]


def _upsert_entity(db, tenant_id: str, entity: dict) -> str:
    key = _entity_key(tenant_id, entity["name"])
    db.collection("entities").insert(
        {
            "_key": key,
            "tenant_id": tenant_id,
            "name": entity["name"],
            "entity_type": entity["type"],
            "created_at": _now(),
        },
        overwrite=True,
    )
    return key


def write_memory(
    tenant_id: str,
    text: str,
    memory_type: str,
    source: str,
    memory_score: float,
    embedding: list[float],
    entities: list[dict],
    metadata: dict,
    importance_score: float = 0.0,
    confidence_score: float = 0.0,
    quality_score: float = 0.0,
    temporal: dict | None = None,
) -> dict:
    db = get_db()
    now = _now()

    if temporal is None:
        temporal = {"valid_from": now, "valid_to": None, "recorded_at": now}

    collection_name = _COLLECTION_MAP.get(memory_type, "semantic_memories")
    text_field = _TEXT_FIELD_MAP.get(memory_type, "text")
    memory_key = uuid.uuid4().hex[:16]

    memory_doc: dict = {
        "_key": memory_key,
        "tenant_id": tenant_id,
        "type": memory_type,
        text_field: text,
        "source": source,
        "memory_score": memory_score,
        "embedding": embedding,
        "created_at": now,
        # Phase 2 quality fields
        "importance_score": importance_score,
        "confidence_score": confidence_score,
        "quality_score": quality_score,
        # Phase 2 consolidation fields
        "consolidated_from": [],
        "duplicate_count": 0,
        # Phase 2 temporal fields
        "valid_from": temporal["valid_from"],
        "valid_to": temporal["valid_to"],
        "recorded_at": temporal["recorded_at"],
        "last_updated_at": now,
        # Phase 2 usage tracking
        "access_count": 0,
        "last_accessed_at": None,
    }

    if memory_type == "episodic":
        memory_doc["timestamp"] = temporal.get("valid_from", now)

    db.collection(collection_name).insert(memory_doc)

    # Provenance record
    prov_key = uuid.uuid4().hex[:16]
    db.collection("provenance_records").insert(
        {
            "_key": prov_key,
            "tenant_id": tenant_id,
            "source_system": source,
            "source_document_id": metadata.get("source_document_id", ""),
            "extraction_model": settings.ollama_chat_model,
            "processing_time": now,
            "raw_event_key": metadata.get("event_key", ""),
        }
    )
    create_memory_provenance_edge(collection_name, memory_key, prov_key, tenant_id)

    # Entities and graph edges
    entity_keys: list[str] = []
    for entity in entities:
        try:
            ek = _upsert_entity(db, tenant_id, entity)
            entity_keys.append(ek)
            create_memory_entity_edge(collection_name, memory_key, ek, tenant_id)
        except Exception:
            continue

    return {
        "memory_id": memory_key,
        "collection": collection_name,
        "memory_type": memory_type,
        "memory_score": memory_score,
        "entity_keys": entity_keys,
    }
