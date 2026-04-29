# Chatbot Solution Delivery Phases

This file tracks project phases, current status, and the next execution plan.

## Completed Phases

### Phase 1.0 - Foundation MVP
- Repo scaffold with `backend`, `frontend`, `docker`, `scripts`
- FastAPI backend + React frontend baseline
- Core endpoints: `/health`, `/api/chat`, `/api/ingest`
- ChromaDB + embedding retrieval pipeline
- Groq LLM integration with SSE response format

### Phase 1.1 - Chat Quality & Safety Basics
- Confidence-based handoff signal
- Streaming token events in `/api/chat`
- Feedback API endpoint and persistence
- Basic PII scrubbing flow before LLM call

### Phase 1.2 - Integration/Auth Skeleton
- Session bootstrap endpoints (`/api/auth/session`)
- Integration stubs for TDX + PureChat
- Ingestion URL allowlist and HTTPS guardrails

### Phase 1.3 - Integration Payload Progress
- TDX live-call path structure (config-driven)
- PureChat handoff payload shaping
- Frontend feedback actions wired to backend

### Phase 1.4 - Role Enforcement & History
- Entra-claims mapping endpoint skeleton
- Server-side role enforcement in chat flow
- Chat history persistence in JSONL

### Phase 1.5 - Hardening & Observability
- Request ID middleware (`x-request-id`)
- Structured JSON request logging
- Per-IP rate limiting
- Verification scripts and smoke checks

### Phase 1.6 - Test Automation
- Backend pytest API suite
- One-command verification pipeline script
- Frontend runtime resiliency improvements

---

## Active Phase

### Phase 5 - Production Readiness & Go-Live (In Progress)
**Goal:** Deployable, monitorable, and supportable in enterprise.

#### Completed in this iteration
- Added production Docker stack (`docker-compose.prod.yml`): built frontend (nginx), backend image, named Chroma volume, healthchecks, restart policy
- Added `frontend/Dockerfile` (multi-stage build) and `frontend/nginx.conf` for static SPA hosting
- Added `docs/RUNBOOK.md` with prod compose usage, Chroma backup/restore examples, and verification pointer
- Documented prod compose and CORS/build-arg notes in `README.md`

#### Next up
- Wire baseline observability targets (dashboards for latency, errors, handoff rate) to your hosting platform
- Load test against pilot targets; record results in go-live checklist
- Optional: reverse-proxy `/api` same-origin to simplify CORS in locked-down environments

---

### Phase 4 - RAG Quality, Safety, Governance (Substantially complete)
**Goal:** Improve answer quality and reduce hallucination risk.

#### Completed in this iteration
- Added post-generation grounding enforcement that removes URLs not present in retrieved sources
- Added handoff escalation trigger when grounding policy violations are detected
- Added tests for grounding policy behavior (allowed retrieved link, blocked ungrounded link)
- Documented grounding/citation guardrails in `README.md`
- Expanded PII/secret detection patterns (email, phone, API token formats) in scrubbing pipeline
- Added tests validating new PII/secret redaction coverage
- Added bulk DOCX ingestion support (`docx_paths`) with configurable batch limit for high-volume imports (e.g., 750 files)
- Added DOCX ingestion tests (success path + batch limit enforcement)
- Added allowed-domain website crawl ingestion (`crawl`, `max_pages`) for KB-scale HTML imports (e.g., 715-750 articles)
- Added crawl limit enforcement test for controlled large-ingestion operations
- Added retrieval quality metrics in chat SSE payload (`quality_metrics`) for handoff/fallback threshold tuning
- Added quality-evaluator tests covering low-confidence and handoff trigger behavior
- Added retrieval reranking (semantic score + query keyword overlap + length penalty heuristics)
- Added reranking tests for relevance promotion and noisy-short-chunk penalty
- Added `scripts/eval-retrieval.ps1` to evaluate retrieval quality metrics across a query set for rerank tuning
- Added confidence calibration (`CONFIDENCE_SCORE_SCALE`) so retrieval score ranges align with handoff thresholds
- Re-ran retrieval evaluation after calibration to validate improved confidence behavior
- Added labeled retrieval evaluation support (`expected_source_contains`) with top-1 source hit-rate reporting
- Added configurable rerank weights and URL-token signal for relevance tuning
- Added rerank test coverage for source-url keyword boosts
- Added `scripts/sweep-rerank.ps1` for grid-search weight tuning against labeled retrieval hit-rate
- Added `scripts/bootstrap-eval-queries.ps1` to generate labeled eval query seeds from live KB pages
- Updated eval/sweep scoring to prefer exact `reference_url` path matching for more reliable hit-rate measurement
- Operational: crawl-ingested OU support KB (seed `https://support.oakland.edu`, up to 750 pages), rebuilt `eval-queries.generated.json` from Chroma, ran eval + sweep; applied best sweep rerank defaults (`RERANK_*` in config)

#### Optional follow-ups
- Re-run `sweep-rerank.ps1` whenever the labeled OU query set grows materially or KB content shifts
- Tune chunking or HTML extraction if specific KB pages produce weak chunks

---

## Remaining work

### Phase 5 (continued)
- Monitoring dashboards (latency, errors, handoff rate) and alerting on your hosting stack
- Load/performance test against pilot targets; capture a short go-live checklist
- **Done:** production Docker profile (`docker-compose.prod.yml`, frontend nginx image), backup/restore notes (`docs/RUNBOOK.md`)

### Release acceptance (both phases)
- Retrieval quality and safety behaviors remain acceptable on your labeled eval set
- No invented links; low-confidence paths trigger handoff consistently
- `scripts/verify-all.ps1` passes before release

---

## Tomorrow Kickoff Plan

1. Deploy `docker-compose.prod.yml` to a staging host; validate CORS and `VITE_API_BASE_URL`
2. Hook structured logs / metrics into dashboards (latency p95, 5xx rate, handoff rate)
3. Run load test at pilot concurrency; document results
4. Run `powershell -ExecutionPolicy Bypass -File .\scripts\verify-all.ps1`

