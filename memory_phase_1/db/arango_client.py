from arango import ArangoClient
from config.settings import settings

_db = None


def get_db():
    global _db
    if _db is None:
        client = ArangoClient(hosts=settings.arango_host)
        _db = client.db(
            settings.arango_db,
            username=settings.arango_username,
            password=settings.arango_password,
        )
    return _db
