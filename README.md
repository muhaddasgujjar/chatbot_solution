# OU Chatbot Solution (Phase 1)

Phase 1 provides a Groq-based RAG MVP with:
- FastAPI backend (`/api/chat`, `/api/ingest`)
- Chroma vector store persistence
- React frontend chat UI
- Phase 1.1/1.2 additions: streaming SSE, feedback API, auth session skeleton, integration stubs

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

## 4) New API endpoints (Phase 1.2)

- `POST /api/auth/session` - initialize user role/session profile
- `GET /api/auth/session/{user_id}` - retrieve in-memory session
- `POST /api/auth/entra/claims` - map Entra-style claims to role session
- `POST /api/integrations/tdx/articles/search` - TDX search stub
- `POST /api/integrations/purechat/handoff` - PureChat handoff payload stub
- `POST /api/feedback` - save Y/N feedback record
- Global middleware adds `x-request-id` and structured request logs

## 5) Docker option

From repo root:

```bash
copy backend\.env.example backend\.env
docker compose up --build
```

## 6) Quick smoke script

Run backend smoke tests from repo root:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1 -ApiBaseUrl http://127.0.0.1:8000
```

## 7) Automated backend tests

Run API tests:

```bash
cd backend
.\.venv\Scripts\python -m pytest -q
```

## 8) One-command full verification

From repo root:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\verify-all.ps1
```

This runs:
- backend pytest suite
- frontend production build
- backend runtime smoke script (`health`, `ingest`, `chat`)
