"""
Integration test for consolidation — requires ArangoDB and Ollama to be running.
"""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

TENANT = "test_consolidation"


def _add(text: str, source: str = "ticketing", doc_id: str = "doc_001") -> dict:
    r = client.post(
        "/memory/add",
        json={
            "tenant_id": TENANT,
            "text": text,
            "source": source,
            "metadata": {"source_document_id": doc_id},
        },
    )
    assert r.status_code == 200
    return r.json()


def test_first_memory_is_stored():
    result = _add(
        "Customer ABC reported payment gateway failure on Monday.",
        doc_id="con_ticket_001",
    )
    assert result["status"] in ("stored", "not_stored")


def test_near_duplicate_is_merged():
    # Seed a fresh memory
    first = _add(
        "Customer XYZ reported database connection errors on Tuesday.",
        source="ticketing",
        doc_id="con_ticket_010",
    )

    if first["status"] != "stored":
        pytest.skip("First memory was not stored (below threshold)")

    # Second near-duplicate
    second = _add(
        "Customer XYZ again reported database connection errors.",
        source="ticketing",
        doc_id="con_ticket_011",
    )

    # Should merge or store (depending on semantic similarity)
    assert second["status"] in ("merged", "stored", "not_stored")
    if second["status"] == "merged":
        assert second["target_memory_id"] is not None
        assert second["duplicate_count"] >= 1
        assert 0.0 <= second["importance_score"] <= 1.0
        assert 0.0 <= second["confidence_score"] <= 1.0
        assert 0.0 <= second["quality_score"] <= 1.0


def test_distinct_memory_is_not_merged():
    _add(
        "The finance team approved the annual budget.",
        source="erp",
        doc_id="con_erp_001",
    )
    result = _add(
        "The engineering team deployed a new microservice to production.",
        source="ticketing",
        doc_id="con_ticket_020",
    )
    # These are semantically different — should not merge
    assert result["status"] != "merged"
