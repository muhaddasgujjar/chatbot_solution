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

### Phase 4 - RAG Quality, Safety, Governance (In Progress)
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

#### Next up
- Run rerank sweep on expanded labeled OU query set and apply best-performing configuration

---

## Remaining Phases

### Phase 4 - RAG Quality, Safety, Governance
**Goal:** Improve answer quality and reduce hallucination risk.

#### Tasks
- Improve chunking, retrieval scoring, and ranking
- Add stricter grounding checks and citation policy
- Expand PII/secret detection rules
- Add answer quality metrics and fallback thresholds

#### Acceptance Criteria
- Better relevance on test question set
- No invented links in responses
- Unsafe/low-confidence replies consistently trigger handoff
- Quality tests and smoke tests pass

---

### Phase 5 - Production Readiness & Go-Live
**Goal:** Deployable, monitorable, and supportable in enterprise.

#### Tasks
- Production Docker profile and environment templates
- Monitoring dashboards (latency, errors, handoff rate)
- Backup/restore and runbook documentation
- Load/performance test and go-live checklist

#### Acceptance Criteria
- Production deployment runbook complete
- Observability and alerting active
- Performance targets met for pilot load
- Final verification suite passes before release

---

## Tomorrow Kickoff Plan

1. Continue **Phase 4** (RAG Quality, Safety, Governance) with retrieval/ranking improvements
2. Expand safety checks (PII/secret detection + grounding policy coverage)
3. Add quality metrics to quantify handoff/fallback decisions
4. Run:
   - `python -m pytest -q`
   - `powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1 -ApiBaseUrl http://127.0.0.1:8000`
   - `powershell -ExecutionPolicy Bypass -File .\scripts\verify-all.ps1`

