"""
Create all required collections on startup.
Idempotent — safe to call multiple times.
"""

from db.arango_client import get_db


def setup_collections():
    """Create document and edge collections if they don't exist."""
    db = get_db()

    # Document collections
    for name in ["memory_events", "entities", "memory_embeddings", "memory_ingestion_log"]:
        if not db.has_collection(name):
            db.create_collection(name)
            print(f"  ✓ Created collection: {name}")
        else:
            print(f"  · Collection exists: {name}")

    # Edge collection
    if not db.has_collection("relations"):
        db.create_collection("relations", edge=True)
        print("  ✓ Created edge collection: relations")
    else:
        print("  · Edge collection exists: relations")

    print("All collections ready.")
