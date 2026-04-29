import time

from app.api.auth import router as auth_router
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.feedback import router as feedback_router
from app.api.ingest import router as ingest_router
from app.api.integrations import router as integrations_router
from app.core.auth import AuthError, get_auth_context_from_request
from app.core.config import settings
from app.core.observability import (
    check_rate_limit,
    get_request_id,
    log_request,
    rate_limit_response,
)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(ingest_router, prefix=settings.api_prefix)
app.include_router(feedback_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(integrations_router, prefix=settings.api_prefix)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    request_id = get_request_id(request)
    client_ip = request.client.host if request.client else "unknown"
    allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    request_origin = request.headers.get("origin")
    if request.method == "OPTIONS" and request_origin:
        allow_origin = request_origin if request_origin in allowed_origins else (allowed_origins[0] if allowed_origins else "*")
        response = Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": allow_origin,
                "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "x-request-id": request_id,
            },
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        log_request(request, response.status_code, latency_ms, request_id)
        return response

    if not check_rate_limit(client_ip):
        return rate_limit_response(request_id)

    protected_paths = (f"{settings.api_prefix}/chat", f"{settings.api_prefix}/integrations")
    if settings.auth_enabled and request.url.path.startswith(protected_paths):
        try:
            request.state.auth_context = get_auth_context_from_request(request)
        except AuthError as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": str(exc), "request_id": request_id},
                headers={"x-request-id": request_id},
            )
    else:
        request.state.auth_context = {}

    try:
        response = await call_next(request)
    except Exception:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        log_request(request, 500, latency_ms, request_id)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"x-request-id": request_id},
        )

    response.headers["x-request-id"] = request_id
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    log_request(request, response.status_code, latency_ms, request_id)
    return response


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env}


@app.options("/{path:path}")
def preflight(path: str):
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    primary_origin = origins[0] if origins else "*"
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": primary_origin,
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )
