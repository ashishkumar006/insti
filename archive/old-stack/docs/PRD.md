# DOCUMENT 1 — Product Requirements Document (PRD)

## CampusGuide — Campus Document Retrieval & QA Platform

> **Status:** Draft v1 (pending approval)
> **Assumptions flagged** where requirements were ambiguous. Deployment target is **TBD**; this PRD assumes an on-prem/intranet deployment with a cloud-ready architecture path.

---

## 1. Product Overview

### What the product is
CampusGuide is a retrieval-augmented question-answering platform for campus documents. It indexes official and semi-official text documents (currently PDFs converted to `.txt` and native `.txt` files), retrieves the most relevant passages using hybrid search, and generates a grounded, cited answer via an LLM.

The product exposes **one backend** with **two surfaces**:
1. **Public Student Search** (`/frontend/`) — a clean, non-technical search interface for students. No "AI" or internal jargon.
2. **Internal Admin Dashboard** (`/static/` or `/`) — an operator console for indexing documents, deleting chunks, viewing logs, and monitoring the gateway.

### The problem it solves
Campus rules, penalties, charters, and guides are scattered across long PDFs that students rarely read. Finding a specific answer (e.g., "what is the fine for tobacco possession?") requires manually searching dense documents. The product turns this into a single natural-language question.

### Why the product is needed
- Documents are long, unstructured, and hard to navigate.
- Students need quick, trustworthy answers with source citations.
- Manual lookup wastes time and leads to misinformation from peers.

### Target users
| User type | Description |
|-----------|-------------|
| Student (primary) | Browses/asks questions on the public surface. No technical knowledge assumed. |
| Content operator (admin) | Indexes new documents, deletes stale chunks, monitors ingestion via the dashboard. |
| (Future) Content owner | Department representative who uploads/owns specific documents. |

### Core value proposition
"Ask a question. Get a cited answer from the official documents — in seconds."

### Key features
- **Hybrid retrieval**: dense (semantic) + sparse (keyword) search fused for accuracy.
- **Grounded answers**: LLM answers only from retrieved chunks, with inline `[chunk_id]` citations.
- **Document indexing**: operator uploads/triggers indexing of `.txt`/PDF-derived text.
- **Chunk management**: delete indexed chunks for a document without full rebuild.
- **Live logs**: operator sees indexing progress and errors.
- **Provider abstraction**: LLM/embedding served via a gateway with failover.

### Product scope (MVP)
- Plain-text and PDF-derived `.txt` documents in a `data/` folder.
- Single-language (English) content.
- Open access (no authentication) — see constraints.
- One backend, two UIs.

### Out of scope (MVP)
- User accounts / authentication (explicitly deferred per requirements).
- Web-link / live URL fetching (mentioned by user; deferred — see assumptions).
- Multi-language (Tamil/English) support.
- Structured data (tables, forms, databases) beyond text extraction.
- Real-time collaborative editing of documents.
- Public cloud multi-tenant hosting (architecture should allow it, but not built now).

---

## 2. Goals & Requirements

### Primary product goals
- G1: Let any student get a cited answer to a campus-document question in < 5 seconds (p95).
- G2: Ensure answers are grounded in retrieved documents (no hallucination).
- G3: Let operators keep the index current with minimal effort.

### User goals
- UG1 (Student): Find the answer without reading the source PDF.
- UG2 (Student): Trust the answer because it shows sources.
- UG3 (Operator): Index a new document in one action and see it succeed/fail.

### Business goals
- BG1: Reduce repetitive student queries to admin offices.
- BG2: Improve information accessibility (inclusion/equity goal for the institute).

### Functional requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Student can submit a natural-language query and receive a cited answer | Must |
| FR-2 | System retrieves top-k relevant chunks via hybrid search | Must |
| FR-3 | Answer cites source chunk IDs inline | Must |
| FR-4 | Operator can trigger indexing of a document in `data/` | Must |
| FR-5 | Operator can delete all indexed chunks for a document | Must |
| FR-6 | Operator can view live indexing logs | Must |
| FR-7 | System shows document list with indexed/non-indexed status | Must |
| FR-8 | Gateway fails over between providers on error | Should |
| FR-9 | Operator can choose LLM provider per query (auto/gemini/ollama) | Should |
| FR-10 | Query history / recent searches | Nice-to-have |
| FR-11 | Web-link ingestion (fetch URL → index) | Nice-to-have (deferred) |

### Non-functional requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-1 | p95 answer latency < 5s for indexed corpus | Must |
| NFR-2 | Answer groundedness: no answer without retrieved context | Must |
| NFR-3 | Indexing of a 50k-char doc completes < 2 min | Should |
| NFR-4 | System degrades gracefully if LLM gateway is down (clear error) | Must |
| NFR-5 | Concurrent users: designed for campus-intranet scale (hundreds) | Should |

### User roles and permissions
| Role | Can search | Can index | Can delete chunks | Can view logs |
|------|-----------|-----------|------------------|---------------|
| Student (public) | ✅ | ❌ | ❌ | ❌ |
| Operator (admin) | ✅ | ✅ | ✅ | ✅ |

> **Assumption A1:** No authentication in MVP. The admin dashboard is reachable on the same network; access control is out of scope. If deployment becomes public, auth (FR-deferred) becomes mandatory.

### Feature-by-feature requirements
- **Search (FR-1..3):** input box, top-k selector, submit; returns answer + sources; empty/error states handled.
- **Indexing (FR-4..7):** document table lists files in `data/`; "Index Now"/"Re-index" buttons; status pill; logs stream.
- **Chunk delete (FR-5):** per-document "Delete Chunks" with confirmation; removes from chunks.json, dense index, sparse index.

### Constraints and assumptions
- **C1:** Embedding model is `nomic-embed-text` (768-dim) via local Ollama; changing it invalidates the FAISS index.
- **C2:** LLM served through `llm_gatewayV9` (port 8109) with provider failover.
- **A1:** No auth in MVP (above).
- **A2:** Deployment target TBD — architecture assumes on-prem/intranet, cloud-ready.
- **A3:** Web-link fetching deferred; current pipeline is file-only.

### Dependencies
- Ollama running locally with `nomic-embed-text` and an LLM model.
- `llm_gatewayV9` service reachable at configured URL.
- Python 3.8+ runtime.
- PDF extraction tooling (pdfplumber/PyPDF2) for onboarding documents.

### Priority summary
- **Must-have:** FR-1..7, NFR-1..2, NFR-4
- **Should-have:** FR-8..9, NFR-3, NFR-5
- **Nice-to-have:** FR-10..11

---

## 3. User Experience

### Student journey (public surface)
1. **Discover/access:** Opens `http://<host>/frontend/` (or root redirect).
2. **Onboarding:** None required. Sees hero + search box.
3. **Core workflow:**
   - Types question → selects top-k → clicks Search.
   - Sees "Searching..." then answer with `[chunk_id]` citations and a sources list.
4. **Success state:** Answer rendered with sources.
5. **Error state:** "Server error" or "provided documents do not contain information" if no match.
6. **Empty state:** "Enter a query and press Search."
7. **Edge cases:**
   - Empty query → no action.
   - Very long query → still embedded; retrieval may be noisy.
   - No indexed docs → honest "not found" answer.

### Operator journey (admin dashboard)
1. **Access:** Opens `/` (dashboard).
2. **Onboarding:** None; assumes trusted operator.
3. **Core workflow:**
   - Views document table with status.
   - Clicks "Index Now" → overlay shows "PROCESSING" → logs stream → "INDEXED".
   - Clicks "Delete Chunks" → confirm → chunks removed → table updates.
4. **Success/error:** Logs show OK/ERR; errors surface in red.
5. **Edge cases:**
   - Indexing already running → blocked with alert.
   - File not found → 404 error shown.
   - Gateway down → indexing fails; clear error in logs.

### UX principles for designers
- Public surface: no technical/AI terminology; friendly, campus-branded.
- Admin surface: dense, operational, log-centric.
- Consistent terminology: "document", "chunk", "index", "source".

---

## 4. Success Metrics

| Metric | What | Why | Calc | Success |
|--------|------|-----|------|---------|
| Activation | % of visitors who submit ≥1 query | Adoption | queries / unique visitors | > 40% |
| Answer groundedness | % answers with ≥1 source citation | Trust | cited answers / total | > 95% |
| Retrieval relevance | Top-1 chunk contains answer (sampled) | Quality | human audit | > 80% |
| p95 latency | Query→answer time | UX | percentile of response times | < 5s |
| Index freshness | Docs indexed within 24h of upload | Currency | indexed / new docs | 100% |
| Error rate | % queries returning server error | Reliability | 5xx / total | < 2% |
| Operator efficiency | Time to index a doc | Ops | avg duration | < 2 min |

> **Note:** Analytics instrumentation is a should-have; MVP can use server logs initially.
