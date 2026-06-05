# Arango Memory POC (Hybrid Mem0 + Graphiti Inspired)

A lightweight, local-first **Agentic Memory system** using ArangoDB Community Edition, Ollama, and FastAPI.

The purpose of this POC is to demonstrate how **ArangoDB** acts as a unified memory layer, combining Document Storage, Graph Storage, Vector Search, and BM25 Search within a single database engine.

---

## High-Level Architecture

### Write Pipeline (Ingestion Path)
When a message is posted to `/memory/add`, the system processes it through a synchronous pipeline:

```
[ User Message ] ──> Store Raw Event (Document) ──> memory_events
       │
       ├───> Extract Entities & Relationships (LLM: qwen2.5-coder:7b)
       │         │
       │         └───> Map "user" node references to actual user_id
       │         └───> Normalize keys to lower_snake_case
       │         └───> Upserts into Knowledge Graph ──> entities (nodes) & relations (edges)
       │
       └───> Generate text embedding (Vector: nomic-embed-text)
                 │
                 └───> Link to parent memory event ID ──> memory_embeddings
```

### Read Pipeline (Retrieval Path)
When a query is searched via `/memory/search`, three retrieval strategies run and merge:

```
                        [ Search Query ]
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Semantic     │         │ Graph        │         │ BM25         │
│ Search       │         │ Search       │         │ Search       │
├──────────────┤         ├──────────────┤         ├──────────────┤
│ Cosine sim   │         │ 1-2 hop AQL  │         │ Stemmed search│
│ over vector  │         │ outbound     │         │ via analyzer │
│ embeddings   │         │ traversal    │         │ memory_view  │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                │
                                ▼
                       ┌────────────────┐
                       │  Merge Router  │
                       ├────────────────┤
                       │ Deduplicates   │
                       │ by text /      │
                       │ entity name.   │
                       └────────┬───────┘
                                │
                                ▼
                      [ Unified Context ]
```

---

## DB Collections & Schemas

The `memory_poc` database contains four collections and one full-text search view:

| Collection / View | Type | Fields / Configuration | Purpose |
| :--- | :--- | :--- | :--- |
| **`memory_events`** | Document | `user_id`, `message`, `timestamp` | Append-only raw logs |
| **`memory_embeddings`** | Document | `memory_id`, `user_id`, `text`, `embedding` (768-dim) | Semantic vectors |
| **`entities`** | Document | `name`, `type` | Knowledge Graph nodes |
| **`relations`** | Edge | `_from`, `_to`, `relation` | Knowledge Graph edges |
| **`memory_view`** | ArangoSearch | Indexed field: `message` (Analyzer: `text_en`) | BM25 full-text query |

---

## Prerequisites

1. **ArangoDB Community Edition** running on `http://localhost:8529`
2. **Ollama** running on `http://localhost:11434`
3. Download the LLM and Embedding models:
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama pull nomic-embed-text
   ```

---

## Quick Start

```bash
# 1. Navigate to the project directory
cd memory_poc/

# 2. Set up virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environmental variables (if customization is needed)
# Default variables:
#   ARANGO_HOST=http://localhost:8529
#   ARANGO_DB=memory_poc
#   ARANGO_PASSWORD=openSesame
cat .env

# 4. Start the FastAPI App
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
On startup, the lifespan hooks will automatically create the database, collections, and the ArangoSearch view.

---

## How to Test

We have provided two integration test scripts:

### 1. Simple Test (`test_poc.py`)
Inserts a single message and validates retrieval:
```bash
python test_poc.py
```

### 2. Complex Scenario Test (`test_complex.py`)
Simulates a multi-turn narrative containing project details, ticket IDs, team members, and release dates:
```bash
python test_complex.py
```

---

## Web UI Database Inspection

To visually inspect the data and the dynamic knowledge graph:
1. Open **[http://localhost:8529](http://localhost:8529)** in your browser.
2. Log in using `root` and password `openSesame`.
3. **Crucial:** In the top-right corner, switch the database dropdown from `_system` to **`memory_poc`**.
4. Browse individual records in the **Collections** tab.
5. To visualize the graph, go to the **Queries** tab, execute:
   ```aql
   FOR e IN relations RETURN e
   ```
   and click the **Graph** view button in the query results pane.

---

## Project Structure

```
memory_poc/
├── app.py                      # FastAPI App definition & Endpoint Routes
├── config.py                   # Environment Configuration loader
├── requirements.txt            # Python dependencies
├── .env                        # Configuration defaults
├── README.md                   # System Architecture & Documentation
│
├── db/                         # Database Lifecycle layer
│   ├── arango_client.py        # Connection pooling client
│   ├── setup_collections.py    # Schema initialization logic
│   └── setup_views.py          # Fulltext index / View configuration
│
├── models/                     # Data contracts layer
│   └── schemas.py              # Request / Response Pydantic models
│
├── prompts/                    # LLM Prompt Templates
│   └── entity_extraction.txt   # Graph Extraction rules & constraints
│
├── services/                   # Business Logic Layer
│   ├── memory_service.py       # Write Pipeline Coordinator
│   ├── extraction_service.py   # Ollama JSON extractor wrapper
│   ├── graph_service.py        # Graph upserting & AQL traversal
│   ├── embedding_service.py    # Vector generator wrapper
│   └── retrieval_service.py    # Parallel Search Runner & Merger
│
├── test_poc.py                 # Basic functional tests
└── test_complex.py             # Multi-turn developer scenario simulator
```
