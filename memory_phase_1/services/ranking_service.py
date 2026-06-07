"""
Quality-aware hybrid ranking.

Phase 1 : final = 0.70 × semantic + 0.30 × graph
Phase 2 : final = 0.50 × semantic + 0.20 × graph + 0.20 × importance + 0.10 × confidence
Phase 3 : final = 0.40 × semantic + 0.20 × graph + 0.20 × importance + 0.10 × confidence + 0.10 × type_boost
"""

MEMORY_TYPE_BOOST: dict[str, float] = {
    "reflective": 1.00,
    "summary": 0.85,
    "procedural": 0.80,
    "semantic": 0.70,
    "episodic": 0.60,
}


def rank_memories(memories: list[dict], top_k: int | None = None) -> list[dict]:
    for m in memories:
        type_boost = m.get("memory_type_boost") or MEMORY_TYPE_BOOST.get(m.get("type", "episodic"), 0.60)
        m["final_score"] = round(
            0.40 * m.get("semantic_score", 0.0)
            + 0.20 * m.get("graph_score", 0.0)
            + 0.20 * m.get("importance_score", 0.0)
            + 0.10 * m.get("confidence_score", 0.0)
            + 0.10 * type_boost,
            4,
        )

    ranked = sorted(memories, key=lambda x: x["final_score"], reverse=True)
    return ranked[:top_k] if top_k else ranked
