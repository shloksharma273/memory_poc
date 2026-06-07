"""Unit + integration tests for reflection candidate selector."""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_rcs"


def _add(text, source="ticketing", score_above_threshold=True):
    payload = {
        "tenant_id": TENANT,
        "text": text,
        "source": source,
        "metadata": {"source_document_id": "rcs_001"},
    }
    r = client.post("/memory/add", json=payload)
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def seed():
    _add("Customer XYZ reported database errors three times this week.", "ticketing")
    _add("Customer XYZ uses the PostgreSQL database for all transactions.", "crm")
    _add("Database connection pool exhaustion procedure: restart service and alert DBA.", "docs")


def test_selector_import():
    from services.reflection_candidate_selector import select_reflection_candidates
    assert callable(select_reflection_candidates)


def test_selector_returns_list():
    from services.reflection_candidate_selector import select_reflection_candidates
    candidates = select_reflection_candidates(TENANT, time_window_days=30, min_quality_score=0.0)
    assert isinstance(candidates, list)


def test_selector_filters_by_tenant():
    from services.reflection_candidate_selector import select_reflection_candidates
    candidates = select_reflection_candidates("nonexistent_tenant_xyz", time_window_days=30)
    assert len(candidates) == 0


def test_candidates_have_required_fields():
    from services.reflection_candidate_selector import select_reflection_candidates
    candidates = select_reflection_candidates(TENANT, time_window_days=30, min_quality_score=0.0)
    for c in candidates:
        assert "_id" in c
        assert "text" in c
        assert "embedding" in c
        assert "entity_names" in c
        assert "quality_score" in c


def test_quality_filter_works():
    from services.reflection_candidate_selector import select_reflection_candidates
    high = select_reflection_candidates(TENANT, min_quality_score=0.0)
    low = select_reflection_candidates(TENANT, min_quality_score=0.99)
    assert len(high) >= len(low)
