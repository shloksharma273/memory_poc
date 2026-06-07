from datetime import datetime, timezone

SOURCE_RELIABILITY: dict[str, float] = {
    "erp": 0.95,
    "crm": 0.90,
    "ticketing": 0.85,
    "docs": 0.80,
    "email": 0.60,
    "slack": 0.45,
    "chat": 0.40,
    "unknown": 0.30,
}

SOURCE_ACCURACY: dict[str, float] = {
    "erp": 0.95,
    "crm": 0.90,
    "ticketing": 0.85,
    "docs": 0.80,
    "email": 0.60,
    "slack": 0.45,
    "chat": 0.40,
    "unknown": 0.30,
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


def score_confidence(
    source: str,
    duplicate_count: int = 0,
    recorded_at: str | None = None,
) -> dict:
    reliability = SOURCE_RELIABILITY.get(source.lower(), SOURCE_RELIABILITY["unknown"])
    accuracy = SOURCE_ACCURACY.get(source.lower(), SOURCE_ACCURACY["unknown"])

    if duplicate_count >= 3:
        agreement = 1.0
    elif duplicate_count == 2:
        agreement = 0.75
    elif duplicate_count == 1:
        agreement = 0.50
    else:
        agreement = 0.20

    recency = _recency(recorded_at)

    confidence = 0.40 * reliability + 0.30 * agreement + 0.20 * recency + 0.10 * accuracy

    return {
        "confidence_score": round(confidence, 4),
        "signals": {
            "reliability": round(reliability, 4),
            "agreement": round(agreement, 4),
            "recency": round(recency, 4),
            "accuracy": round(accuracy, 4),
        },
    }
