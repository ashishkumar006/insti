# DOCUMENT 2 — Technical Requirements Document (TRD)

## CampusGuide — Campus Document Retrieval & QA Platform

> **Traceability:** Every section maps to PRD requirements (IDs referenced).
> Assumes on-prem/intranet deployment (A2); cloud-ready where noted.

---

## 1. System Architecture

### Overall architecture
```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│ Public Frontend │     │   FastAPI Backend    │     │  LLM Gateway V9     │
│ (/frontend/)    │────▶│   (main.py :8200)    │────▶│  (port 8109)        │
│ Static HTML/JS  │     │  - /ask             │     │  - /v1/chat         │
└─────────────────┘     │  - /api/documents   │     │  - /v1/embed        │
                        │  - /api/index/{f}   │     └──────────┬──────────┘
┌─────────────────┐     │  - /api/index/{f}/  │                │
│ Admin Dashboard │────▶│    delete           │                │
│ (/ or /static/) │     │  - /api/logs        │     ┌──────────▼──────────┐
└─────────────────┘     └──────────┬───────────┘     │  Ollama (11434)     │
                                    │                  │  nomic-embed-text  │
                        ┌───────────▼───────────┐      │  LLM model         │
                        │   Retrieval Engine    │      └─────────────────────┘
                        │  - DenseStore (FAISS) │
                        │  - SparseStore (BM25) │
                        │  - HybridRetriever    │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │   Storage (indexes/)  │
                        │  dense.index/meta     │
                        │  sparse.db            │
                        │  chunks.json          │
                        └───────────────────────┘
```

### Components
- **Frontend:** Vanilla HTML/CSS/JS (no framework). Public + admin bundles.
- **Backend:** FastAPI (Python 3.8). Serves UI, APIs, orchestrates retrieval + agent.
- **Retrieval engine:** `HybridRetriever` = FAISS (dense) + BM25 (sparse) + RRF fusion.
- **Agent:** `run_agent` tool-calling loop; LLM calls `fetch_chunks`.
- **LLM Gateway:** Separate service (`llm_gatewayV9`) abstracting providers with failover.
- **Embeddings:** Local Ollama `nomic-embed-text` (768-dim).
- **Storage:** Filesystem under `indexes/` (FAISS, SQLite, JSON).

### Communication
- Browser → Backend: REST/JSON (fetch).
- Backend → Gateway: HTTP/JSON (`gateway_client.py`).
- Gateway → Ollama: HTTP (`/api/embeddings`, `/api/chat`).
- Backend → Index: direct file I/O (FAISS read/write, SQLite, JSON).

---

## 2. Backend Architecture

### Structure (modules)
| Module | Responsibility |
|--------|----------------|
| `main.py` | App, routes, lifecycle, job orchestration |
| `config.py` | Settings (env-driven) |
| `ingest.py` | Chunking strategy |
| `vector_store.py` | `DenseStore` (FAISS) |
| `sparse_store.py` | `SparseStore` (BM25/SQLite) |
| `retriever.py` | `HybridRetriever` + RRF |
| `agent.py` | `run_agent`, `FETCH_TOOL`, system prompt |
| `gateway_client.py` | HTTP client to LLM gateway |
| `index_document.py` | Indexing pipeline (chunk→embed→store) |

### Controllers / routes
- `GET /` → admin dashboard HTML
- `GET /api/documents` → list docs + status
- `POST /api/index/{filename}` → start background indexing job
- `POST /api/index/{filename}/delete` → delete doc chunks
- `GET /api/logs?job_id&since` → incremental log stream
- `POST /ask` → query → retrieve → answer

### Services
- **Indexing job** (`_run_index_job`): background thread; chunk → embed → store → save.
- **Log service**: in-memory deque + seq counter; polled by client.
- **Retrieval service**: `HybridRetriever.retrieve(query, top_k)`.

### Middleware / validation
- Pydantic request models (`AskRequest`, `IngestRequest`).
- File-type guard: only `.txt` in `data/`.
- 404/400/500 structured errors.

### Error handling
- Gateway down → `RuntimeError` → 500 with detail.
- Indexing failure → job status `error`, logged, surfaced in UI.

### Logging
- `_log(level, message, job_id)` → in-memory deque (last 2000).
- Printed to stdout for server-log analysis (NFR: observability).

### Background jobs
- Indexing runs in daemon threads; job state in `_jobs` dict.

---

## 3. Database Schema

> Current implementation uses files, not a relational DB. Schema below describes the **logical model** the files represent, to support all FRs and future migration.

### Entity: documents (logical — currently `data/` + `chunks.json`)
| Field | Type | Key | Notes |
|-------|------|-----|-------|
| name | string | PK | filename in `data/` |
| doc_id | string | — | equals name |
| size | int | — | bytes |
| indexed | bool | — | derived from chunk count |
| chunks | int | — | count in chunks.json |

### Entity: chunks (`chunks.json`)
| Field | Type | Key | Notes |
|-------|------|-----|-------|
| chunk_id | string | PK | `{doc_id}::chunk_{i:05d}` |
| doc_id | string | FK→documents | prefix |
| text | text | — | chunk content |
| char_count | int | — | length |

### Entity: dense_index (`dense.index` + `dense_meta.json`)
| Field | Type | Key | Notes |
|-------|------|-----|-------|
| id (vector) | float[768] | — | FAISS ntotal |
| chunk_id | string | PK (id_map) | order-aligned |
| text | text | — | text_map |

### Entity: sparse_index (`sparse.db`)
| Table `terms` | | | |
| term | string | PK(part) | stemmed |
| chunk_id | string | PK(part) | FK→chunks |
| tf | int | — | term frequency |
| Table `chunk_texts` | | | |
| chunk_id | string | PK | FK→chunks |
| text | text | — | |
| Table `meta` | | | |
| k | string | PK | N, avg_dl |

### Relationships
- documents **1—N** chunks (via `doc_id::` prefix).
- chunks **1—1** dense vector (by `chunk_id`).
- chunks **1—N** sparse terms (by `chunk_id`).

### Constraints
- `chunk_id` unique across stores.
- Delete must keep all three stores consistent (FR-5).

---

## 4. API Specification

### Documents
**GET /api/documents**
- Auth: none (open)
- Response: `{ documents: [{name, doc_id, size, size_human, indexed, indexing, chunks}], gateway_url, index_dir }`

**POST /api/index/{filename}**
- Body: none
- 200: `{ job_id, filename, status }`
- 404: file not found; 400: not .txt

**POST /api/index/{filename}/delete**
- 200: `{ status:"deleted", filename, deleted_chunks }`
- 404/400/500 as above

**GET /api/logs?job_id&since**
- 200: `{ logs:[{seq,level,message,ts,job_id}], last_seq, done, error, job_id }`

### Query
**POST /ask**
- Body: `{ query:string, top_k:int=10, max_turns:int=4, provider:string? }`
- 200: `{ query, answer, sources:[chunk_id], tool_calls_used:int }`
- 500: gateway/retrieval failure

---

## 5. Security & Reliability

### Authentication
- **None in MVP** (A1). Admin dashboard trusted on network.

### Authorization
- Role implied by surface (public vs admin path). No enforcement yet.

### Data protection
- Documents stay on server filesystem; no PII collected from queries (queries are text only).

### Input validation
- Pydantic models; filename sanitization via path join + existence check.

### Rate limiting
- Not in MVP; gateway has per-provider RPM state.

### API security
- No secrets in client; gateway URL server-side.

### Failure handling
- Gateway down → clear 500; UI shows error (NFR-4).
- Indexing crash → job marked error, logged.

### Backup
- `indexes/` is regenerable from `data/`; backup `data/` + periodic `indexes/` snapshot.

### Monitoring
- Server stdout logs; gateway `/v1/status` endpoint available.

---

## 6. Technical Decisions

| Decision | Choice | Why | Alternatives | Trade-off |
|----------|-------|-----|--------------|-----------|
| Retrieval | Hybrid (FAISS + BM25 + RRF) | Balances semantic + keyword; robust | Pure dense, pure sparse | More moving parts |
| Chunking | Paragraph/sentence, 750 tok, 75 overlap | Coherent chunks, simple | Fixed-size, heading-aware | No structure awareness (future) |
| Embeddings | Local Ollama nomic-embed-text 768 | Free, private, fast | Gemini API | Index tied to model |
| LLM access | Gateway with failover | Swap providers w/o code change | Direct calls | Extra service |
| Storage | Filesystem (FAISS/SQLite/JSON) | Zero infra, simple | Postgres/pgvector | Less concurrent-safe |
| Frontend | Vanilla JS | No build step, easy experiments | React/Vue | Less componentization |
| No auth | Open MVP | Speed to value | JWT/OAuth | Security risk if public |

> **Future:** heading-aware chunking, web-link ingestion (A3), auth (A1), cloud deploy (A2).
