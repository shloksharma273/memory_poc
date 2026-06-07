"""
Phase 2 quality-aware hybrid ranking.

Phase 1 formula : final = 0.70 × semantic + 0.30 × graph
Phase 2 formula : final = 0.50 × semantic + 0.20 × graph + 0.20 × importance + 0.10 × confidence
"""


def rank_memories(memories: list[dict], top_k: int | None = None) -> list[dict]:
    for m in memories:
        m["final_score"] = round(
            0.50 * m.get("semantic_score", 0.0)
            + 0.20 * m.get("graph_score", 0.0)
            + 0.20 * m.get("importance_score", 0.0)
            + 0.10 * m.get("confidence_score", 0.0),
            4,
        )

    ranked = sorted(memories, key=lambda x: x["final_score"], reverse=True)
    return ranked[:top_k] if top_k else ranked
