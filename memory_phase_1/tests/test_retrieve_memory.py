"""
Integration tests for POST /memory/retrieve.
Requires ArangoDB and Ollama to be running, and sample data to have been inserted.
"""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_retrieve"

# ── helpers ──────────────────────────────────────────────────────────────────

def _insert(text: str, source: str, doc_id: str):
    client.post(
        "/memory/add",
        json={"tenant_id": TENANT, "text": text, "source": source, "metadata": {"source_document_id": doc_id}},
    )


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def seed_memories():
    _insert("Customer ABC reported repeated payment gateway failures on Monday.", "ticketing", "ticket_001")
    _insert("Customer ABC uses Payment Gateway X for checkout transactions.", "crm", "crm_001")
    _insert("For payment gateway failure, check transaction logs, retry queue, and notify finance operations.", "docs", "runbook_001")


# ── tests ────────────────────────────────────────────────────────────────────

def test_retrieve_returns_200():
    r = client.post(
        "/memory/retrieve",
        json={"tenant_id": TENANT, "query": "What payment issues did Customer ABC face?", "top_k": 5},
    )
    assert r.status_code == 200


def test_retrieve_response_shape():
    r = client.post(
        "/memory/retrieve",
        json={"tenant_id": TENANT, "query": "payment gateway Customer ABC", "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert "query" in data
    assert "context" in data
    ctx = data["context"]
    assert "facts" in ctx
    assert "events" in ctx
    assert "procedures" in ctx
    assert "citations" in ctx


def test_retrieve_returns_results():
    r = client.post(
        "/memory/retrieve",
        json={"tenant_id": TENANT, "query": "payment gateway failure Customer ABC", "top_k": 5},
    )
    assert r.status_code == 200
    ctx = r.json()["context"]
    total = len(ctx["facts"]) + len(ctx["events"]) + len(ctx["procedures"])
    assert total >= 1, "Expected at least one memory returned for payment gateway query"


def test_retrieve_missing_query_returns_422():
    r = client.post("/memory/retrieve", json={"tenant_id": TENANT})
    assert r.status_code == 422
