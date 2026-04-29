# OU Chatbot Solution (Phase 5 in progress)

Phase 1 provides a Groq-based RAG MVP with:
- FastAPI backend (`/api/chat`, `/api/ingest`)
- Chroma vector store persistence
- React frontend chat UI
- Phase 1.1/1.2 additions: streaming SSE, feedback API, auth session skeleton
- Phase 2 additions: TDX article normalization, TDX ticket create endpoint, PureChat handoff metadata
- Phase 3 additions: token validation middleware, role-based route protection, frontend bearer-token test path

## 1) Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set values in `.env`:
- `GROQ_API_KEY`
- optional `GROQ_MODEL`
- optional `ALLOWED_INGEST_DOMAINS`, `TDX_BASE_URL`, `TDX_API_TOKEN`, `PURECHAT_WIDGET_ID`
- optional `TDX_ARTICLES_PATH`, `TDX_TICKET_CREATE_PATH`, `TDX_TIMEOUT_SECONDS`, `TDX_MAX_RETRIES`
- optional auth settings: `AUTH_ENABLED`, `ENTRA_ISSUER`, `ENTRA_AUDIENCE`, `ENTRA_JWT_ALGORITHMS`, `ENTRA_TEST_HS256_SECRET`
- optional `CHAT_STORE_PATH` for chat transcript persistence
- optional `RATE_LIMIT_PER_MINUTE` for per-IP request throttling

Run backend:

```bash
uvicorn app.main:app --reload --port 8000
```

## 2) Ingest OU content

Example request:

```bash
curl -X POST http://localhost:8000/api/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"urls\": [\"https://oakland.edu/helpdesk\"], \"role_access\": \"all\"}"
```

DOCX batch ingestion example (supports large sets, e.g. 750 files):

```bash
curl -X POST http://localhost:8000/api/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"docx_paths\": [\"D:/data/docs/001.docx\", \"D:/data/docs/002.docx\"], \"role_access\": \"all\"}"
```

Notes:
- Request supports `urls` and `docx_paths` together or separately.
- Max DOCX files per request is controlled by `INGEST_MAX_DOCX_FILES` (default `1000`).
- DOCX paths are local to the backend runtime machine.

Website crawl ingestion example (for KB scrape-style training):

```bash
curl -X POST http://localhost:8000/api/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"urls\": [\"https://support.oakland.edu\"], \"crawl\": true, \"max_pages\": 750, \"role_access\": \"all\"}"
```

Crawler notes:
- Crawls only HTTPS links within `ALLOWED_INGEST_DOMAINS`.
- Max crawl pages per request is controlled by `INGEST_MAX_CRAWL_PAGES` (default `1000`).
- Designed to match KB-scale ingestion requirements (e.g. ~715-750 HTML articles).

## 3) Frontend setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open `http://localhost:5173`.

For local API endpoint override, edit `frontend/.env`:
- `VITE_API_BASE_URL=http://localhost:8000`
- `VITE_DEMO_USER_ID=demo-user`
- `VITE_DEMO_USER_ROLE=all`
- `VITE_DEMO_BEARER_TOKEN=<token>` (required when `AUTH_ENABLED=true`)

Quick start (auto port conflict handling):

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

What it does:
- picks free backend/frontend ports (starting from `8000` and `5173`)
- updates `frontend/.env` `VITE_API_BASE_URL` to match backend port
- starts backend and frontend in separate PowerShell windows

Preview ports/commands only (no process start):

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -DryRun
```

## 4) API endpoints

- `POST /api/auth/session` - initialize user role/session profile
- `GET /api/auth/session/{user_id}` - retrieve in-memory session
- `POST /api/auth/entra/claims` - map Entra-style claims to role session
- `POST /api/integrations/tdx/articles/search` - TDX article search (normalized response)
- `POST /api/integrations/tdx/tickets/create` - TDX ticket creation endpoint
- `POST /api/integrations/purechat/handoff` - PureChat handoff payload with transcript metadata
- `POST /api/feedback` - save Y/N feedback record
- Global middleware adds `x-request-id` and structured request logs

## 5) Auth and RBAC (Phase 3)

- Protected paths when `AUTH_ENABLED=true`:
  - `/api/chat`
  - `/api/integrations/*`
- Validation checks:
  - token signature (HS256 local mode and RS256 via JWKS)
  - issuer (`ENTRA_ISSUER`)
  - audience (`ENTRA_AUDIENCE`)
  - expiry (`exp`)
- Role enforcement:
  - `POST /api/integrations/tdx/tickets/create` allows `faculty` and `all`
  - student token requests to ticket creation are blocked with `403`
- Deterministic claim-to-role mapping policy:
  - precedence: `faculty` match > `student` match > fallback `all`
  - match sources: `department`, `jobTitle`, `groups`
  - mixed claims (e.g. student group + faculty title) resolve to `faculty`

Local auth test mode:
- Set `ENTRA_JWT_ALGORITHMS=HS256`
- Set `ENTRA_TEST_HS256_SECRET=<shared-secret>`
- Provide matching bearer token in frontend via `VITE_DEMO_BEARER_TOKEN`

Generate an HS256 test token:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\generate-hs256-token.ps1 -Secret "your-shared-secret" -Groups student
```

Use output token in `frontend/.env`:
- `VITE_DEMO_BEARER_TOKEN=<generated-token>`

Auto-write token to frontend env:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\generate-hs256-token.ps1 -Secret "your-shared-secret" -Groups student -WriteToFrontendEnv
```

RS256 mode (Entra-style):
- Set `ENTRA_JWT_ALGORITHMS=RS256`
- Set `ENTRA_JWKS_URL=<your Entra JWKS endpoint>`
- Set `ENTRA_ISSUER` and `ENTRA_AUDIENCE` to match issued tokens

## 6) RAG quality and grounding guardrails (Phase 4 start)

- Post-generation grounding policy removes links not present in retrieved sources.
- Detected grounding violations force `requires_handoff=true` in chat SSE end payload.
- This reduces hallucinated/external link leakage in generated answers.
- Expanded query scrubbing rules now redact:
  - SSN and card-like patterns
  - email addresses and phone numbers
  - secret-like tokens (Groq/GitHub/AWS key formats)
- Chat SSE end payload now includes `quality_metrics` for threshold tuning:
  - `chunk_count`, `source_count`
  - `avg_score`, `confidence`, `top_score`, `score_spread`
  - `low_confidence`
- Retrieval reranking now combines:
  - semantic similarity score from vector distance
  - keyword overlap with query terms
  - source URL token overlap with query terms
  - short/overly-long chunk penalties to reduce noisy context
- Confidence is calibrated via `CONFIDENCE_SCORE_SCALE` (default `2.5`) before threshold checks.
- Rerank behavior is configurable via:
  - `RERANK_SEMANTIC_WEIGHT`
  - `RERANK_KEYWORD_WEIGHT`
  - `RERANK_SOURCE_URL_WEIGHT`
  - `RERANK_SHORT_CHUNK_PENALTY`
  - `RERANK_LONG_CHUNK_PENALTY`

## 7) Integration API contracts (Phase 2)

### TDX article search

`POST /api/integrations/tdx/articles/search`

Request body:

```json
{
  "query": "reset password"
}
```

Response shape:

```json
{
  "enabled": true,
  "message": "TDX search completed.",
  "query": "reset password",
  "results": [
    {
      "id": "1234",
      "title": "Password reset guide",
      "summary": "Steps for resetting your OU password.",
      "url": "https://support.oakland.edu/kb/1234",
      "score": 0.92,
      "category": "account",
      "updated_at": "2026-04-01T12:30:00Z"
    }
  ],
  "attempts": 1,
  "error_type": null
}
```

### TDX ticket creation

`POST /api/integrations/tdx/tickets/create`

Request body:

```json
{
  "title": "Cannot access student portal",
  "description": "Login fails after MFA prompt with access denied.",
  "requester_email": "student@example.edu",
  "priority": "high",
  "category": "access"
}
```

Response shape:

```json
{
  "enabled": true,
  "message": "TDX ticket created.",
  "ticket": {
    "id": "98765",
    "number": "INC-98765",
    "status": "created"
  },
  "error_type": null,
  "attempts": 1
}
```

### PureChat handoff

`POST /api/integrations/purechat/handoff`

Request body:

```json
{
  "user_id": "demo-user",
  "transcript": ["Hi", "I need help with registration"]
}
```

Response fields include:
- `handoff.widget_id`
- `handoff.customData.transcript`
- `handoff.customData.turn_count`
- `handoff.customData.handoff_reason`
- `handoff.customData.source`
- `handoff.customData.created_at`

## 8) Docker option

From repo root:

```bash
copy backend\.env.example backend\.env
docker compose up --build
```

Production-oriented compose (built frontend image, named Chroma volume, healthchecks):

```bash
copy backend\.env.example backend\.env
docker compose -f docker-compose.prod.yml up --build -d
```

Set `CORS_ORIGINS` in `backend/.env` to include the UI origin (for example `http://localhost:8080`). Rebuild the frontend image with `VITE_API_BASE_URL` pointing at the API URL browsers use. Operational backup steps and notes: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## 9) Quick smoke script

Run backend smoke tests from repo root:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1 -ApiBaseUrl http://127.0.0.1:8000
```

Default smoke mode validates:
- `health`, `ingest`, `chat`
- integration endpoint contracts: `tdx/articles/search`, `tdx/tickets/create`, `purechat/handoff`

Run live integration checks (optional):

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1 -ApiBaseUrl http://127.0.0.1:8000 -IncludeLiveIntegrations
```

Live mode behavior:
- Reads `backend/.env` for `TDX_BASE_URL`, `TDX_API_TOKEN`, `PURECHAT_WIDGET_ID`
- Auto-skips TDX/PureChat live checks when not configured
- Fails if integrations are configured but endpoint responses still return `enabled=false`

Run auth and RBAC checks (optional, Phase 3):

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1 -ApiBaseUrl http://127.0.0.1:8000 -IncludeAuthChecks
```

Auth smoke behavior:
- Reads `backend/.env` for `AUTH_ENABLED`, `ENTRA_ISSUER`, `ENTRA_AUDIENCE`, `ENTRA_JWT_ALGORITHMS`, `ENTRA_TEST_HS256_SECRET`
- Auto-skips when auth mode is not configured for local HS256 testing
- Verifies:
  - valid token can call `/api/chat`
  - student token is denied (`403`) on `/api/integrations/tdx/tickets/create`
  - faculty token is allowed on `/api/integrations/tdx/tickets/create`

## 10) Retrieval evaluation helper

Run retrieval/rerank quality evaluation against `/api/chat`:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\eval-retrieval.ps1 -ApiBaseUrl http://127.0.0.1:8000
```

Optional custom query file:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\eval-retrieval.ps1 -ApiBaseUrl http://127.0.0.1:8000 -QueryFile .\scripts\eval-queries.json
```

`QueryFile` format supports:
- JSON array of strings (query-only mode), or
- JSON array of objects with:
  - `query`
  - `reference_url` (preferred for exact path match scoring)
  - `expected_source_contains` (substring expected in top source URL)

Use `scripts/eval-queries.example.json` as a template.
When labels are present, summary includes top-1 and top-3 source hit-rate metrics (prefers `reference_url` path match, falls back to `expected_source_contains`).

Grid-search rerank weight tuning (labeled queries):

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\sweep-rerank.ps1 -QueryFile .\scripts\eval-queries.example.json
```

This evaluates multiple weight/penalty combinations and prints:
- best config by top-1 hit-rate
- top 5 configs for manual selection/tuning

Bootstrap labeled query seeds from live KB pages:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-eval-queries.ps1 -SeedUrl https://support.oakland.edu -MaxPages 30 -OutFile .\scripts\eval-queries.generated.json
```

This generates query/label candidates (`query`, `expected_source_contains`, `reference_url`) you can review before running eval/sweep.

## 11) Automated backend tests

Run API tests:

```bash
cd backend
.\.venv\Scripts\python -m pytest -q
```

## 12) One-command full verification

From repo root:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\verify-all.ps1
```

This runs:
- backend pytest suite
- frontend production build
- backend runtime smoke script (`health`, `ingest`, `chat`, integration contracts)
