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


def infer_role_from_claim_attributes(department: str, job_title: str, groups: list[str]) -> str:
    """
    Deterministic precedence:
    1) faculty match anywhere -> faculty
    2) student match anywhere -> student
    3) otherwise -> all
    """
    job_title_normalized = str(job_title).lower()
    department_normalized = str(department).lower()
    groups_normalized = [str(group).lower() for group in groups]

    if (
        "faculty" in job_title_normalized
        or "faculty" in department_normalized
        or "faculty" in groups_normalized
    ):
        return "faculty"
    if (
        "student" in job_title_normalized
        or "student" in department_normalized
        or "student" in groups_normalized
    ):
        return "student"
    return "all"


def infer_role_from_raw_claims(claims: dict) -> str:
    job_title = str(claims.get("jobTitle", ""))
    department = str(claims.get("department", ""))
    groups_raw = claims.get("groups", [])
    groups = [str(group).lower() for group in groups_raw] if isinstance(groups_raw, list) else []
    return infer_role_from_claim_attributes(department=department, job_title=job_title, groups=groups)


def upsert_session_from_entra(payload: EntraClaimsRequest) -> dict:
    role = infer_role_from_claim_attributes(
        department=payload.department,
        job_title=payload.job_title,
        groups=payload.groups,
    )
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
