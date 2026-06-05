"""
Hybrid retrieval service — semantic (vector), graph (AQL traversal), and BM25.
"""

import numpy as np

from db.arango_client import get_db
from services.embedding_service import generate_embedding
from services.graph_service import _normalize_key
from config import TOP_K_VECTOR, TOP_K_BM25, TOP_K_GRAPH


# ── Helpers ──────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_np = np.array(a)
    b_np = np.array(b)
    denom = np.linalg.norm(a_np) * np.linalg.norm(b_np)
    if denom < 1e-10:
        return 0.0
    return float(np.dot(a_np, b_np) / denom)


# ── Semantic (Vector) Search ─────────────────────────────────────────


def semantic_search(query: str, top_k: int | None = None) -> list[dict]:
    """
    Brute-force cosine similarity over all stored embeddings.
    Fine for POC-scale data; swap for ANN index in production.
    """
    if top_k is None:
        top_k = TOP_K_VECTOR

    db = get_db()
    query_embedding = generate_embedding(query)

    cursor = db.aql.execute("FOR doc IN memory_embeddings RETURN doc")

    results = []
    for doc in cursor:
        score = _cosine_similarity(query_embedding, doc["embedding"])
        results.append(
            {
                "text": doc["text"],
                "memory_id": doc["memory_id"],
                "score": round(score, 4),
                "source": "semantic",
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ── Graph Search ─────────────────────────────────────────────────────


def graph_search(
    query: str, user_id: str = "demo_user", top_k: int | None = None
) -> list[dict]:
    """
    Traverse outbound edges from the user node and return connected entities.
    The query string is currently unused — all user relationships are returned.
    """
    if top_k is None:
        top_k = TOP_K_GRAPH

    db = get_db()
    user_key = _normalize_key(user_id)

    entities_col = db.collection("entities")
    if not entities_col.has(user_key):
        return []

    cursor = db.aql.execute(
        """
        FOR v, e IN 1..2 OUTBOUND @start relations
            RETURN {
                "entity": v.name,
                "entity_type": v.type,
                "relation": e.relation,
                "source": "graph"
            }
        """,
        bind_vars={"start": f"entities/{user_key}"},
    )

    return list(cursor)[:top_k]


# ── BM25 Search ──────────────────────────────────────────────────────


def bm25_search(query: str, top_k: int | None = None) -> list[dict]:
    """
    Full-text BM25 search over the memory_view ArangoSearch view.
    """
    if top_k is None:
        top_k = TOP_K_BM25

    db = get_db()

    cursor = db.aql.execute(
        """
        FOR doc IN memory_view
            SEARCH ANALYZER(doc.message IN TOKENS(@query, 'text_en'), 'text_en')
            SORT BM25(doc) DESC
            LIMIT @top_k
            RETURN {
                "text": doc.message,
                "memory_id": doc._key,
                "score": BM25(doc),
                "source": "bm25",
                "user_id": doc.user_id,
                "timestamp": doc.timestamp
            }
        """,
        bind_vars={"query": query, "top_k": top_k},
    )

    return list(cursor)


# ── Hybrid (Merged) Search ───────────────────────────────────────────


def hybrid_search(query: str, user_id: str = "demo_user") -> dict:
    """
    Execute all three retrieval paths and merge results, deduplicating by text.
    """
    semantic_results = semantic_search(query)
    graph_results = graph_search(query, user_id)
    bm25_results = bm25_search(query)

    # Merge & deduplicate
    merged: list[dict] = []
    seen: set[str] = set()

    for result in semantic_results + bm25_results:
        text = result.get("text", "")
        if text and text not in seen:
            seen.add(text)
            merged.append(result)

    # Graph results have a different shape — deduplicate by entity name
    for result in graph_results:
        entity = result.get("entity", "")
        if entity and entity not in seen:
            seen.add(entity)
            merged.append(result)

    return {
        "semantic": semantic_results,
        "graph": graph_results,
        "bm25": bm25_results,
        "merged": merged,
    }
