from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth_service import decode_access_token
from app.db import get_db
from app.models.db_models import Conversation

router = APIRouter(prefix="/conversations", tags=["conversations"])
_bearer = HTTPBearer(auto_error=False)


def _require_user_id(credentials: HTTPAuthorizationCredentials) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    claims = decode_access_token(credentials.credentials)
    uid = claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return uid


@router.get("")
def list_conversations(
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
):
    user_id = _require_user_id(credentials)
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title or "New conversation",
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in convs
        ]
    }


@router.get("/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
):
    user_id = _require_user_id(credentials)
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources or [],
                "requires_handoff": m.requires_handoff,
                "created_at": m.created_at.isoformat(),
            }
            for m in conv.messages
        ],
    }


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
):
    user_id = _require_user_id(credentials)
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(conv)
    db.commit()
    return {"deleted": True}
