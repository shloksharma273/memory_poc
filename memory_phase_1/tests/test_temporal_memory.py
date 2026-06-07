from services.temporal_service import assign_temporal_metadata


def test_episodic_with_event_timestamp():
    result = assign_temporal_metadata(
        memory_type="episodic",
        metadata={"event_timestamp": "2026-06-07T10:00:00Z"},
    )
    assert result["valid_from"] == "2026-06-07T10:00:00Z"
    assert result["valid_to"] == "2026-06-07T10:00:00Z"
    assert result["recorded_at"] is not None


def test_episodic_without_timestamp_uses_now():
    result = assign_temporal_metadata(memory_type="episodic", metadata={})
    assert result["valid_from"] is not None
    assert result["valid_to"] is not None
    assert result["recorded_at"] is not None


def test_semantic_with_valid_from():
    result = assign_temporal_metadata(
        memory_type="semantic",
        metadata={"valid_from": "2026-01-01T00:00:00Z"},
    )
    assert result["valid_from"] == "2026-01-01T00:00:00Z"
    assert result["valid_to"] is None  # open-ended by default


def test_semantic_without_metadata():
    result = assign_temporal_metadata(memory_type="semantic", metadata={})
    assert result["valid_from"] is not None
    assert result["valid_to"] is None


def test_procedural_open_ended():
    result = assign_temporal_metadata(memory_type="procedural", metadata={})
    assert result["valid_from"] is not None
    assert result["valid_to"] is None


def test_recorded_at_always_present():
    for mtype in ("episodic", "semantic", "procedural"):
        result = assign_temporal_metadata(memory_type=mtype, metadata={})
        assert result["recorded_at"] is not None
