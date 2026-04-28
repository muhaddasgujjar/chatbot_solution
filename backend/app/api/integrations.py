from datetime import datetime, timezone

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import PureChatHandoffRequest, TdxArticleSearchRequest

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/tdx/articles/search")
async def tdx_article_search(payload: TdxArticleSearchRequest):
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

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(request_url, json={"query": payload.query}, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "enabled": enabled,
            "message": f"TDX request failed with status {exc.response.status_code}.",
            "query": payload.query,
            "results": [],
        }
    except httpx.HTTPError:
        return {
            "enabled": enabled,
            "message": "Could not reach TDX API endpoint.",
            "query": payload.query,
            "results": [],
        }

    if isinstance(data, list):
        results = data[:5]
    else:
        results = data.get("results", [])[:5] if isinstance(data, dict) else []

    return {
        "enabled": enabled,
        "message": "TDX search completed.",
        "query": payload.query,
        "results": results,
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
            "customData": {"transcript": transcript_items, "turn_count": len(transcript_items)},
        },
    }
