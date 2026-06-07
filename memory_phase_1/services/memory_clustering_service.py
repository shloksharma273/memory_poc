"""Cluster related memories for reflection."""
import uuid
from datetime import datetime, timezone
from services.embedding_service import cosine_similarity

def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)

def _time_proximity(ts_a: str, ts_b: str) -> float:
    try:
        def parse(ts):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        diff = abs((parse(ts_a) - parse(ts_b)).days)
        if diff <= 7:
            return 1.0
        elif diff <= 30:
            return 0.5
        return 0.0
    except Exception:
        return 0.0

def _pair_similarity(a: dict, b: dict) -> float:
    emb_sim = cosine_similarity(a["embedding"], b["embedding"])
    entity_overlap = _jaccard(a["entity_names"], b["entity_names"])
    type_match = 1.0 if a["type"] == b["type"] else 0.0
    time_prox = _time_proximity(a.get("created_at", ""), b.get("created_at", ""))
    return 0.60 * emb_sim + 0.25 * entity_overlap + 0.10 * type_match + 0.05 * time_prox

def cluster_memories(
    memories: list[dict],
    similarity_threshold: float = 0.75,
    min_cluster_size: int = 3,
) -> list[dict]:
    assigned = set()
    clusters = []

    for i in range(len(memories)):
        if i in assigned:
            continue
        seed = memories[i]
        group = [seed]
        assigned.add(i)
        for j in range(i + 1, len(memories)):
            if j in assigned:
                continue
            sim = _pair_similarity(seed, memories[j])
            if sim >= similarity_threshold:
                group.append(memories[j])
                assigned.add(j)

        if len(group) < min_cluster_size:
            continue

        avg_quality = sum(m.get("quality_score", 0.0) for m in group) / len(group)
        avg_importance = sum(m.get("importance_score", 0.0) for m in group) / len(group)
        avg_confidence = sum(m.get("confidence_score", 0.0) for m in group) / len(group)

        # Derive cluster theme from most common entity or seed text words
        all_entities: list[str] = []
        for m in group:
            all_entities.extend(m.get("entity_names", set()))
        from collections import Counter
        top_entity = Counter(all_entities).most_common(1)
        theme = top_entity[0][0].replace(" ", "_") if top_entity else f"cluster_{uuid.uuid4().hex[:6]}"

        clusters.append({
            "cluster_id": f"cluster_{uuid.uuid4().hex[:8]}",
            "cluster_theme": theme,
            "memories": group,
            "avg_quality_score": round(avg_quality, 4),
            "avg_importance_score": round(avg_importance, 4),
            "avg_confidence_score": round(avg_confidence, 4),
        })

    return clusters
