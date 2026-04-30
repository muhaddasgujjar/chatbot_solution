import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.storage import save_feedback
from app.db import get_db
from app.models.db_models import Feedback
from app.models.schemas import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
def feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    record = Feedback(
        id=str(uuid.uuid4()),
        query=payload.query,
        answer=payload.answer,
        helpful=payload.helpful,
    )
    db.add(record)
    db.commit()
    # Also write to JSONL backup
    save_feedback(payload)
    return {"status": "saved"}


@router.get("")
def list_feedback(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    feedbacks = (
        db.query(Feedback)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )
    total = db.query(Feedback).count()
    items = [
        {
            "id": f.id,
            "user_id": f.user_id or "",
            "query": f.query,
            "answer": f.answer,
            "helpful": f.helpful,
            "timestamp": f.created_at.isoformat(),
        }
        for f in feedbacks
    ]
    return {"items": items, "total": total}
