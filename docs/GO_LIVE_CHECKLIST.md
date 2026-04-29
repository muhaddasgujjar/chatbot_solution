# Go-live checklist

Use this before promoting a build to production or a pilot audience.

## Configuration

- [ ] `backend/.env` populated from `.env.example`; secrets not committed.
- [ ] `GROQ_API_KEY` (or configured LLM provider) validated in staging.
- [ ] `CORS_ORIGINS` lists every browser origin that loads the UI (or same-origin proxy is used and CORS is narrowed intentionally).
- [ ] Auth: `AUTH_ENABLED`, issuer, audience, JWKS/HS256 test settings match the identity provider.
- [ ] Integrations: TDX/PureChat URLs and tokens verified against non-production sandboxes first.

## Data and KB

- [ ] Chroma volume backed up using [RUNBOOK.md](./RUNBOOK.md) procedure after major ingest.
- [ ] Ingest allowlists (`ALLOWED_INGEST_DOMAINS`) reviewed for scope.
- [ ] Spot-check answers against sensitive topics (FERPA-style, account resets, emergencies).

## Observability

- [ ] Open **Analytics** in the UI (or `GET /api/analytics/dashboard`) and confirm counters move under test traffic.
- [ ] Confirm structured logs include `x-request-id` and are collected by your log stack.
- [ ] Define alert thresholds (5xx rate, p95 latency, handoff rate spike) in your platform.

## Performance

- [ ] Run `scripts/load-test.ps1` against staging; save approximate RPS and error rate.
- [ ] Chat streaming timeouts acceptable behind your reverse proxy (see nginx `proxy_read_timeout`).

## Verification

- [ ] `scripts/verify-all.ps1` passes on the release candidate.
- [ ] Smoke test with optional `-IncludeLiveIntegrations` / `-IncludeAuthChecks` as applicable.

## Rollback

- [ ] Previous container images or deployment revision tagged and ready to roll back.
- [ ] Chroma restore procedure validated once in a non-prod environment.
