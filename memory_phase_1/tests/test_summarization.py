"""Integration tests for summarization service — requires ArangoDB + Ollama."""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_summ"


def _add(text, source="ticketing"):
    r = client.post("/memory/add", json={
        "tenant_id": TENANT, "text": text, "source": source,
        "metadata": {
            "source_document_id": "summ_001",
            "event_timestamp": "2026-06-04T10:00:00Z",
        },
    })
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def seed():
    _add("Customer GHI reported login failures due to OAuth token expiry.")
    _add("Customer GHI uses the OAuth service for all authentication.")
    _add("For OAuth token issues, rotate the client secret and redeploy.")
    _add("Customer GHI had another OAuth-related login issue.")
    _add("OAuth token expiry caused widespread login failures for multiple customers.")


def test_summarize_endpoint_200():
    r = client.post("/intelligence/summarize", json={
        "tenant_id": TENANT,
        "summary_level": "weekly",
        "group_by": "time",
        "start_time": "2026-06-01T00:00:00Z",
        "end_time": "2026-06-07T23:59:59Z",
    })
    assert r.status_code == 200


def test_summarize_response_shape():
    r = client.post("/intelligence/summarize", json={
        "tenant_id": TENANT,
        "summary_level": "weekly",
        "group_by": "time",
        "start_time": "2026-06-01T00:00:00Z",
        "end_time": "2026-06-07T23:59:59Z",
    })
    data = r.json()
    assert data["status"] in ("completed", "skipped")
    if data["status"] == "completed":
        assert "summary_id" in data
        assert "summary_text" in data
        assert "memory_count" in data


def test_list_summaries():
    r = client.get(f"/intelligence/summaries?tenant_id={TENANT}")
    assert r.status_code == 200
    assert "summaries" in r.json()
