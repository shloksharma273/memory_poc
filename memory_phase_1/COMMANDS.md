# Commands Reference

All commands are run from the `memory_phase_1/` directory.

---

## 1. ArangoDB

### What is ArangoDB

ArangoDB is a native multi-model database that supports:

- **Document store** — JSON documents (like MongoDB)
- **Graph database** — edges between documents (like Neo4j)
- **Key-value store** — fast lookups by key

This project uses all three models simultaneously:
- Document collections store memories, entities, and provenance
- Edge collections link memories to entities and provenance (graph)
- Vector embeddings stored in document fields for semantic search

### Version in use

| Component | Version |
|---|---|
| ArangoDB server | 3.12.9-1 |
| python-arango client | 8.3.3 |

### Connection details

| Setting | Value |
|---|---|
| Host | http://localhost:8529 |
| Database | memory_poc |
| Username | root |
| Password | openSesame |
| Web UI | http://localhost:8529/_db/memory_poc/_admin/aardvark/ |

### Collections in this project

**Document collections:**

| Collection | Purpose |
|---|---|
| `memory_events` | Raw input before processing |
| `episodic_memories` | Time-bound events (text field: `text`) |
| `semantic_memories` | Stable facts and relationships (text field: `fact`) |
| `procedural_memories` | Workflows and SOPs (text field: `procedure`) |
| `entities` | Extracted named entities |
| `provenance_records` | Source traceability metadata |
| `memory_merge_logs` | Audit trail for merged/consolidated memories |

**Edge collections:**

| Collection | Connects |
|---|---|
| `memory_mentions_entity` | Memory → Entity |
| `memory_has_provenance` | Memory → Provenance record |
| `entity_related_to_entity` | Entity → Entity (reserved for future use) |

### Start ArangoDB with Docker

```bash
docker run -d \
  --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=openSesame \
  arangodb
```

### Check ArangoDB is running

```bash
curl http://localhost:8529/_api/version
```

Expected output:

```json
{"server":"arango","license":"community","version":"3.12.9-1"}
```

### Stop and remove ArangoDB container

```bash
docker stop arangodb && docker rm arangodb
```

### Open ArangoDB Web UI

Open in browser:

```
http://localhost:8529
```

Login with `root` / `openSesame`, then select database `memory_poc`.

---

## 2. Project Setup

### Create virtual environment and install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Set up environment variables

```bash
cp .env.example .env
```

The `.env` file is already pre-filled with:

```env
ARANGO_HOST=http://localhost:8529
ARANGO_DB=memory_poc
ARANGO_USERNAME=root
ARANGO_PASSWORD=openSesame

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5-coder:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

MEMORY_THRESHOLD=0.35
```

### Create ArangoDB collections and indexes

Run once before starting the server for the first time:

```bash
.venv/bin/python db/setup_db.py
```

Expected output:

```
[=] Database already exists: memory_poc
[+] Created collection: episodic_memories
[+] Created collection: semantic_memories
[+] Created collection: procedural_memories
...
[OK] Setup complete.
```

### Run Phase 2 schema migration

Run once after upgrading to Phase 2 (adds importance, confidence, temporal fields to existing memories):

```bash
.venv/bin/python migrations/phase_2_schema_migration.py
```

Expected output:

```
[+] Created collection: memory_merge_logs
[+] episodic_memories: migrated N documents
[OK] Phase 2 migration complete.
```

---

## 3. Running the Server

### Start with auto-reload (development)

```bash
.venv/bin/uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Start without reload (stable)

```bash
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

### Check server is running

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status": "ok"}
```

### Interactive API docs (Swagger UI)

Open in browser:

```
http://localhost:8000/docs
```

---

## 4. Demo — Add Memories

### Add episodic memory (event with timestamp)

```bash
curl -s -X POST http://localhost:8000/memory/add \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "text": "Customer ABC reported repeated payment gateway failures on Monday.",
    "source": "ticketing",
    "metadata": {
      "source_document_id": "ticket_001",
      "event_timestamp": "2026-06-07T10:00:00Z"
    }
  }' | python3 -m json.tool
```

Expected response:

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
    "entities": [
        {"name": "ABC", "type": "customer"},
        {"name": "payment gateway", "type": "product"}
    ]
}
```

### Add semantic memory (stable fact)

```bash
curl -s -X POST http://localhost:8000/memory/add \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "text": "Customer ABC uses Payment Gateway X for checkout transactions.",
    "source": "crm",
    "metadata": {
      "source_document_id": "crm_001"
    }
  }' | python3 -m json.tool
```

### Add procedural memory (workflow / SOP)

```bash
curl -s -X POST http://localhost:8000/memory/add \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "text": "For payment gateway failure, check transaction logs, retry queue, and notify finance operations.",
    "source": "docs",
    "metadata": {
      "source_document_id": "runbook_001"
    }
  }' | python3 -m json.tool
```

---

## 5. Demo — Consolidation (Deduplication)

Send a near-duplicate of the episodic memory added above:

```bash
curl -s -X POST http://localhost:8000/memory/add \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "text": "Customer ABC again reported gateway payment failure.",
    "source": "ticketing",
    "metadata": {
      "source_document_id": "ticket_002",
      "event_timestamp": "2026-06-07T11:00:00Z"
    }
  }' | python3 -m json.tool
```

Expected — merged instead of stored:

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

---

## 6. Demo — Retrieve Memory

```bash
curl -s -X POST http://localhost:8000/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "query": "What payment issues did Customer ABC face?",
    "top_k": 5
  }' | python3 -m json.tool
```

Expected — all three memory types returned with quality scores and citations:

```json
{
    "query": "What payment issues did Customer ABC face?",
    "context": {
        "facts": [{
            "memory_id": "...",
            "text": "Customer ABC uses Payment Gateway X for checkout transactions.",
            "score": 0.4822,
            "importance_score": 0.59,
            "confidence_score": 0.71,
            "quality_score": 0.638,
            "valid_from": "...",
            "valid_to": null
        }],
        "events": [{
            "memory_id": "...",
            "text": "Customer ABC reported repeated payment gateway failures on Monday.",
            "score": 0.5475,
            "importance_score": 0.55,
            "confidence_score": 0.775,
            "quality_score": 0.64,
            "valid_from": "2026-06-07T10:00:00Z",
            "valid_to": "2026-06-07T10:00:00Z"
        }],
        "procedures": [{
            "memory_id": "...",
            "text": "For payment gateway failure, check transaction logs...",
            "score": 0.4754,
            "importance_score": 0.57,
            "confidence_score": 0.66,
            "quality_score": 0.606,
            "valid_from": "...",
            "valid_to": null
        }],
        "citations": [
            {"memory_id": "...", "source_system": "ticketing", "source_document_id": "ticket_001", "confidence_score": 0.775},
            {"memory_id": "...", "source_system": "crm",       "source_document_id": "crm_001",    "confidence_score": 0.71},
            {"memory_id": "...", "source_system": "docs",      "source_document_id": "runbook_001","confidence_score": 0.66}
        ]
    }
}
```

---

## 7. Run Tests

### Unit tests only (no ArangoDB or Ollama needed)

```bash
.venv/bin/python -m pytest tests/test_importance_scorer.py tests/test_confidence_scorer.py tests/test_temporal_memory.py -v
```

### All integration tests (requires ArangoDB + Ollama running)

```bash
.venv/bin/python -m pytest tests/ -v
```

### Single test file

```bash
.venv/bin/python -m pytest tests/test_consolidation.py -v
```

### With output printed (useful for debugging)

```bash
.venv/bin/python -m pytest tests/ -v -s
```

---

## 8. ArangoDB AQL Queries (Direct Inspection)

Run these in the ArangoDB Web UI → Query Editor, or via arangosh.

### Count all stored memories

```aql
RETURN {
  episodic  : LENGTH(episodic_memories),
  semantic  : LENGTH(semantic_memories),
  procedural: LENGTH(procedural_memories),
  events    : LENGTH(memory_events),
  entities  : LENGTH(entities),
  merges    : LENGTH(memory_merge_logs)
}
```

### View all episodic memories for a tenant

```aql
FOR doc IN episodic_memories
  FILTER doc.tenant_id == "default"
  RETURN {
    id             : doc._key,
    text           : doc.text,
    importance     : doc.importance_score,
    confidence     : doc.confidence_score,
    quality        : doc.quality_score,
    duplicate_count: doc.duplicate_count,
    valid_from     : doc.valid_from,
    valid_to       : doc.valid_to
  }
```

### View all merge logs

```aql
FOR log IN memory_merge_logs
  SORT log.created_at DESC
  RETURN log
```

### View graph: which entities does a memory mention?

```aql
LET memory_id = "episodic_memories/YOUR_MEMORY_KEY_HERE"
FOR v, e IN 1..1 OUTBOUND memory_id memory_mentions_entity
  RETURN {entity: v.name, type: v.entity_type}
```

### View graph: which memories mention a given entity?

```aql
LET entity_id = "entities/default_abc"
FOR v, e IN 1..1 INBOUND entity_id memory_mentions_entity
  RETURN {memory: v._key, type: v.type, text: v.text}
```

### View provenance for a memory

```aql
LET memory_id = "episodic_memories/YOUR_MEMORY_KEY_HERE"
FOR v, e IN 1..1 OUTBOUND memory_id memory_has_provenance
  RETURN v
```

### Find memories by source system

```aql
FOR doc IN episodic_memories
  FILTER doc.source == "ticketing"
  SORT doc.quality_score DESC
  RETURN {id: doc._key, text: doc.text, quality: doc.quality_score}
```

### Find temporally bounded memories (what was true on a specific date)

```aql
LET target_date = "2026-06-07T10:00:00Z"
FOR doc IN episodic_memories
  FILTER doc.valid_from <= target_date
  FILTER doc.valid_to == null OR doc.valid_to >= target_date
  RETURN {id: doc._key, text: doc.text, valid_from: doc.valid_from, valid_to: doc.valid_to}
```

---

## 9. Ollama Commands

### Check Ollama is running

```bash
curl http://localhost:11434/api/tags
```

### List available models

```bash
curl http://localhost:11434/api/tags | python3 -m json.tool
```

### Pull models if not already available

```bash
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

### Test embedding generation manually

```bash
curl -s -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"nomic-embed-text","prompt":"Customer ABC payment gateway failure"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Embedding dims:', len(d['embedding']))"
```

Expected:

```
Embedding dims: 768
```

### Test LLM classification manually

```bash
curl -s -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role":"user","content":"Classify this as episodic, semantic, or procedural. Return JSON only: {\"type\":\"...\",\"reason\":\"...\"}. Text: Customer ABC reported a payment failure."}],
    "stream": false
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['message']['content'])"
```

---

## 10. Quick Full Demo Script

Paste this block to run the entire demo end-to-end in one shot:

```bash
TENANT="quickdemo_$(date +%s)"

echo "=== Adding 3 memories ==="
curl -s -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"text\":\"Customer ABC reported repeated payment gateway failures on Monday.\",\"source\":\"ticketing\",\"metadata\":{\"source_document_id\":\"ticket_001\",\"event_timestamp\":\"2026-06-07T10:00:00Z\"}}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('1:', d['status'], d.get('memory_type',''), '| importance:', d.get('importance_score'))"

curl -s -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"text\":\"Customer ABC uses Payment Gateway X for checkout transactions.\",\"source\":\"crm\",\"metadata\":{\"source_document_id\":\"crm_001\"}}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('2:', d['status'], d.get('memory_type',''), '| importance:', d.get('importance_score'))"

curl -s -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"text\":\"For payment gateway failure, check transaction logs, retry queue, and notify finance operations.\",\"source\":\"docs\",\"metadata\":{\"source_document_id\":\"runbook_001\"}}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('3:', d['status'], d.get('memory_type',''), '| importance:', d.get('importance_score'))"

echo ""
echo "=== Testing consolidation (near-duplicate) ==="
curl -s -X POST http://localhost:8000/memory/add -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"text\":\"Customer ABC again reported gateway payment failure.\",\"source\":\"ticketing\",\"metadata\":{\"source_document_id\":\"ticket_002\"}}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('4:', d['status'], '| consolidation_score:', d.get('consolidation_score'), '| duplicate_count:', d.get('duplicate_count'))"

echo ""
echo "=== Retrieving memories ==="
curl -s -X POST http://localhost:8000/memory/retrieve -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"query\":\"What payment issues did Customer ABC face?\",\"top_k\":5}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
ctx = d['context']
print('Facts:',      len(ctx['facts']),      '|', [f['text'][:50] for f in ctx['facts']])
print('Events:',     len(ctx['events']),     '|', [f['text'][:50] for f in ctx['events']])
print('Procedures:', len(ctx['procedures']), '|', [f['text'][:50] for f in ctx['procedures']])
print('Citations:',  len(ctx['citations']))
"
```

---

## 11. Troubleshooting

| Problem | Check |
|---|---|
| `Connection refused` on port 8529 | Run `docker ps` — is the ArangoDB container running? |
| `Connection refused` on port 11434 | Is Ollama running? Run `ollama serve` |
| `model not found` error | Run `ollama pull qwen2.5-coder:7b && ollama pull nomic-embed-text` |
| `Collection not found` error | Run `python db/setup_db.py` |
| `importance_score: null` in old memories | Run `python migrations/phase_2_schema_migration.py` |
| All memories return `not_stored` | Lower `MEMORY_THRESHOLD` in `.env` (currently `0.35`) |
| Near-duplicates not merging | Lower `CONSOLIDATION_THRESHOLD` in `services/consolidation_service.py` (currently `0.80`) |
| Slow responses | LLM calls are synchronous — normal for local Ollama with 7B model |
