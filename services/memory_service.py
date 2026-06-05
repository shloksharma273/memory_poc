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
    Full ingestion pipeline for a single user message.
    Returns a summary dict with status and counts.
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

    # ── 2. Extract entities & relationships via LLM ──────────────────
    extraction = extract_entities(message)
    print(
        f"  ✓ Extracted {len(extraction.entities)} entities, "
        f"{len(extraction.relationships)} relationships"
    )

    # ── 3. Build knowledge graph ─────────────────────────────────────
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

    # ── 4. Generate & store embedding ────────────────────────────────
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

    return {
        "status": "success",
        "event_key": event_key,
        "entities_created": entities_created,
        "relationships_created": relationships_created,
    }
