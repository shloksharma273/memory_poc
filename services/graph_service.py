"""
Knowledge graph operations — entity upsert, relationship creation, traversal.
"""

import re
from db.arango_client import get_db


def _normalize_key(name: str) -> str:
    """
    Normalize a name into a valid ArangoDB document key.
    Lowercases, replaces non-alphanumeric chars with underscores, collapses runs.
    """
    key = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.lower().strip())
    key = re.sub(r"_+", "_", key)
    return key.strip("_")


def upsert_entity(name: str, entity_type: str) -> str:
    """Insert an entity if it doesn't already exist. Returns the document key."""
    db = get_db()
    key = _normalize_key(name)
    collection = db.collection("entities")

    if collection.has(key):
        return key

    collection.insert(
        {
            "_key": key,
            "name": name,
            "type": entity_type,
        }
    )
    return key


def create_relationship(source: str, target: str, relation: str):
    """
    Create a directed edge from source → target with the given relation label.
    Skips if an identical edge already exists.
    """
    db = get_db()
    source_key = _normalize_key(source)
    target_key = _normalize_key(target)

    # Ensure both endpoints exist
    entities = db.collection("entities")
    if not entities.has(source_key):
        upsert_entity(source, "unknown")
    if not entities.has(target_key):
        upsert_entity(target, "unknown")

    from_id = f"entities/{source_key}"
    to_id = f"entities/{target_key}"

    # Check for duplicate edge
    cursor = db.aql.execute(
        """
        FOR e IN relations
            FILTER e._from == @from_id AND e._to == @to_id AND e.relation == @relation
            LIMIT 1
            RETURN e
        """,
        bind_vars={"from_id": from_id, "to_id": to_id, "relation": relation},
    )

    if not list(cursor):
        db.collection("relations").insert(
            {
                "_from": from_id,
                "_to": to_id,
                "relation": relation,
            }
        )


def get_user_graph(user_id: str = "demo_user") -> dict:
    """
    Return all outbound relationships from a user entity (1–2 hops).
    Uses anonymous graph traversal over the 'relations' edge collection.
    """
    db = get_db()
    user_key = _normalize_key(user_id)

    entities_col = db.collection("entities")
    if not entities_col.has(user_key):
        return {"user": user_id, "relationships": []}

    cursor = db.aql.execute(
        """
        FOR v, e IN 1..2 OUTBOUND @start relations
            RETURN {
                "relation": e.relation,
                "target": v.name,
                "target_type": v.type
            }
        """,
        bind_vars={"start": f"entities/{user_key}"},
    )

    relationships = list(cursor)
    return {"user": user_id, "relationships": relationships}
