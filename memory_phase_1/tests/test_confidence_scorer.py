from services.confidence_scorer import score_confidence


def test_new_memory_default():
    result = score_confidence(source="ticketing")
    assert 0.0 < result["confidence_score"] <= 1.0
    assert result["confidence_score"] > 0.5


def test_high_reliability_source():
    erp = score_confidence(source="erp")
    chat = score_confidence(source="chat")
    assert erp["confidence_score"] > chat["confidence_score"]


def test_agreement_increases_with_duplicates():
    low = score_confidence(source="ticketing", duplicate_count=0)
    high = score_confidence(source="ticketing", duplicate_count=3)
    assert high["confidence_score"] > low["confidence_score"]


def test_signals_present():
    result = score_confidence(source="crm", duplicate_count=1)
    assert "signals" in result
    for key in ("reliability", "agreement", "recency", "accuracy"):
        assert key in result["signals"]
        assert 0.0 <= result["signals"][key] <= 1.0


def test_score_bounded():
    result = score_confidence(source="erp", duplicate_count=5)
    assert 0.0 <= result["confidence_score"] <= 1.0


def test_unknown_source_gets_low_confidence():
    result = score_confidence(source="unknown")
    erp = score_confidence(source="erp")
    assert result["confidence_score"] < erp["confidence_score"]
