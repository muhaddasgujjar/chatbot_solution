import json

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings
from app.core.llm import enforce_answer_grounding, generate_answer
from app.core.quality import build_quality_metrics, should_trigger_handoff
from app.core.retrieval import retrieve_context
from app.core.session_store import get_session, infer_role_from_raw_claims
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
async def chat(payload: ChatRequest, request: Request):
    session = get_session(payload.user_id)
    auth_context = getattr(request.state, "auth_context", {})
    token_role = infer_role_from_raw_claims(auth_context.get("claims", {})) if auth_context else "all"
    session_role = session.get("role")
    effective_role = session_role if session_role in {"student", "faculty", "all"} else token_role
    if effective_role not in {"student", "faculty", "all"}:
        effective_role = payload.role
    if effective_role not in {"student", "faculty", "all"}:
        effective_role = "all"

    chunks = retrieve_context(payload.query, effective_role, settings.top_k)
    sources = []
    seen_sources = set()
    for chunk in chunks:
        source_url = chunk.source_url
        if source_url and source_url not in seen_sources:
            seen_sources.add(source_url)
            sources.append(source_url)
    answer = await generate_answer(payload.query, chunks)
    answer, had_grounding_violation = enforce_answer_grounding(answer, sources)
    quality_metrics = build_quality_metrics(
        chunks,
        settings.min_confidence_score,
        settings.confidence_score_scale,
    )
    confidence = quality_metrics["confidence"]
    requires_handoff = should_trigger_handoff(
        query=payload.query,
        quality_metrics=quality_metrics,
        had_grounding_violation=had_grounding_violation,
    )
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
        yield f"data: {json.dumps({'type': 'end', 'helpful_prompt': '[Was this helpful? Y/N]', 'sources': sources, 'confidence': confidence, 'requires_handoff': requires_handoff, 'quality_metrics': quality_metrics})}\n\n"

    return StreamingResponse(sse_stream(), media_type="text/event-stream")
