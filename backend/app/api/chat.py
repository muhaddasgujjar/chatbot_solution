import json

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings
from app.core.llm import generate_answer
from app.core.retrieval import retrieve_context
from app.core.session_store import get_session
from app.core.storage import save_chat_turn
from app.models.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


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


@router.post("")
async def chat(payload: ChatRequest):
    session = get_session(payload.user_id)
    effective_role = session.get("role") if session.get("role") in {"student", "faculty", "all"} else payload.role
    if effective_role not in {"student", "faculty", "all"}:
        effective_role = "all"

    chunks = retrieve_context(payload.query, effective_role, settings.top_k)
    answer = await generate_answer(payload.query, chunks)
    sources = sorted({chunk.source_url for chunk in chunks if chunk.source_url})
    confidence = sum(chunk.score for chunk in chunks) / len(chunks) if chunks else 0.0
    requires_handoff = confidence < settings.min_confidence_score or "human" in payload.query.lower()
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
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        for token in answer.split():
            yield f"data: {json.dumps({'type': 'token', 'value': token + ' '})}\n\n"
        yield f"data: {json.dumps({'type': 'end', 'helpful_prompt': '[Was this helpful? Y/N]', 'sources': sources, 'confidence': confidence, 'requires_handoff': requires_handoff})}\n\n"

    return StreamingResponse(sse_stream(), media_type="text/event-stream")
