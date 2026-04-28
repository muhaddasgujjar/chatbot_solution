from typing import Dict

from app.models.schemas import EntraClaimsRequest, SessionInitRequest

_SESSIONS: Dict[str, dict] = {}


def upsert_session(payload: SessionInitRequest) -> dict:
    record = {
        "user_id": payload.user_id,
        "role": payload.role,
        "department": payload.department,
        "job_title": payload.job_title,
    }
    _SESSIONS[payload.user_id] = record
    return record


def get_session(user_id: str) -> dict:
    return _SESSIONS.get(user_id, {})


def _infer_role_from_claims(payload: EntraClaimsRequest) -> str:
    job_title = payload.job_title.lower()
    department = payload.department.lower()
    groups = [group.lower() for group in payload.groups]

    if "faculty" in job_title or "faculty" in department or "faculty" in groups:
        return "faculty"
    if "student" in job_title or "student" in department or "student" in groups:
        return "student"
    return "all"


def upsert_session_from_entra(payload: EntraClaimsRequest) -> dict:
    role = _infer_role_from_claims(payload)
    record = {
        "user_id": payload.user_id,
        "role": role,
        "department": payload.department,
        "job_title": payload.job_title,
        "groups": payload.groups,
        "source": "entra_claims",
    }
    _SESSIONS[payload.user_id] = record
    return record
