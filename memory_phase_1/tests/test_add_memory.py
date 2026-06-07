"""
Integration tests for POST /memory/add.
Requires ArangoDB and Ollama to be running.
"""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_add"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_add_episodic_memory():
    r = client.post(
        "/memory/add",
        json={
            "tenant_id": TENANT,
            "text": "Customer ABC reported repeated payment gateway failures on Monday.",
            "source": "ticketing",
            "metadata": {"source_document_id": "ticket_001"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("stored", "not_stored")
    assert "memory_score" in data


def test_add_semantic_memory():
    r = client.post(
        "/memory/add",
        json={
            "tenant_id": TENANT,
            "text": "Customer ABC uses Payment Gateway X for checkout transactions.",
            "source": "crm",
            "metadata": {"source_document_id": "crm_001"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("stored", "not_stored")


def test_add_procedural_memory():
    r = client.post(
        "/memory/add",
        json={
            "tenant_id": TENANT,
            "text": "For payment gateway failure, check transaction logs, retry queue, and notify finance operations.",
            "source": "docs",
            "metadata": {"source_document_id": "runbook_001"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("stored", "not_stored")


def test_add_memory_missing_text_returns_422():
    r = client.post(
        "/memory/add",
        json={"tenant_id": TENANT, "source": "ticketing"},
    )
    assert r.status_code == 422


def test_stored_response_shape():
    r = client.post(
        "/memory/add",
        json={
            "tenant_id": TENANT,
            "text": "Finance team approved the Q3 budget increase.",
            "source": "erp",
            "metadata": {},
        },
    )
    assert r.status_code == 200
    data = r.json()
    if data["status"] == "stored":
        assert "memory_id" in data
        assert "memory_type" in data
        assert data["memory_type"] in ("episodic", "semantic", "procedural")
        assert isinstance(data["entities"], list)
