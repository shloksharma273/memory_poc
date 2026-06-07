"""Unit tests for memory clustering service — no DB needed."""
import pytest
from services.memory_clustering_service import cluster_memories, _jaccard, _time_proximity


def _fake_memory(text, emb, entity_names, mem_type="episodic", created_at="2026-06-01T10:00:00Z"):
    return {
        "_id": f"episodic_memories/fake_{text[:5]}",
        "text": text,
        "embedding": emb,
        "entity_names": set(entity_names),
        "type": mem_type,
        "quality_score": 0.75,
        "importance_score": 0.60,
        "confidence_score": 0.70,
        "created_at": created_at,
    }


PAYMENT_EMB = [0.9, 0.1, 0.05, 0.1]
HR_EMB      = [0.05, 0.1, 0.9, 0.1]


def _norm(v):
    mag = sum(x*x for x in v)**0.5
    return [x/mag for x in v]


PAYMENT_EMB = _norm(PAYMENT_EMB)
HR_EMB      = _norm(HR_EMB)


def test_jaccard_identical():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint():
    assert _jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty():
    assert _jaccard(set(), set()) == 0.0


def test_time_proximity_same_day():
    assert _time_proximity("2026-06-01T10:00:00Z", "2026-06-01T12:00:00Z") == 1.0


def test_time_proximity_within_7():
    assert _time_proximity("2026-06-01T10:00:00Z", "2026-06-05T10:00:00Z") == 1.0


def test_time_proximity_within_30():
    assert _time_proximity("2026-06-01T10:00:00Z", "2026-06-20T10:00:00Z") == 0.5


def test_time_proximity_over_30():
    assert _time_proximity("2026-01-01T10:00:00Z", "2026-06-01T10:00:00Z") == 0.0


def test_no_clusters_when_too_few_similar():
    mems = [
        _fake_memory("payment failure A", PAYMENT_EMB, ["abc"], "episodic"),
        _fake_memory("HR policy update",  HR_EMB,      ["hr"],  "semantic"),
    ]
    clusters = cluster_memories(mems, similarity_threshold=0.75, min_cluster_size=3)
    assert clusters == []


def test_cluster_formed_from_similar_memories():
    mems = [
        _fake_memory("payment failure one",   PAYMENT_EMB, ["abc", "payment"], "episodic"),
        _fake_memory("payment failure two",   PAYMENT_EMB, ["abc", "payment"], "episodic"),
        _fake_memory("payment failure three", PAYMENT_EMB, ["abc", "payment"], "episodic"),
        _fake_memory("HR policy unrelated",   HR_EMB,      ["hr"],             "semantic"),
    ]
    clusters = cluster_memories(mems, similarity_threshold=0.70, min_cluster_size=3)
    assert len(clusters) >= 1
    assert len(clusters[0]["memories"]) >= 3


def test_cluster_has_required_fields():
    mems = [_fake_memory(f"payment issue {i}", PAYMENT_EMB, ["abc"], "episodic") for i in range(3)]
    clusters = cluster_memories(mems, similarity_threshold=0.70, min_cluster_size=3)
    if clusters:
        c = clusters[0]
        assert "cluster_id" in c
        assert "cluster_theme" in c
        assert "memories" in c
        assert "avg_quality_score" in c
