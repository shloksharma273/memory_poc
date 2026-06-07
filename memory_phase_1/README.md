# Arango Agentic Memory System

A 3-phase agentic memory engine that stores, classifies, deduplicates, scores, and reflects on agent memories — backed by ArangoDB and Ollama running entirely locally.

---

## The Big Picture

The system is not a simple key-value store. It decides *what's worth remembering*, *how certain it is*, *whether it's a duplicate*, and *what patterns are emerging* across memories over time. Think of it like a brain that reads, filters, connects, and reflects on experiences.

Three layers are built on top of each other:

```
Phase 1 → Store & Retrieve    (the core)
Phase 2 → Score & Deduplicate (the intelligence)
Phase 3 → Reflect & Summarize (the wisdom)
```

---

## Phase 1 — Core Memory Engine

### Step 1: Input arrives

Raw text arrives at `POST /memory/add` — a support ticket, a CRM note, a runbook entry — with a tenant ID and source system. The system doesn't store it directly. It first decides *whether it deserves to be remembered*.

**Files:** `routes/memory_routes.py`, `models/api_models.py`

---

### Step 2: Candidate Scoring

The text gets an embedding via **nomic-embed-text** (Ollama). That embedding is compared against all existing memories using cosine similarity computed directly in ArangoDB AQL — no separate vector DB needed.

A **novelty score** is calculated: how different is this from what's already stored? Combined with a **source weight** (CRM is more trustworthy than a chat log):

```
memory_score = 0.60 × novelty + 0.40 × source_weight
```

If `memory_score < 0.35`, the text is rejected as `not_stored`.

**Files:** `services/candidate_generator.py`, `services/embedding_service.py`, `db/queries.py`

---

### Step 3: Classification

If it passes the threshold, **qwen2.5-coder:7b** (Ollama) classifies the text into one of three memory types:

- **Episodic** — a time-bound event ("Customer ABC reported a failure on Monday")
- **Semantic** — a stable fact ("Customer ABC uses Payment Gateway X")
- **Procedural** — a how-to or SOP ("For gateway failures, check the retry queue")

Each type is stored in its own ArangoDB collection.

**Files:** `services/classifier.py`

---

### Step 4: Entity Extraction + Graph Linking

The LLM extracts named entities (people, products, systems). Each entity gets a node in the `entities` collection. Edge collections link the memory to its entities and source document, forming a **knowledge graph**.

**Files:** `services/entity_extractor.py`, `services/graph_service.py`

---

### Step 5: Written to ArangoDB

The classified, embedded, entity-linked memory document is written to the correct collection with full provenance metadata.

**Files:** `services/memory_writer.py`, `db/arango_client.py`, `db/setup_db.py`

---

### Step 6: Retrieval

On `POST /memory/retrieve`, two searches run in parallel:

1. **Semantic search** — embed the query, cosine similarity against all 3 memory collections
2. **Graph search** — extract entities from the query, traverse edges to find related memories

Results are merged and ranked:

```
final_score = 0.70 × semantic + 0.30 × graph
```

The response groups memories into `facts`, `events`, `procedures`, and `citations` — ready for an LLM to use as context.

**Files:** `services/memory_retriever.py`, `services/context_builder.py`, `db/queries.py`

---

## Phase 2 — Intelligence Layer

### Importance Scoring

When a memory is stored it gets an `importance_score`:

```
importance = 0.40 × impact + 0.25 × frequency + 0.20 × recency + 0.15 × usage
```

Impact is inferred from language ("critical", "outage" = high). Frequency counts how many near-duplicates were seen. Recency weights recent events higher.

**File:** `services/importance_scorer.py`

---

### Confidence Scoring

```
confidence = 0.40 × source_reliability + 0.30 × agreement + 0.20 × recency + 0.10 × accuracy
```

A CRM record has higher source reliability than an anonymous report. Agreement measures whether other memories say the same thing.

**File:** `services/confidence_scorer.py`

---

### Quality Score

```
quality = 0.60 × importance + 0.40 × confidence
```

This single number summarizes how much to trust a memory and drives ranking.

---

### Temporal Metadata

Every memory gets `valid_from`, `valid_to`, and `recorded_at` timestamps extracted from the input or inferred from context.

**File:** `services/temporal_service.py`

---

### Consolidation (Deduplication)

When a new memory arrives, before storing it the system checks all existing memories:

```
consolidation_score = 0.70 × embedding_similarity
                    + 0.20 × entity_overlap (Jaccard)
                    + 0.10 × type_match
```

If `score ≥ 0.80`, it's a near-duplicate — instead of storing a second copy, the system **merges** it into the existing memory, incrementing `duplicate_count` and bumping `confidence_score`.

**File:** `services/consolidation_service.py`

---

### Quality-Aware Retrieval Ranking

```
final_score = 0.50 × semantic + 0.20 × graph + 0.20 × importance + 0.10 × confidence
```

High-quality memories naturally rise to the top.

**File:** `services/ranking_service.py`

---

### Schema Migration

Adds Phase 2 fields to existing memories and creates `memory_merge_logs`.

**File:** `migrations/phase_2_schema_migration.py`

---

## Phase 3 — Reflection & Summarization

### Step 1: Candidate Selection

`POST /intelligence/reflect` pulls memories from the last N days with quality above a threshold. These are the candidates for pattern analysis.

**File:** `services/reflection_candidate_selector.py`

---

### Step 2: Clustering

Candidate memories are grouped by similarity:

```
cluster_score = 0.60 × embedding_sim + 0.25 × entity_overlap
              + 0.10 × type_match    + 0.05 × time_proximity
```

Memories that score above `similarity_threshold` against each other are placed in the same cluster.

**File:** `services/memory_clustering_service.py`

---

### Step 3: Pattern Detection

For each cluster with `size ≥ 2`, the LLM is asked: *"Do these memories show a recurring pattern?"* It returns a structured result with `pattern_type` (recurring_issue, behavior_pattern, risk_pattern, etc.) and a `pattern_summary`. A deterministic fallback fires if the LLM call fails.

**File:** `services/pattern_detector.py`

---

### Step 4: Reflective Memory Created

A new document is written to `reflective_memories` — a higher-order memory *about* other memories:

```json
{
  "reflection_text": "Customer ABC repeatedly reports payment failures post-deployment",
  "pattern_type": "recurring_issue",
  "support_count": 2,
  "supporting_memory_ids": ["episodic_memories/abc", "episodic_memories/xyz"]
}
```

Edge links connect it to the evidence memories.

**File:** `services/reflection_generator.py`

---

### Step 5: Summarization

`POST /intelligence/summarize` groups memories by time window and asks the LLM to write a concise rollup, stored in `summary_memories`.

**File:** `services/summarization_service.py`

---

### Step 6: Reflection-Aware Retrieval

On retrieval, `reflective_memories` and `summary_memories` are searched alongside base memories. The ranking applies a **type boost**:

```
final_score = 0.40 × semantic + 0.20 × graph + 0.20 × importance
            + 0.10 × confidence + 0.10 × type_boost

type_boost:  reflective=1.00 | summary=0.85 | procedural=0.80 | semantic=0.70 | episodic=0.60
```

Reflective memories surface in `context.reflections` — an LLM gets not just raw facts but the patterns the system has detected over time.

**Files:** `services/reflection_retriever.py`, `services/context_builder.py`, `services/ranking_service.py`

---

### Orchestration and Routes

**Files:** `services/phase_3_orchestrator.py`, `routes/intelligence_routes.py`, `migrations/phase_3_schema_migration.py`

---

## Data Flow in One Line

> Raw text → scored for novelty → classified by LLM → embedded and graph-linked → deduplicated against existing memories → scored for importance and confidence → periodically clustered for pattern detection → surfaced as reflective memories in future retrievals.

---

## Tech Stack

| Layer | Tool |
|---|---|
| API | FastAPI — `app.py` |
| Config | pydantic-settings — `config/settings.py` |
| Database | ArangoDB 3.12 (documents + graph + cosine AQL) |
| DB client | python-arango — `db/arango_client.py` |
| AQL queries | `db/queries.py` |
| Embeddings | nomic-embed-text via Ollama (768-dim) |
| LLM | qwen2.5-coder:7b via Ollama |
| API models | `models/api_models.py` |

Everything runs locally — no cloud APIs, no external vector DB.

---

## Collections

| Collection | Type | Purpose |
|---|---|---|
| `episodic_memories` | Document | Time-bound events |
| `semantic_memories` | Document | Facts and stable knowledge |
| `procedural_memories` | Document | Workflows and SOPs |
| `entities` | Document | Extracted named entities |
| `provenance_records` | Document | Source traceability |
| `memory_merge_logs` | Document | Audit trail for merges |
| `reflective_memories` | Document | LLM-detected patterns (Phase 3) |
| `summary_memories` | Document | Temporal rollup summaries (Phase 3) |
| `memory_mentions_entity` | Edge | Memory → Entity |
| `memory_has_provenance` | Edge | Memory → Provenance record |
| `reflection_supported_by_memory` | Edge | Reflection → Supporting memories (Phase 3) |
| `summary_contains_memory` | Edge | Summary → Summarized memories (Phase 3) |

---

## Setup

```bash
# 1. Start ArangoDB
docker run -d --name arangodb -p 8529:8529 -e ARANGO_ROOT_PASSWORD=openSesame arangodb

# 2. Start Ollama and pull models
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text

# 3. Install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env   # credentials already pre-filled

# 5. Create collections
.venv/bin/python db/setup_db.py
.venv/bin/python migrations/phase_2_schema_migration.py
.venv/bin/python migrations/phase_3_schema_migration.py

# 6. Start the server
.venv/bin/uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

---

## Running Tests

```bash
# End-to-end feature test (recommended)
.venv/bin/python demo_test.py

# Unit tests only (no ArangoDB/Ollama required)
.venv/bin/python -m pytest tests/test_importance_scorer.py tests/test_confidence_scorer.py tests/test_temporal_memory.py -v

# All integration tests
.venv/bin/python -m pytest tests/ -v
```

See `COMMANDS.md` for the full curl command reference.
