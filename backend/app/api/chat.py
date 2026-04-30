import asyncio
import json
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth_service import decode_access_token
from app.core.config import settings
from app.core.llm import enforce_answer_grounding, generate_answer
from app.core.metrics import record_chat_turn
from app.core.quality import build_quality_metrics, should_trigger_handoff
from app.core.retrieval import retrieve_context
from app.core.session_store import get_session, infer_role_from_raw_claims
from app.core.storage import save_chat_turn
from app.db import get_db
from app.models.db_models import Conversation, Message
from app.models.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])

_STREAM_CHUNK = 4
_STREAM_DELAY = 0.012


@router.api_route("", methods=["OPTIONS"], include_in_schema=False)
async def chat_preflight(request: Request):
    origin = request.headers.get("origin", "http://localhost:5173")
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


def _extract_local_user_id(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    claims = decode_access_token(token)
    return claims.get("sub") if claims else None


def _save_conversation_turn(
    db: Session,
    db_user_id: str,
    conversation_id: str | None,
    query: str,
    answer: str,
    sources: list[str],
    confidence: float,
    requires_handoff: bool,
) -> str:
    if not conversation_id:
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=db_user_id,
            title=query[:100],
        )
        db.add(conv)
        db.flush()
        conversation_id = conv.id

    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=query,
        sources=[],
    )
    db.add(user_msg)
    db.flush()

    asst_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        sources=sources,
        confidence=confidence,
        requires_handoff=requires_handoff,
    )
    db.add(asst_msg)

    conv_obj = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv_obj and not conv_obj.title:
        conv_obj.title = query[:100]

    db.commit()
    return conversation_id


@router.post("")
async def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    session = get_session(payload.user_id)
    auth_context = getattr(request.state, "auth_context", {})
    token_role = infer_role_from_raw_claims(auth_context.get("claims", {})) if auth_context else "all"
    session_role = session.get("role")
    _roles = {"student", "faculty", "all", "alumni", "staff"}

    effective_role = session_role if session_role in _roles else token_role
    if effective_role not in _roles:
        effective_role = payload.role
    if effective_role not in _roles:
        effective_role = "all"

    chunks = retrieve_context(payload.query, effective_role, settings.top_k)

    sources: list[str] = []
    seen_sources: set[str] = set()
    for chunk in chunks:
        if chunk.source_url and chunk.source_url not in seen_sources:
            seen_sources.add(chunk.source_url)
            sources.append(chunk.source_url)

    answer = await generate_answer(payload.query, chunks, effective_role)
    answer, had_grounding_violation = enforce_answer_grounding(answer, sources)

    quality_metrics = build_quality_metrics(chunks, settings.min_confidence_score, settings.confidence_score_scale)
    confidence = quality_metrics["confidence"]
    requires_handoff = should_trigger_handoff(
        query=payload.query,
        quality_metrics=quality_metrics,
        had_grounding_violation=had_grounding_violation,
    )

    # Save to DB if authenticated with local JWT
    saved_conversation_id: str | None = payload.conversation_id
    db_user_id = _extract_local_user_id(request)
    if db_user_id:
        try:
            saved_conversation_id = _save_conversation_turn(
                db=db,
                db_user_id=db_user_id,
                conversation_id=payload.conversation_id,
                query=payload.query,
                answer=answer,
                sources=sources,
                confidence=confidence,
                requires_handoff=requires_handoff,
            )
        except Exception:
            pass  # Don't fail the chat if DB write fails

    # Also write to JSONL for ops backup
    save_chat_turn(
        user_id=payload.user_id,
        query=payload.query,
        answer=answer,
        role=effective_role,
        sources=sources,
        confidence=confidence,
        requires_handoff=requires_handoff,
    )

    async def sse_stream():
        started = time.perf_counter()
        try:
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            for i in range(0, len(answer), _STREAM_CHUNK):
                chunk = answer[i: i + _STREAM_CHUNK]
                yield f"data: {json.dumps({'type': 'token', 'value': chunk})}\n\n"
                await asyncio.sleep(_STREAM_DELAY)

            end_payload = {
                "type": "end",
                "helpful_prompt": "[Was this helpful? Y/N]",
                "sources": sources,
                "confidence": confidence,
                "requires_handoff": requires_handoff,
                "quality_metrics": quality_metrics,
                "conversation_id": saved_conversation_id,
            }
            yield f"data: {json.dumps(end_payload)}\n\n"
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_chat_turn(effective_role, latency_ms, requires_handoff)

    return StreamingResponse(sse_stream(), media_type="text/event-stream")
