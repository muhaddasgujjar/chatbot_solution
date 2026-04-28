import json
from datetime import datetime, timezone

from app.core.config import settings
from app.models.schemas import FeedbackRequest


def save_feedback(payload: FeedbackRequest) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": payload.user_id,
        "query": payload.query,
        "answer": payload.answer,
        "helpful": payload.helpful,
    }
    with open(settings.feedback_store_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


def save_chat_turn(
    user_id: str,
    query: str,
    answer: str,
    role: str,
    sources: list[str],
    confidence: float,
    requires_handoff: bool,
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "query": query,
        "answer": answer,
        "role": role,
        "sources": sources,
        "confidence": confidence,
        "requires_handoff": requires_handoff,
    }
    with open(settings.chat_store_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
