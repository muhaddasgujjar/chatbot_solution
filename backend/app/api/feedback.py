import json
from pathlib import Path

from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.storage import save_feedback
from app.models.schemas import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def feedback(payload: FeedbackRequest):
    save_feedback(payload)
    return {"status": "saved"}


@router.get("")
def list_feedback(limit: int = Query(default=20, ge=1, le=200)):
    """Return recent feedback entries for the admin panel."""
    path = Path(settings.feedback_store_path)
    if not path.exists():
        return {"items": [], "total": 0}

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    items: list[dict] = []
    for line in reversed(raw_lines[-500:]):
        if line.strip():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if len(items) >= limit:
            break

    return {"items": items, "total": len(raw_lines)}
