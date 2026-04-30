from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth_service import (
    authenticate_user,
    create_access_token,
    create_user,
    decode_access_token,
    get_user_by_email,
    get_user_by_id,
)
from app.core.session_store import get_session, upsert_session, upsert_session_from_entra
from app.db import get_db
from app.models.schemas import (
    EntraClaimsRequest,
    LoginRequest,
    SessionInitRequest,
    SignupRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _token_response(user) -> dict:
    return {
        "token": create_access_token(user.id, user.email, user.role, user.is_admin),
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_admin": user.is_admin,
    }


@router.post("/register", response_model=TokenResponse)
def register(payload: SignupRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    valid_roles = {"student", "faculty", "staff", "alumni", "all"}
    role = payload.role if payload.role in valid_roles else "all"
    user = create_user(db, payload.email, payload.password, payload.display_name, role)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _token_response(user)


@router.get("/me")
def me(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    claims = decode_access_token(credentials.credentials)
    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = get_user_by_id(db, claims["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_admin": user.is_admin,
    }


# Legacy session endpoints (Entra / in-memory)
@router.post("/session")
def init_session(payload: SessionInitRequest):
    return {"session": upsert_session(payload)}


@router.get("/session/{user_id}")
def read_session(user_id: str):
    return {"session": get_session(user_id)}


@router.post("/entra/claims")
def map_entra_claims(payload: EntraClaimsRequest):
    return {"session": upsert_session_from_entra(payload)}
