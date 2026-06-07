"""Unit tests for pattern detector — tests fallback without LLM."""
from services.pattern_detector import detect_pattern, _fallback


def _make_cluster(size, avg_quality):
    return {
        "cluster_id": "test_cluster",
        "memories": [{"text": f"memory {i}", "_id": f"e/m{i}"} for i in range(size)],
        "avg_quality_score": avg_quality,
        "avg_importance_score": 0.6,
        "avg_confidence_score": 0.7,
    }


def test_fallback_high_quality_cluster():
    cluster = _make_cluster(3, 0.75)
    result = _fallback(cluster)
    assert result["has_pattern"] is True
    assert result["pattern_type"] == "recurring_issue"
    assert result["evidence_count"] == 3


def test_fallback_low_quality_cluster():
    cluster = _make_cluster(3, 0.50)
    result = _fallback(cluster)
    assert result["has_pattern"] is False


def test_fallback_small_cluster():
    cluster = _make_cluster(2, 0.80)
    result = _fallback(cluster)
    assert result["has_pattern"] is False


def test_detect_pattern_too_small():
    cluster = _make_cluster(2, 0.80)
    result = detect_pattern(cluster)
    assert result["has_pattern"] is False


def test_detect_pattern_returns_dict():
    cluster = _make_cluster(3, 0.75)
    result = detect_pattern(cluster)
    assert isinstance(result, dict)
    assert "has_pattern" in result
    assert "pattern_type" in result
    assert "evidence_count" in result


def test_pattern_type_is_valid():
    from services.pattern_detector import PATTERN_TYPES
    cluster = _make_cluster(3, 0.75)
    result = detect_pattern(cluster)
    assert result["pattern_type"] in PATTERN_TYPES
