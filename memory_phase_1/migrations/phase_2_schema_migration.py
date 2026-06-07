"""
Phase 2 schema migration — adds quality/temporal/consolidation fields to existing memories
and creates the memory_merge_logs collection.

    python migrations/phase_2_schema_migration.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.arango_client import get_db

MEMORY_COLLECTIONS = ["episodic_memories", "semantic_memories", "procedural_memories"]


def migrate():
    db = get_db()

    # New collection for merge audit trail
    if not db.has_collection("memory_merge_logs"):
        db.create_collection("memory_merge_logs")
        print("[+] Created collection: memory_merge_logs")
    else:
        print("[=] Collection exists: memory_merge_logs")

    for col_name in MEMORY_COLLECTIONS:
        if not db.has_collection(col_name):
            print(f"[!] Collection missing, skipping: {col_name}")
            continue

        cursor = db.aql.execute(
            """
            FOR doc IN @@collection
              FILTER doc.importance_score == null
              UPDATE doc WITH {
                importance_score  : 0.0,
                confidence_score  : 0.0,
                quality_score     : 0.0,
                consolidated_from : [],
                duplicate_count   : 0,
                valid_from        : doc.created_at,
                valid_to          : null,
                recorded_at       : doc.created_at,
                last_updated_at   : doc.created_at,
                access_count      : 0,
                last_accessed_at  : null
              } IN @@collection
              RETURN NEW._key
            """,
            bind_vars={"@collection": col_name},
        )
        updated = list(cursor)
        print(f"[+] {col_name}: migrated {len(updated)} documents")

    print("\n[OK] Phase 2 migration complete.")


if __name__ == "__main__":
    migrate()
