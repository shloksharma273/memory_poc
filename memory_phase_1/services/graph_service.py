from datetime import datetime, timezone

from db.arango_client import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_memory_entity_edge(memory_collection: str, memory_key: str, entity_key: str, tenant_id: str) -> None:
    db = get_db()
    db.collection("memory_mentions_entity").insert(
        {
            "_from": f"{memory_collection}/{memory_key}",
            "_to": f"entities/{entity_key}",
            "tenant_id": tenant_id,
            "relation": "mentions",
            "created_at": _now(),
        },
        overwrite=True,
    )


def create_memory_provenance_edge(memory_collection: str, memory_key: str, provenance_key: str, tenant_id: str) -> None:
    db = get_db()
    db.collection("memory_has_provenance").insert(
        {
            "_from": f"{memory_collection}/{memory_key}",
            "_to": f"provenance_records/{provenance_key}",
            "tenant_id": tenant_id,
            "relation": "has_provenance",
            "created_at": _now(),
        },
        overwrite=True,
    )
