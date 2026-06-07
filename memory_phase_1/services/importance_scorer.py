from datetime import datetime, timezone

SOURCE_IMPACT_WEIGHTS: dict[str, float] = {
    "erp": 1.00,
    "crm": 0.90,
    "ticketing": 0.80,
    "docs": 0.70,
    "email": 0.60,
    "slack": 0.40,
    "chat": 0.40,
    "unknown": 0.30,
}

MEMORY_TYPE_WEIGHTS: dict[str, float] = {
    "procedural": 0.90,
    "semantic": 0.80,
    "episodic": 0.70,
}


def _recency(recorded_at: str | None) -> float:
    if recorded_at is None:
        return 1.0
    try:
        recorded = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        days_old = (datetime.now(timezone.utc) - recorded).days
        return max(0.0, 1.0 - days_old / 30)
    except Exception:
        return 1.0


def score_importance(
    source: str,
    memory_type: str,
    duplicate_count: int = 0,
    recorded_at: str | None = None,
    access_count: int = 0,
) -> dict:
    source_weight = SOURCE_IMPACT_WEIGHTS.get(source.lower(), SOURCE_IMPACT_WEIGHTS["unknown"])
    type_weight = MEMORY_TYPE_WEIGHTS.get(memory_type, 0.70)
    impact = (source_weight + type_weight) / 2

    frequency = 0.20 if duplicate_count == 0 else min(duplicate_count / 5, 1.0)
    recency = _recency(recorded_at)
    usage = 0.0 if access_count == 0 else min(access_count / 10, 1.0)

    importance = 0.40 * impact + 0.25 * frequency + 0.20 * recency + 0.15 * usage

    return {
        "importance_score": round(importance, 4),
        "signals": {
            "impact": round(impact, 4),
            "frequency": round(frequency, 4),
            "recency": round(recency, 4),
            "usage": round(usage, 4),
        },
    }
