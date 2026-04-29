import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.session_store import infer_role_from_raw_claims
from app.models.schemas import PureChatHandoffRequest, TdxArticleSearchRequest, TdxTicketCreateRequest

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _require_roles(request: Request, allowed_roles: set[str]) -> None:
    auth_context = getattr(request.state, "auth_context", {})
    claims = auth_context.get("claims", {}) if isinstance(auth_context, dict) else {}
    user_role = infer_role_from_raw_claims(claims) if isinstance(claims, dict) else "all"
    if user_role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient role for this endpoint.")


def _normalize_tdx_article(item: dict[str, Any]) -> dict[str, Any]:
    article_id = item.get("id") or item.get("ID") or item.get("articleId")
    title = item.get("title") or item.get("Title") or "Untitled article"
    summary = item.get("summary") or item.get("Description") or item.get("bodyPreview") or ""
    url = item.get("url") or item.get("Url") or item.get("link") or ""
    score = item.get("score") or item.get("Score") or 0.0
    category = item.get("category") or item.get("Category") or "general"
    updated = item.get("updatedAt") or item.get("UpdatedDate") or ""
    return {
        "id": str(article_id) if article_id is not None else "",
        "title": str(title),
        "summary": str(summary),
        "url": str(url),
        "score": float(score) if isinstance(score, (int, float)) else 0.0,
        "category": str(category),
        "updated_at": str(updated),
    }


def _classify_tdx_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connection_error"
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 429:
            return "rate_limited"
        if 500 <= status_code <= 599:
            return "upstream_server_error"
        if 400 <= status_code <= 499:
            return "client_request_error"
    return "request_error"


async def _tdx_post_with_retry(request_url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    max_attempts = max(settings.tdx_max_retries + 1, 1)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.tdx_timeout_seconds) as client:
                response = await client.post(request_url, json=payload, headers=headers)
                response.raise_for_status()
                return {
                    "ok": True,
                    "data": response.json(),
                    "attempts": attempt,
                    "error_type": None,
                }
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            last_error = exc
            error_type = _classify_tdx_error(exc)
            should_retry = (
                attempt < max_attempts
                and error_type in {"timeout", "connection_error", "rate_limited", "upstream_server_error"}
            )
            if not should_retry:
                break
            await asyncio.sleep(min(0.5 * attempt, 2.0))
        except httpx.HTTPError as exc:
            last_error = exc
            break

    return {
        "ok": False,
        "data": None,
        "attempts": max_attempts,
        "error_type": _classify_tdx_error(last_error) if last_error else "request_error",
    }


@router.post("/tdx/articles/search")
async def tdx_article_search(payload: TdxArticleSearchRequest, request: Request):
    _require_roles(request, {"student", "faculty", "all"})
    enabled = bool(settings.tdx_base_url and settings.tdx_api_token)
    if not enabled:
        return {
            "enabled": enabled,
            "message": "TDX is not configured yet. Set TDX_BASE_URL and TDX_API_TOKEN.",
            "query": payload.query,
            "results": [],
        }

    request_url = f"{settings.tdx_base_url.rstrip('/')}{settings.tdx_articles_path}"
    headers = {
        "Authorization": f"Bearer {settings.tdx_api_token}",
        "Content-Type": "application/json",
    }

    result = await _tdx_post_with_retry(request_url, {"query": payload.query}, headers)
    if not result["ok"]:
        return {
            "enabled": enabled,
            "message": "TDX article search failed.",
            "query": payload.query,
            "results": [],
            "error_type": result["error_type"],
            "attempts": result["attempts"],
        }
    data = result["data"]

    if isinstance(data, list):
        raw_results = data[:5]
    else:
        raw_results = data.get("results", [])[:5] if isinstance(data, dict) else []
    results = [_normalize_tdx_article(item) for item in raw_results if isinstance(item, dict)]

    return {
        "enabled": enabled,
        "message": "TDX search completed.",
        "query": payload.query,
        "results": results,
        "attempts": result["attempts"],
        "error_type": None,
    }


@router.post("/tdx/tickets/create")
async def tdx_ticket_create(payload: TdxTicketCreateRequest, request: Request):
    _require_roles(request, {"faculty", "all"})
    enabled = bool(settings.tdx_base_url and settings.tdx_api_token)
    if not enabled:
        return {
            "enabled": enabled,
            "message": "TDX is not configured yet. Set TDX_BASE_URL and TDX_API_TOKEN.",
            "ticket": None,
        }

    request_url = f"{settings.tdx_base_url.rstrip('/')}{settings.tdx_ticket_create_path}"
    headers = {
        "Authorization": f"Bearer {settings.tdx_api_token}",
        "Content-Type": "application/json",
    }
    tdx_payload = {
        "title": payload.title,
        "description": payload.description,
        "requesterEmail": payload.requester_email,
        "priority": payload.priority,
        "category": payload.category,
    }

    result = await _tdx_post_with_retry(request_url, tdx_payload, headers)
    if not result["ok"]:
        return {
            "enabled": enabled,
            "message": "TDX ticket creation failed.",
            "ticket": None,
            "error_type": result["error_type"],
            "attempts": result["attempts"],
        }

    data = result["data"] if isinstance(result["data"], dict) else {}
    ticket_id = data.get("id") or data.get("ID") or data.get("ticketId")
    ticket_number = data.get("ticketNumber") or data.get("Number") or ""
    status = data.get("status") or data.get("Status") or "created"

    return {
        "enabled": enabled,
        "message": "TDX ticket created.",
        "ticket": {
            "id": str(ticket_id) if ticket_id is not None else "",
            "number": str(ticket_number),
            "status": str(status),
        },
        "error_type": None,
        "attempts": result["attempts"],
    }


@router.post("/purechat/handoff")
def purechat_handoff(payload: PureChatHandoffRequest):
    enabled = bool(settings.purechat_widget_id)
    transcript_items = [
        {
            "message": line,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for line in payload.transcript
    ]
    return {
        "enabled": enabled,
        "message": (
            "PureChat handoff payload created."
            if enabled
            else "PureChat is not configured yet. Set PURECHAT_WIDGET_ID."
        ),
        "handoff": {
            "widget_id": settings.purechat_widget_id,
            "user_id": payload.user_id,
            "customData": {
                "transcript": transcript_items,
                "turn_count": len(transcript_items),
                "handoff_reason": "agent_low_confidence",
                "source": "ou-chatbot",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }
