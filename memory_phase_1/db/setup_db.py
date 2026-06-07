"""
Run once before starting the server to create all collections.

    python db/setup_db.py
"""
import sys
import os

# Allow running from the project root or from db/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arango import ArangoClient
from config.settings import settings

DOCUMENT_COLLECTIONS = [
    "memory_events",
    "episodic_memories",
    "semantic_memories",
    "procedural_memories",
    "entities",
    "provenance_records",
]

EDGE_COLLECTIONS = [
    "memory_mentions_entity",
    "memory_has_provenance",
    "entity_related_to_entity",
]


def setup():
    client = ArangoClient(hosts=settings.arango_host)

    sys_db = client.db(
        "_system",
        username=settings.arango_username,
        password=settings.arango_password,
    )

    if not sys_db.has_database(settings.arango_db):
        sys_db.create_database(settings.arango_db)
        print(f"[+] Created database: {settings.arango_db}")
    else:
        print(f"[=] Database already exists: {settings.arango_db}")

    db = client.db(
        settings.arango_db,
        username=settings.arango_username,
        password=settings.arango_password,
    )

    for name in DOCUMENT_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name)
            print(f"[+] Created collection: {name}")
        else:
            print(f"[=] Collection exists: {name}")

    for name in EDGE_COLLECTIONS:
        if not db.has_collection(name):
            db.create_collection(name, edge=True)
            print(f"[+] Created edge collection: {name}")
        else:
            print(f"[=] Edge collection exists: {name}")

    # Attempt vector index (ArangoDB 3.12+). Falls back to AQL cosine similarity if unavailable.
    memory_cols = ["episodic_memories", "semantic_memories", "procedural_memories"]
    for col_name in memory_cols:
        col = db.collection(col_name)
        try:
            col.add_index({
                "type": "vector",
                "fields": ["embedding"],
                "params": {"metric": "cosine", "dimension": 768, "nLists": 2},
            })
            print(f"[+] Vector index created on {col_name}")
        except Exception as e:
            print(f"[~] Vector index skipped on {col_name} (using AQL fallback): {type(e).__name__}")

    print("\n[OK] Setup complete.")


if __name__ == "__main__":
    setup()
