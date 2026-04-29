# Operations runbook

## Production Docker (`docker-compose.prod.yml`)

1. Copy environment files:
   - `backend/.env.example` → `backend/.env`
   - Set `GROQ_API_KEY`, Chroma path stays `./chroma_db` inside the container (volume mount).
   - **Same-origin (default stack):** build uses empty `VITE_API_BASE_URL` so the browser calls `/api` and `/health` on the UI host; nginx proxies to the backend. Set `CORS_ORIGINS` to the UI origin (for example `http://localhost:8080`).
   - **Split origin:** if the UI calls a different API hostname, rebuild with `--build-arg VITE_API_BASE_URL=...` and list both origins in `CORS_ORIGINS`.

2. Build (same-origin default):

   ```bash
   docker compose -f docker-compose.prod.yml build
   ```

   Split-origin example:

   ```bash
   docker compose -f docker-compose.prod.yml build --build-arg VITE_API_BASE_URL=https://your-api.example.com frontend
   ```

3. Start:

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

   - API: `http://localhost:8000` (adjust published ports as needed).
   - UI: `http://localhost:8080` (maps container port 80).

4. Health: `GET /health` on the backend (used by the compose healthcheck). When using the nginx proxy, the browser can use the same path as in development: `GET /health` on the UI port forwards to the API.

## Observability

- **In-app:** open the **Analytics** tab in the web UI (or `GET /api/analytics/dashboard` on the API). Metrics are in-process and reset on restart; they include HTTP error rates, API latency, and per-audience chat and handoff rates (faculty, student, alumni, all).
- **Logs:** use `x-request-id` and structured JSON `request_completed` events in your log aggregator.

## Chroma backup and restore

Data lives in the Docker volume `ou_chroma_data` (see `docker-compose.prod.yml`).

**Backup (example):**

```bash
docker run --rm -v ou_chroma_data:/data -v "%cd%:/backup" alpine tar czf /backup/chroma-backup.tgz -C /data .
```

**Restore (example, with stack stopped):**

```bash
docker run --rm -v ou_chroma_data:/data -v "%cd%:/backup" alpine sh -c "cd /data && rm -rf * && tar xzf /backup/chroma-backup.tgz"
```

Adjust volume name if you changed it in compose. On Linux/macOS, replace `%cd%` with `$(pwd)`.

## Verification before release

From the repo root (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-all.ps1
```

## Logs and request IDs

The API logs structured JSON per request and attaches `x-request-id` to responses. Correlate client reports with backend logs using that header.
