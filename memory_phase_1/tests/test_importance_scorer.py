from services.importance_scorer import score_importance


def test_new_memory_default_scores():
    result = score_importance(source="ticketing", memory_type="episodic")
    assert 0.0 < result["importance_score"] <= 1.0
    assert result["importance_score"] > 0.5


def test_high_source_gives_higher_importance():
    erp = score_importance(source="erp", memory_type="procedural")
    chat = score_importance(source="chat", memory_type="episodic")
    assert erp["importance_score"] > chat["importance_score"]


def test_frequency_increases_importance():
    low = score_importance(source="ticketing", memory_type="episodic", duplicate_count=0)
    high = score_importance(source="ticketing", memory_type="episodic", duplicate_count=5)
    assert high["importance_score"] > low["importance_score"]


def test_usage_increases_importance():
    low = score_importance(source="ticketing", memory_type="episodic", access_count=0)
    high = score_importance(source="ticketing", memory_type="episodic", access_count=10)
    assert high["importance_score"] > low["importance_score"]


def test_signals_present():
    result = score_importance(source="crm", memory_type="semantic")
    assert "signals" in result
    for key in ("impact", "frequency", "recency", "usage"):
        assert key in result["signals"]
        assert 0.0 <= result["signals"][key] <= 1.0


def test_score_bounded():
    result = score_importance(
        source="erp",
        memory_type="procedural",
        duplicate_count=10,
        access_count=20,
    )
    assert 0.0 <= result["importance_score"] <= 1.0
