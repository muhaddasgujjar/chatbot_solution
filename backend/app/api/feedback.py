from fastapi import APIRouter

from app.core.storage import save_feedback
from app.models.schemas import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def feedback(payload: FeedbackRequest):
    save_feedback(payload)
    return {"status": "saved"}
