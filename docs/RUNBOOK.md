# Operations runbook

## Production Docker (`docker-compose.prod.yml`)

1. Copy environment files:
   - `backend/.env.example` → `backend/.env`
   - Set `GROQ_API_KEY`, Chroma path stays `./chroma_db` inside the container (volume mount).
   - Set `CORS_ORIGINS` to include every browser origin that loads the UI (for example `http://localhost:8080` when using the default compose port mapping).

2. Build the UI with the **public** API URL your users will call (often the same host as the backend or your API gateway):

   ```bash
   docker compose -f docker-compose.prod.yml build --build-arg VITE_API_BASE_URL=https://your-api.example.com frontend
   ```

3. Start:

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

   - API: `http://localhost:8000` (adjust published ports as needed).
   - UI: `http://localhost:8080` (maps container port 80).

4. Health: `GET /health` on the backend (used by the compose healthcheck).

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
