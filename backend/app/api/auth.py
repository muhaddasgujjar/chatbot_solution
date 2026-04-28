from fastapi import APIRouter

from app.core.session_store import get_session, upsert_session, upsert_session_from_entra
from app.models.schemas import EntraClaimsRequest, SessionInitRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/session")
def init_session(payload: SessionInitRequest):
    return {"session": upsert_session(payload)}


@router.get("/session/{user_id}")
def read_session(user_id: str):
    return {"session": get_session(user_id)}


@router.post("/entra/claims")
def map_entra_claims(payload: EntraClaimsRequest):
    return {"session": upsert_session_from_entra(payload)}
