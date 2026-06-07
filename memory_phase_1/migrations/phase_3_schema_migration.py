"""
Phase 3 schema migration — creates reflection/summary collections and edge collections.

    python migrations/phase_3_schema_migration.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.arango_client import get_db

DOCUMENT_COLLECTIONS = ["reflective_memories", "summary_memories"]
EDGE_COLLECTIONS = ["reflection_supported_by_memory", "summary_contains_memory"]


def migrate():
    db = get_db()

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

    print("\n[OK] Phase 3 migration complete.")


if __name__ == "__main__":
    migrate()
