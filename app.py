"""
Agentic Memory POC — FastAPI application.

Combines ArangoDB (document + graph + vector + BM25) with Ollama LLMs
to create a unified memory layer for agentic systems.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from db.setup_collections import setup_collections
from db.setup_views import setup_views
from models.schemas import (
    MemoryAddRequest,
    MemoryAddResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    GraphResponse,
)
from services.memory_service import add_memory
from services.retrieval_service import hybrid_search
from services.graph_service import get_user_graph


# ── Lifespan ─────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure collections and views exist."""
    print("\n🧠 Agentic Memory POC — Starting up...")
    setup_collections()
    setup_views()
    print("✓ Ready.\n")
    yield
    print("\n🧠 Shutting down.")


# ── App ──────────────────────────────────────────────────────────────


app = FastAPI(
    title="Agentic Memory POC",
    description=(
        "Hybrid Mem0 + Graphiti inspired memory system using ArangoDB. "
        "Combines document storage, knowledge graphs, vector search, "
        "and BM25 retrieval in a single unified layer."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ── Routes ───────────────────────────────────────────────────────────


@app.post("/memory/add", response_model=MemoryAddResponse)
def memory_add(request: MemoryAddRequest):
    """
    Ingest a memory: store event → extract entities → build graph → embed.
    """
    print(f"\n📥 Adding memory for user={request.user_id}")
    result = add_memory(request.user_id, request.message)
    return result


@app.post("/memory/search", response_model=MemorySearchResponse)
def memory_search(request: MemorySearchRequest):
    """
    Hybrid search: semantic + graph + BM25, merged and deduplicated.
    """
    print(f"\n🔍 Searching: {request.query!r}")
    results = hybrid_search(request.query, request.user_id)
    return results


@app.get("/graph/{user_id}", response_model=GraphResponse)
def graph_user(user_id: str = "demo_user"):
    """
    Return all graph relationships for a user (1–2 hops outbound).
    """
    return get_user_graph(user_id)


@app.get("/health")
def health():
    """Simple health check."""
    return {"status": "ok"}
