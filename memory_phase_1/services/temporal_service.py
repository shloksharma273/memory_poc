from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assign_temporal_metadata(memory_type: str, metadata: dict) -> dict:
    """
    Returns valid_from, valid_to, recorded_at for a memory document.
    Episodic memories anchor both ends to the event timestamp when available.
    Semantic/procedural memories are open-ended by default.
    """
    now = _now()

    if memory_type == "episodic":
        event_ts = metadata.get("event_timestamp")
        valid_from = event_ts or now
        valid_to = event_ts or now
    else:
        valid_from = metadata.get("valid_from") or now
        valid_to = metadata.get("valid_to")  # None = still valid

    return {
        "valid_from": valid_from,
        "valid_to": valid_to,
        "recorded_at": now,
    }
