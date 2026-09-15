# DOCUMENT 3 — Implementation Plan

## CampusGuide — Campus Document Retrieval & QA Platform

> Phases build on the **existing working codebase** (already implements MVP). Plan focuses on hardening, completing should-haves, and preparing for deferred features.

---

## 1. Development Phases

| Phase | Focus | Exit criteria |
|-------|-------|---------------|
| 1 — Foundation | Repo, env, services, storage | Gateway + backend run reliably; Ollama on 127.0.0.1 |
| 2 — Core Features | Search, indexing, delete, logs | All FR-1..7 working + tested |
| 3 — Secondary | Provider select, failover, history | FR-8..9 done |
| 4 — Testing & Hardening | Unit/integration/security/perf | Coverage + load test pass |
| 5 — Deployment | Infra, env, backup, rollback | Reproducible deploy |
| 6 — Launch & Post | Beta, feedback, roadmap | Metrics live |

---

## 2. Feature Breakdown

### Phase 1 — Foundation
**Tasks:**
- Pin Ollama to `127.0.0.1` in gateway `.env` (done — fixes `getaddrinfo`).
- Document `.env` contract (root + gateway).
- Add `requirements.txt` / venv setup for root project.
- Add startup script (`run.sh`) launching gateway + backend.

**Definition of done:** `python main.py serve` + gateway up; `/ask` returns cited answer.

### Phase 2 — Core Features (MVP)
**Search (FR-1..3):**
- Backend: `/ask` already implemented; add input sanitization + timeout.
- Frontend: public search box + answer render + source list.
- Test: 20 golden queries (penalties, contacts, yearbook).

**Indexing (FR-4..7):**
- Backend: `/api/index/{f}`, `/api/logs`, `/api/documents` done.
- Frontend: document table, status pills, Index/Re-index buttons, log stream.
- Test: index each PDF-derived txt; verify chunk counts.

**Chunk delete (FR-5):**
- Backend: `/api/index/{f}/delete` done (chunks.json + FAISS rebuild + SQLite).
- Frontend: Delete Chunks button + confirm.
- Test: delete → re-index → verify consistency.

### Phase 3 — Secondary (Should-have)
- FR-8: Gateway failover verified across providers.
- FR-9: Provider dropdown wired to `/ask` (already in UI; confirm backend honors `provider`).
- FR-10: Query history in localStorage (nice-to-have).

### Phase 4 — Testing & Hardening
- Unit: `chunk()`, `_rrf_fuse()`, `DenseStore`, `SparseStore`.
- Integration: `/ask` against indexed corpus; delete-then-search.
- API: contract tests for all endpoints.
- Security: filename traversal test; gateway-down handling.
- Performance: p95 latency on 100-query sample (NFR-1).

### Phase 5 — Deployment
- Infra: on-prem server (A2); docker-compose optional.
- Env: document all vars; secrets via env file (not committed).
- Backup: `data/` + nightly `indexes/` snapshot.
- Rollback: keep previous `indexes/` backup; restart script.

### Phase 6 — Launch & Post
- Beta: 10–20 students; collect feedback.
- Analytics: add minimal event log (query, latency, cited).
- Roadmap: heading-aware chunking, web-link ingestion (A3), auth (A1).

---

## 3. Task Dependencies
```
P1 (env/services)
 └─ P2 Search ─┐
 └─ P2 Indexing ├─ P2 Delete ─┐
                              └─ P3 Provider/Failover
                                     └─ P4 Testing
                                            └─ P5 Deploy
                                                   └─ P6 Launch
```

---

## 4. Testing Strategy
- **Unit:** pure functions (chunking, fusion, stores).
- **Integration:** end-to-end `/ask` against indexed corpus.
- **API:** schema + error response tests.
- **UI:** manual + snapshot of public/admin flows.
- **Security:** path traversal, missing gateway.
- **Perf:** p95 on representative query set.

---

## 5. Deployment Plan
- Single host (intranet). Gateway :8109, backend :8200.
- Process manager (or `run.sh` with nohup).
- Env files outside VCS.
- Backup cron: `data/` + `indexes/`.
- Rollback: restore `indexes/`, restart.

---

## 6. Launch Plan
- Internal beta → feedback loop → metric dashboard → iterate.

---

## 7. Future Roadmap
1. Heading-aware chunking (structure preservation).
2. Web-link / URL ingestion (A3).
3. Authentication & roles (A1).
4. Multi-language (Tamil + English).
5. Cloud deployment path (A2).
6. Analytics & query insights.
