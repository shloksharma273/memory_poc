"""
Orchestrates the full memory-add pipeline:
  store event → extract entities → build graph → embed → store embedding.
"""

import uuid
from datetime import datetime, timezone

from db.arango_client import get_db
from services.embedding_service import generate_embedding
from services.extraction_service import extract_entities
from services.graph_service import upsert_entity, create_relationship


def add_memory(user_id: str, message: str) -> dict:
    """
    Store memory event and queue the ingestion job.
    """
    db = get_db()

    # ── 1. Store raw memory event (append-only) ──────────────────────
    event_key = f"evt_{uuid.uuid4().hex[:8]}"
    event_doc = {
        "_key": event_key,
        "user_id": user_id,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    db.collection("memory_events").insert(event_doc)
    print(f"  ✓ Stored memory event: {event_key}")

    # ── 2. Create ingestion_log entry ────────────────────────────────
    log_doc = {
        "memory_event_id": event_key,
        "user_id": user_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "retry_count": 0
    }
    db.collection("memory_ingestion_log").insert(log_doc)
    print(f"  ✓ Queued memory event {event_key} for ingestion")

    return {
        "success": True,
        "memory_event_id": event_key,
        "queued": True,
    }


def process_memory_event(event_key: str) -> None:
    """
    Executes LLM entity extraction, graph construction, and embedding generation
    synchronously for a stored event. Used by the background worker.
    """
    db = get_db()

    event_doc = db.collection("memory_events").get(event_key)
    if not event_doc:
        raise ValueError(f"Memory event not found: {event_key}")

    user_id = event_doc["user_id"]
    message = event_doc["message"]

    # ── 1. Extract entities & relationships via LLM ──────────────────
    extraction = extract_entities(message)
    print(
        f"  ✓ Extracted {len(extraction.entities)} entities, "
        f"{len(extraction.relationships)} relationships"
    )

    # ── 2. Build knowledge graph ─────────────────────────────────────
    # Always ensure the user node exists
    upsert_entity(user_id, "user")

    entities_created = 0
    for entity in extraction.entities:
        upsert_entity(entity.name, entity.type)
        entities_created += 1

    relationships_created = 0
    for rel in extraction.relationships:
        source = user_id if rel.source.lower() == "user" else rel.source
        target = user_id if rel.target.lower() == "user" else rel.target
        create_relationship(source, target, rel.relation)
        relationships_created += 1

    print(
        f"  ✓ Graph updated: {entities_created} entities, "
        f"{relationships_created} relationships"
    )

    # ── 3. Generate & store embedding ────────────────────────────────
    embedding = generate_embedding(message)
    emb_doc = {
        "_key": f"emb_{event_key}",
        "memory_id": event_key,
        "text": message,
        "embedding": embedding,
        "user_id": user_id,
    }
    db.collection("memory_embeddings").insert(emb_doc)
    print(f"  ✓ Stored embedding (dim={len(embedding)})")
