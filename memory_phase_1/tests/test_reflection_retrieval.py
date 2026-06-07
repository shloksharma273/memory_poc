"""Integration tests for reflection-aware retrieval."""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_rret"


def _add(text, source="ticketing"):
    r = client.post("/memory/add", json={
        "tenant_id": TENANT,
        "text": text,
        "source": source,
        "metadata": {"source_document_id": "rret_001", "event_timestamp": "2026-06-01T10:00:00Z"},
    })
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def seed_and_reflect():
    _add("Customer JKL reported network timeout errors repeatedly.")
    _add("Customer JKL had network timeouts causing service disruption.")
    _add("Customer JKL experienced another network timeout outage.")
    _add("Customer JKL uses a dedicated VPN for connectivity.")
    # Trigger reflection
    client.post("/intelligence/reflect", json={"tenant_id": TENANT, "time_window_days": 30, "min_quality_score": 0.0})


def test_retrieve_includes_reflections_key():
    r = client.post("/memory/retrieve", json={
        "tenant_id": TENANT,
        "query": "What recurring issues does Customer JKL have?",
        "top_k": 5,
    })
    assert r.status_code == 200
    ctx = r.json()["context"]
    assert "reflections" in ctx
    assert "summaries" in ctx


def test_retrieve_context_shape():
    r = client.post("/memory/retrieve", json={
        "tenant_id": TENANT,
        "query": "network timeout customer JKL",
        "top_k": 5,
    })
    ctx = r.json()["context"]
    for key in ("facts", "events", "procedures", "reflections", "summaries", "citations"):
        assert key in ctx


def test_reflection_item_has_quality_score():
    r = client.post("/memory/retrieve", json={
        "tenant_id": TENANT,
        "query": "What recurring issues does Customer JKL have?",
        "top_k": 10,
    })
    reflections = r.json()["context"]["reflections"]
    for ref in reflections:
        assert "score" in ref
        assert "confidence_score" in ref
