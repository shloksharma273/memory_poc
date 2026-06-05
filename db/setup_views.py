"""
Create the ArangoSearch view for BM25 full-text search.
Idempotent — safe to call multiple times.
"""

from db.arango_client import get_db


def setup_views():
    """Create the memory_view ArangoSearch view if it doesn't exist."""
    db = get_db()
    view_name = "memory_view"

    existing_views = {v["name"] for v in db.views()}

    if view_name not in existing_views:
        db.create_arangosearch_view(
            name=view_name,
            properties={
                "links": {
                    "memory_events": {
                        "analyzers": ["text_en"],
                        "fields": {
                            "message": {
                                "analyzers": ["text_en"],
                            }
                        },
                        "includeAllFields": False,
                        "storeValues": "none",
                        "trackListPositions": False,
                    }
                }
            },
        )
        print(f"  ✓ Created ArangoSearch view: {view_name}")
    else:
        print(f"  · ArangoSearch view exists: {view_name}")
