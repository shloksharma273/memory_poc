"""Integration tests for reflection generator — requires ArangoDB + Ollama."""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_rgen"


def _add(text, source="ticketing"):
    r = client.post("/memory/add", json={
        "tenant_id": TENANT, "text": text, "source": source,
        "metadata": {"source_document_id": "rgen_001", "event_timestamp": "2026-06-01T10:00:00Z"},
    })
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def seed():
    _add("Customer DEF reported SSL certificate errors after deployment.")
    _add("Customer DEF again had SSL errors post-deployment.")
    _add("Customer DEF SSL certificate expired causing service outage.")


def test_reflect_endpoint_returns_200():
    r = client.post("/intelligence/reflect", json={
        "tenant_id": TENANT, "time_window_days": 30, "min_quality_score": 0.0,
    })
    assert r.status_code == 200


def test_reflect_response_shape():
    r = client.post("/intelligence/reflect", json={
        "tenant_id": TENANT, "time_window_days": 30, "min_quality_score": 0.0,
    })
    data = r.json()
    assert data["status"] == "completed"
    assert "candidate_count" in data
    assert "cluster_count" in data
    assert "patterns_detected" in data
    assert "reflections_created" in data
    assert "reflections_updated" in data


def test_list_reflections():
    r = client.get(f"/intelligence/reflections?tenant_id={TENANT}")
    assert r.status_code == 200
    data = r.json()
    assert "reflections" in data
    for ref in data["reflections"]:
        assert "reflection_id" in ref
        assert "reflection_text" in ref
        assert "quality_score" in ref
