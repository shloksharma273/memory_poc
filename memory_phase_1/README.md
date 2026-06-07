# Arango Agentic Memory — Phase 1 + Phase 2

Core Memory Engine with Intelligence Layer: store, classify, deduplicate, score, and retrieve agent memories backed by ArangoDB and Ollama.

---

## What Phase 2 adds over Phase 1

| Capability | Phase 1 | Phase 2 |
|---|---|---|
| Importance scoring | ✗ | ✓ |
| Confidence scoring | ✗ | ✓ |
| Quality score | ✗ | ✓ |
| Consolidation / deduplication | ✗ | ✓ |
| Temporal fields (valid_from / valid_to) | ✗ | ✓ |
| Merge audit log | ✗ | ✓ |
| Access tracking | ✗ | ✓ |
| Quality-aware retrieval ranking | ✗ | ✓ |
| Citation confidence scores | ✗ | ✓ |

---

## Architecture

```
User / Agent Input
      ↓
POST /memory/add
      ↓
Candidate Generator  (novelty × source weight → memory_score)
      ↓
Memory Classifier    (LLM → episodic | semantic | procedural)
      ↓
Entity Extractor     (LLM → named entities)
      ↓
Embedding Generator  (Ollama nomic-embed-text)
      ↓
Memory Writer        (ArangoDB document + provenance record)
      ↓
Graph Linker         (memory_mentions_entity, memory_has_provenance edges)
      ↓
POST /memory/retrieve
      ↓
Semantic Search      (AQL cosine similarity across all 3 memory collections)
      ↓
Graph Traversal      (inbound edges from matched entities)
      ↓
Hybrid Fusion        (0.70 × semantic + 0.30 × graph)
      ↓
Context Builder      (facts / events / procedures / citations)
      ↓
Agent-ready context
```

---

## Collections

| Collection | Type | Purpose |
|---|---|---|
| `memory_events` | Document | Raw input before processing |
| `episodic_memories` | Document | Time-bound events |
| `semantic_memories` | Document | Facts and stable knowledge |
| `procedural_memories` | Document | Workflows and SOPs |
| `entities` | Document | Extracted named entities |
| `provenance_records` | Document | Source traceability |
| `memory_mentions_entity` | Edge | Memory → Entity links |
| `memory_has_provenance` | Edge | Memory → Provenance links |
| `entity_related_to_entity` | Edge | Entity → Entity links (future) |

---

## Setup

### 1. Start ArangoDB

```bash
docker run -d \
  --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=openSesame \
  arangodb
```

### 2. Install dependencies

```bash
cd memory_phase_1
pip install -r requirements.txt
```

### 3. Configure environment

Copy and edit the example env file:

```bash
cp .env.example .env
```

Default values match the local Ollama + ArangoDB setup:

```env
ARANGO_HOST=http://localhost:8529
ARANGO_DB=memory_poc
ARANGO_USERNAME=root
ARANGO_PASSWORD=openSesame

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5-coder:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

MEMORY_THRESHOLD=0.50
```

### 4. Create database collections

```bash
python db/setup_db.py
```

### 5. Start the API server

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

---

## API Examples

### Add Memory

```bash
curl -X POST http://localhost:8000/memory/add \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "text": "Customer ABC reported repeated payment gateway failures on Monday.",
    "source": "ticketing",
    "metadata": {
      "source_document_id": "ticket_001",
      "user_id": "user_123"
    }
  }'
```

Response (stored):

```json
{
  "status": "stored",
  "memory_id": "a3f8c91d2e4b6f78",
  "memory_type": "episodic",
  "memory_score": 0.88,
  "entities": [
    {"name": "Customer ABC", "type": "customer"},
    {"name": "Payment Gateway", "type": "system"}
  ]
}
```

Response (not stored — duplicate or low-signal input):

```json
{
  "status": "not_stored",
  "reason": "memory_score_below_threshold",
  "memory_score": 0.31
}
```

---

### Retrieve Memory

```bash
curl -X POST http://localhost:8000/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "query": "What payment issues did Customer ABC face?",
    "top_k": 5
  }'
```

Response:

```json
{
  "query": "What payment issues did Customer ABC face?",
  "context": {
    "facts": [
      {
        "memory_id": "b1c2d3e4f5a6b7c8",
        "text": "Customer ABC uses Payment Gateway X for checkout transactions.",
        "score": 0.87
      }
    ],
    "events": [
      {
        "memory_id": "a3f8c91d2e4b6f78",
        "text": "Customer ABC reported repeated payment gateway failures on Monday.",
        "score": 0.91
      }
    ],
    "procedures": [
      {
        "memory_id": "d4e5f6a7b8c9d0e1",
        "text": "For payment gateway failure, check transaction logs, retry queue, and notify finance operations.",
        "score": 0.76
      }
    ],
    "citations": [
      {
        "memory_id": "a3f8c91d2e4b6f78",
        "source_system": "ticketing",
        "source_document_id": "ticket_001"
      }
    ]
  }
}
```

---

## Sample Test Data

Load all three memory types:

```bash
# Episodic
curl -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d '{"tenant_id":"default","text":"Customer ABC reported repeated payment gateway failures on Monday.","source":"ticketing","metadata":{"source_document_id":"ticket_001"}}'

# Semantic
curl -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d '{"tenant_id":"default","text":"Customer ABC uses Payment Gateway X for checkout transactions.","source":"crm","metadata":{"source_document_id":"crm_001"}}'

# Procedural
curl -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d '{"tenant_id":"default","text":"For payment gateway failure, check transaction logs, retry queue, and notify finance operations.","source":"docs","metadata":{"source_document_id":"runbook_001"}}'
```

Then retrieve:

```bash
curl -X POST http://localhost:8000/memory/retrieve -H "Content-Type: application/json" \
  -d '{"tenant_id":"default","query":"What payment issues did Customer ABC face?","top_k":5}'
```

---

## Run Tests

```bash
pytest tests/ -v
```

Tests require ArangoDB and Ollama to be running.

---

## Candidate Scoring

```
memory_score = 0.60 × novelty + 0.40 × source_weight
```

Source weights:

| Source | Weight |
|---|---|
| erp | 1.00 |
| crm | 0.90 |
| ticketing | 0.80 |
| docs | 0.70 |
| email | 0.60 |
| slack / chat | 0.40 |
| unknown | 0.30 |

Novelty = `1 - max_cosine_similarity` vs all existing memories. First memory gets novelty = 1.0.

Memories with `memory_score < 0.50` are not stored.

---

## Hybrid Retrieval

```
final_score = 0.70 × semantic_score + 0.30 × graph_score
```

- **Semantic** — AQL cosine similarity across all memory collections (works on all ArangoDB versions)
- **Graph** — inbound edge traversal from entities matched in the query

---

## Phase 2 Scoring Formulas

### Importance
```
importance = 0.40 × impact + 0.25 × frequency + 0.20 × recency + 0.15 × usage
impact     = (source_weight + memory_type_weight) / 2
frequency  = min(duplicate_count / 5, 1.0)   # 0.20 for new memories
recency    = max(0, 1 − days_old / 30)        # 1.0 for new memories
usage      = min(access_count / 10, 1.0)     # 0.0 for new memories
```

### Confidence
```
confidence = 0.40 × reliability + 0.30 × agreement + 0.20 × recency + 0.10 × accuracy
agreement  = 1.0 (dup≥3) | 0.75 (dup=2) | 0.50 (dup=1) | 0.20 (new)
```

### Quality (combined ranking signal)
```
quality_score = 0.60 × importance_score + 0.40 × confidence_score
```

### Consolidation (deduplication)
```
consolidation_score = 0.70 × embedding_similarity
                    + 0.20 × entity_overlap (Jaccard)
                    + 0.10 × type_match
```
Threshold: **0.80** — memories scoring above are merged, not stored as new.

### Phase 2 Retrieval Ranking
```
final_score = 0.50 × semantic_score
            + 0.20 × graph_score
            + 0.20 × importance_score
            + 0.10 × confidence_score
```

---

## Phase 2 Setup

Run schema migration once after upgrade:

```bash
python migrations/phase_2_schema_migration.py
```

This adds Phase 2 fields to existing memories and creates the `memory_merge_logs` collection.

---

## Phase 2 API Examples

### Stored response (new memory)

```json
{
  "status": "stored",
  "memory_id": "42e2b740f507452c",
  "memory_type": "episodic",
  "memory_score": 0.92,
  "importance_score": 0.55,
  "confidence_score": 0.685,
  "quality_score": 0.604,
  "temporal": {
    "valid_from": "2026-06-07T10:00:00Z",
    "valid_to": "2026-06-07T10:00:00Z",
    "recorded_at": "2026-06-07T15:38:14Z"
  },
  "entities": [{"name": "ABC", "type": "customer"}]
}
```

### Merged response (near-duplicate)

```json
{
  "status": "merged",
  "target_memory_id": "42e2b740f507452c",
  "target_collection": "episodic_memories",
  "consolidation_score": 0.8168,
  "duplicate_count": 1,
  "importance_score": 0.55,
  "confidence_score": 0.775,
  "quality_score": 0.64
}
```

### Retrieval response (Phase 2)

```json
{
  "query": "What payment issues did Customer ABC face?",
  "context": {
    "events": [{
      "memory_id": "42e2b740f507452c",
      "text": "Customer ABC reported repeated payment gateway failures on Monday.",
      "score": 0.5475,
      "importance_score": 0.55,
      "confidence_score": 0.775,
      "quality_score": 0.64,
      "valid_from": "2026-06-07T10:00:00Z",
      "valid_to": "2026-06-07T10:00:00Z"
    }],
    "citations": [{
      "memory_id": "42e2b740f507452c",
      "source_system": "ticketing",
      "source_document_id": "ticket_001",
      "confidence_score": 0.775
    }]
  }
}
```

---

## Phase 1 Limitations

- No reflection or summarization pipeline
- No memory promotion or retention/decay
- No BM25 keyword search
- No temporal weighting
- No multi-tenant isolation beyond `tenant_id` filtering
- Vector index creation attempted but falls back to AQL cosine similarity if ArangoDB < 3.12
- LLM calls are synchronous; high-throughput use cases should add async queuing

---

## Next Phases

- Phase 3: Reflection pipeline, memory summarization, promotion engine
- Phase 4: Retention/decay lifecycle, full ontology enforcement
- Phase 5: Multi-tenant isolation, benchmarking, UI dashboard
