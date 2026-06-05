"""
ArangoDB client singleton.
Creates the database if it doesn't exist and returns a cached connection.
"""

from arango import ArangoClient
from config import ARANGO_HOST, ARANGO_DB, ARANGO_USERNAME, ARANGO_PASSWORD

_client: ArangoClient | None = None
_db = None


def get_db():
    """Return a cached ArangoDB database handle, creating the DB if needed."""
    global _client, _db

    if _db is not None:
        return _db

    _client = ArangoClient(hosts=ARANGO_HOST)

    # Connect to _system to ensure our database exists
    sys_db = _client.db(
        "_system",
        username=ARANGO_USERNAME,
        password=ARANGO_PASSWORD,
    )
    if not sys_db.has_database(ARANGO_DB):
        sys_db.create_database(ARANGO_DB)
        print(f"Created database: {ARANGO_DB}")

    _db = _client.db(
        ARANGO_DB,
        username=ARANGO_USERNAME,
        password=ARANGO_PASSWORD,
    )
    return _db
