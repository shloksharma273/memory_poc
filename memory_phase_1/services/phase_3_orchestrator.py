"""Orchestrate Phase 3 reflection and summarization pipelines."""
from services.reflection_candidate_selector import select_reflection_candidates
from services.memory_clustering_service import cluster_memories
from services.pattern_detector import detect_pattern
from services.reflection_generator import generate_reflection
from services.summarization_service import generate_summary


def run_reflection_pipeline(
    tenant_id: str,
    time_window_days: int = 30,
    min_quality_score: float = 0.60,
    similarity_threshold: float = 0.75,
    min_cluster_size: int = 3,
) -> dict:
    candidates = select_reflection_candidates(tenant_id, time_window_days, min_quality_score)
    if not candidates:
        return {
            "status": "completed",
            "candidate_count": 0,
            "cluster_count": 0,
            "patterns_detected": 0,
            "reflections_created": 0,
            "reflections_updated": 0,
        }

    clusters = cluster_memories(candidates, similarity_threshold, min_cluster_size)

    created = 0
    updated = 0
    patterns_detected = 0

    for cluster in clusters:
        pattern = detect_pattern(cluster)
        if not pattern.get("has_pattern"):
            continue
        patterns_detected += 1
        result = generate_reflection(tenant_id, cluster, pattern)
        if result.get("status") == "stored":
            created += 1
        elif result.get("status") == "updated":
            updated += 1

    return {
        "status": "completed",
        "candidate_count": len(candidates),
        "cluster_count": len(clusters),
        "patterns_detected": patterns_detected,
        "reflections_created": created,
        "reflections_updated": updated,
    }


def run_summarization_pipeline(
    tenant_id: str,
    summary_level: str = "weekly",
    group_by: str = "time",
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    return generate_summary(
        tenant_id=tenant_id,
        summary_level=summary_level,
        group_by=group_by,
        start_time=start_time,
        end_time=end_time,
    )
