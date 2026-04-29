import base64
import hashlib
import hmac
import json
import random
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.llm import enforce_answer_grounding, scrub_pii
from app.core import auth as auth_core
from app.api import ingest as ingest_api
from app.core.quality import build_quality_metrics, should_trigger_handoff
from app.core.retrieval import rerank_chunks
from app.main import app
from app.core.config import settings
from app.models.schemas import SourceChunk


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "env" in payload


def test_request_id_header_present():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")


def test_custom_request_id_is_preserved():
    expected_request_id = "pytest-request-id"
    response = client.get("/health", headers={"x-request-id": expected_request_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == expected_request_id


def test_auth_session_roundtrip():
    payload = {
        "user_id": "pytest-user",
        "role": "student",
        "department": "Computer Science",
        "job_title": "Student",
    }
    create_response = client.post("/api/auth/session", json=payload)
    assert create_response.status_code == 200
    created = create_response.json()["session"]
    assert created["role"] == "student"

    read_response = client.get("/api/auth/session/pytest-user")
    assert read_response.status_code == 200
    read_back = read_response.json()["session"]
    assert read_back["user_id"] == "pytest-user"
    assert read_back["role"] == "student"


def test_entra_claim_mapping():
    payload = {
        "user_id": "entra-pytest",
        "department": "Engineering Faculty",
        "job_title": "Professor",
        "groups": ["staff"],
    }
    response = client.post("/api/auth/entra/claims", json=payload)
    assert response.status_code == 200
    session = response.json()["session"]
    assert session["role"] == "faculty"


def test_entra_claim_mapping_precedence_faculty_over_student():
    payload = {
        "user_id": "entra-precedence",
        "department": "Student Services",
        "job_title": "Faculty Advisor",
        "groups": ["student"],
    }
    response = client.post("/api/auth/entra/claims", json=payload)
    assert response.status_code == 200
    session = response.json()["session"]
    assert session["role"] == "faculty"


def test_chat_preflight_options():
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 204
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_tdx_article_search_unconfigured_shape():
    response = client.post("/api/integrations/tdx/articles/search", json={"query": "reset password"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["results"] == []
    assert "TDX is not configured" in payload["message"]


def test_tdx_ticket_create_unconfigured_shape():
    response = client.post(
        "/api/integrations/tdx/tickets/create",
        json={
            "title": "Login issue",
            "description": "User cannot log in to the portal after password reset.",
            "requester_email": "student@example.edu",
            "priority": "high",
            "category": "access",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["ticket"] is None
    assert "TDX is not configured" in payload["message"]


def test_purechat_handoff_contains_metadata():
    response = client.post(
        "/api/integrations/purechat/handoff",
        json={
            "user_id": "pytest-user",
            "transcript": ["Hi", "Need help with registration"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    handoff_data = payload["handoff"]["customData"]
    assert handoff_data["turn_count"] == 2
    assert handoff_data["source"] == "ou-chatbot"
    assert handoff_data["handoff_reason"] == "agent_low_confidence"
    assert handoff_data["created_at"]


def _make_hs256_token(groups: list[str], expires_in_seconds: int = 300):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "pytest-user",
        "iss": "https://login.microsoftonline.com/tenant/v2.0",
        "aud": "ou-chatbot-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "department": "Engineering Faculty" if "faculty" in groups else "Student Affairs",
        "jobTitle": "Professor" if "faculty" in groups else "Student",
        "groups": groups,
    }
    header = {"alg": "HS256", "typ": "JWT"}

    def _b64(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")

    encoded_header = _b64(header)
    encoded_payload = _b64(payload)
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(b"pytest-secret", signing_input, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("utf-8")
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def _b64url_encode_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _is_probable_prime(n: int, rounds: int = 8) -> bool:
    if n < 2:
        return False
    small_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    for p in small_primes:
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for _ in range(rounds):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _generate_prime(bits: int) -> int:
    while True:
        candidate = random.getrandbits(bits)
        candidate |= (1 << (bits - 1)) | 1
        if _is_probable_prime(candidate):
            return candidate


def _build_rs256_token_and_jwk() -> tuple[str, dict]:
    random.seed(42)
    e = 65537
    while True:
        p = _generate_prime(256)
        q = _generate_prime(256)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if phi % e != 0:
            break
    n = p * q
    d = pow(e, -1, phi)
    key_len = (n.bit_length() + 7) // 8

    now = int(datetime.now(timezone.utc).timestamp())
    header = {"alg": "RS256", "typ": "JWT", "kid": "pytest-rs-key"}
    payload = {
        "sub": "pytest-rs-user",
        "iss": "https://login.microsoftonline.com/tenant/v2.0",
        "aud": "ou-chatbot-api",
        "iat": now,
        "exp": now + 300,
        "department": "Engineering Faculty",
        "jobTitle": "Professor",
        "groups": ["faculty"],
    }
    encoded_header = _b64url_encode_bytes(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")

    digest = hashlib.sha256(signing_input).digest()
    digest_info_prefix = bytes.fromhex("3031300d060960864801650304020105000420")
    t = digest_info_prefix + digest
    ps = b"\xff" * (key_len - len(t) - 3)
    em = b"\x00\x01" + ps + b"\x00" + t
    em_int = int.from_bytes(em, byteorder="big")
    signature_int = pow(em_int, d, n)
    signature = signature_int.to_bytes(key_len, byteorder="big")
    encoded_signature = _b64url_encode_bytes(signature)
    token = f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    jwk = {
        "kty": "RSA",
        "kid": "pytest-rs-key",
        "n": _b64url_encode_bytes(n.to_bytes(key_len, byteorder="big")),
        "e": _b64url_encode_bytes(e.to_bytes((e.bit_length() + 7) // 8, byteorder="big")),
        "alg": "RS256",
        "use": "sig",
    }
    return token, jwk


def test_auth_enabled_blocks_missing_token_on_chat():
    previous = {
        "auth_enabled": settings.auth_enabled,
        "entra_test_hs256_secret": settings.entra_test_hs256_secret,
        "entra_issuer": settings.entra_issuer,
        "entra_audience": settings.entra_audience,
        "entra_jwt_algorithms": settings.entra_jwt_algorithms,
    }
    settings.auth_enabled = True
    settings.entra_test_hs256_secret = "pytest-secret"
    settings.entra_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    settings.entra_audience = "ou-chatbot-api"
    settings.entra_jwt_algorithms = "HS256"
    try:
        response = client.post(
            "/api/chat",
            json={"query": "hello", "user_id": "no-token-user", "role": "all"},
        )
        assert response.status_code == 401
    finally:
        settings.auth_enabled = previous["auth_enabled"]
        settings.entra_test_hs256_secret = previous["entra_test_hs256_secret"]
        settings.entra_issuer = previous["entra_issuer"]
        settings.entra_audience = previous["entra_audience"]
        settings.entra_jwt_algorithms = previous["entra_jwt_algorithms"]


def test_auth_enabled_accepts_valid_token_for_chat():
    previous = {
        "auth_enabled": settings.auth_enabled,
        "entra_test_hs256_secret": settings.entra_test_hs256_secret,
        "entra_issuer": settings.entra_issuer,
        "entra_audience": settings.entra_audience,
        "entra_jwt_algorithms": settings.entra_jwt_algorithms,
    }
    settings.auth_enabled = True
    settings.entra_test_hs256_secret = "pytest-secret"
    settings.entra_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    settings.entra_audience = "ou-chatbot-api"
    settings.entra_jwt_algorithms = "HS256"
    token = _make_hs256_token(groups=["student"])
    try:
        response = client.post(
            "/api/chat",
            json={"query": "How can I contact IT support?", "user_id": "token-user", "role": "student"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
    finally:
        settings.auth_enabled = previous["auth_enabled"]
        settings.entra_test_hs256_secret = previous["entra_test_hs256_secret"]
        settings.entra_issuer = previous["entra_issuer"]
        settings.entra_audience = previous["entra_audience"]
        settings.entra_jwt_algorithms = previous["entra_jwt_algorithms"]


def test_rbac_blocks_student_for_tdx_ticket_create():
    previous = {
        "auth_enabled": settings.auth_enabled,
        "entra_test_hs256_secret": settings.entra_test_hs256_secret,
        "entra_issuer": settings.entra_issuer,
        "entra_audience": settings.entra_audience,
        "entra_jwt_algorithms": settings.entra_jwt_algorithms,
    }
    settings.auth_enabled = True
    settings.entra_test_hs256_secret = "pytest-secret"
    settings.entra_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    settings.entra_audience = "ou-chatbot-api"
    settings.entra_jwt_algorithms = "HS256"
    token = _make_hs256_token(groups=["student"])
    try:
        response = client.post(
            "/api/integrations/tdx/tickets/create",
            json={
                "title": "Need help",
                "description": "Student trying to create faculty endpoint request.",
                "requester_email": "student@example.edu",
                "priority": "normal",
                "category": "general",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
    finally:
        settings.auth_enabled = previous["auth_enabled"]
        settings.entra_test_hs256_secret = previous["entra_test_hs256_secret"]
        settings.entra_issuer = previous["entra_issuer"]
        settings.entra_audience = previous["entra_audience"]
        settings.entra_jwt_algorithms = previous["entra_jwt_algorithms"]


def test_rbac_allows_faculty_for_tdx_ticket_create():
    previous = {
        "auth_enabled": settings.auth_enabled,
        "entra_test_hs256_secret": settings.entra_test_hs256_secret,
        "entra_issuer": settings.entra_issuer,
        "entra_audience": settings.entra_audience,
        "entra_jwt_algorithms": settings.entra_jwt_algorithms,
    }
    settings.auth_enabled = True
    settings.entra_test_hs256_secret = "pytest-secret"
    settings.entra_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    settings.entra_audience = "ou-chatbot-api"
    settings.entra_jwt_algorithms = "HS256"
    token = _make_hs256_token(groups=["faculty"])
    try:
        response = client.post(
            "/api/integrations/tdx/tickets/create",
            json={
                "title": "Faculty help",
                "description": "Faculty workflow should pass RBAC even when TDX is not configured.",
                "requester_email": "faculty@example.edu",
                "priority": "normal",
                "category": "general",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is False
    finally:
        settings.auth_enabled = previous["auth_enabled"]
        settings.entra_test_hs256_secret = previous["entra_test_hs256_secret"]
        settings.entra_issuer = previous["entra_issuer"]
        settings.entra_audience = previous["entra_audience"]
        settings.entra_jwt_algorithms = previous["entra_jwt_algorithms"]


def test_rs256_decode_and_validate_token_success():
    token, jwk = _build_rs256_token_and_jwk()

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [jwk]}

    previous = {
        "entra_issuer": settings.entra_issuer,
        "entra_audience": settings.entra_audience,
        "entra_jwt_algorithms": settings.entra_jwt_algorithms,
        "entra_jwks_url": settings.entra_jwks_url,
    }
    settings.entra_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    settings.entra_audience = "ou-chatbot-api"
    settings.entra_jwt_algorithms = "RS256"
    settings.entra_jwks_url = "https://example.invalid/jwks"
    original_get = auth_core.httpx.get
    auth_core.httpx.get = lambda *_args, **_kwargs: _FakeResponse()
    try:
        claims = auth_core.decode_and_validate_token(token)
        assert claims["sub"] == "pytest-rs-user"
    finally:
        auth_core.httpx.get = original_get
        settings.entra_issuer = previous["entra_issuer"]
        settings.entra_audience = previous["entra_audience"]
        settings.entra_jwt_algorithms = previous["entra_jwt_algorithms"]
        settings.entra_jwks_url = previous["entra_jwks_url"]


def test_rs256_decode_and_validate_token_rejects_bad_signature():
    token, jwk = _build_rs256_token_and_jwk()
    parts = token.split(".")
    tampered_payload = _b64url_encode_bytes(json.dumps({"sub": "tampered"}, separators=(",", ":")).encode("utf-8"))
    bad_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [jwk]}

    previous = {
        "entra_issuer": settings.entra_issuer,
        "entra_audience": settings.entra_audience,
        "entra_jwt_algorithms": settings.entra_jwt_algorithms,
        "entra_jwks_url": settings.entra_jwks_url,
    }
    settings.entra_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    settings.entra_audience = "ou-chatbot-api"
    settings.entra_jwt_algorithms = "RS256"
    settings.entra_jwks_url = "https://example.invalid/jwks"
    original_get = auth_core.httpx.get
    auth_core.httpx.get = lambda *_args, **_kwargs: _FakeResponse()
    try:
        try:
            auth_core.decode_and_validate_token(bad_token)
            assert False, "Expected AuthError for tampered RS256 token"
        except auth_core.AuthError:
            pass
    finally:
        auth_core.httpx.get = original_get
        settings.entra_issuer = previous["entra_issuer"]
        settings.entra_audience = previous["entra_audience"]
        settings.entra_jwt_algorithms = previous["entra_jwt_algorithms"]
        settings.entra_jwks_url = previous["entra_jwks_url"]


def test_enforce_answer_grounding_allows_retrieved_source_link():
    source_urls = ["https://support.oakland.edu/kb/reset-password"]
    answer = "Use this guide: https://support.oakland.edu/kb/reset-password"
    sanitized, had_violation = enforce_answer_grounding(answer, source_urls)
    assert had_violation is False
    assert "https://support.oakland.edu/kb/reset-password" in sanitized


def test_enforce_answer_grounding_removes_unretrieved_link():
    source_urls = ["https://support.oakland.edu/kb/reset-password"]
    answer = "Check https://example.com/phishing for details."
    sanitized, had_violation = enforce_answer_grounding(answer, source_urls)
    assert had_violation is True
    assert "example.com" not in sanitized
    assert "[link removed: not in retrieved sources]" in sanitized


def test_scrub_pii_redacts_email_and_phone():
    text = "Contact me at student@oakland.edu or 248-555-1212."
    scrubbed = scrub_pii(text)
    assert "student@oakland.edu" not in scrubbed
    assert "248-555-1212" not in scrubbed
    assert scrubbed.count("[REDACTED]") >= 2


def test_scrub_pii_redacts_secret_like_tokens():
    text = (
        "keys: sk-abcdefghijklmnopqrstuvwxyz1234 "
        "ghp_abcdefghijklmnopqrstuvwxyz123456 "
        "AKIAABCDEFGHIJKLMNOP"
    )
    scrubbed = scrub_pii(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in scrubbed
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in scrubbed
    assert "AKIAABCDEFGHIJKLMNOP" not in scrubbed
    assert scrubbed.count("[REDACTED]") >= 3


def test_ingest_docx_paths_success_with_mocked_extractor(tmp_path):
    sample_docx = tmp_path / "sample.docx"
    sample_docx.write_bytes(b"fake-docx-content")

    original_extract = ingest_api._extract_docx_text_from_path
    original_upsert = ingest_api.upsert_chunks
    ingest_api._extract_docx_text_from_path = lambda _path: "Paragraph one. Paragraph two."
    ingest_api.upsert_chunks = lambda chunks: len(chunks)
    try:
        response = client.post(
            "/api/ingest",
            json={"docx_paths": [str(sample_docx)], "role_access": "all"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ingested_urls"] == []
        assert len(payload["ingested_docx_paths"]) == 1
        assert payload["chunks_upserted"] > 0
    finally:
        ingest_api._extract_docx_text_from_path = original_extract
        ingest_api.upsert_chunks = original_upsert


def test_ingest_docx_paths_limit_enforced(tmp_path):
    previous_limit = settings.ingest_max_docx_files
    settings.ingest_max_docx_files = 2
    try:
        paths = [str((tmp_path / f"doc-{idx}.docx").resolve()) for idx in range(3)]
        response = client.post("/api/ingest", json={"docx_paths": paths, "role_access": "all"})
        assert response.status_code == 400
        assert "DOCX batch exceeds limit" in response.json()["detail"]
    finally:
        settings.ingest_max_docx_files = previous_limit


def test_ingest_crawl_limit_enforced():
    previous_limit = settings.ingest_max_crawl_pages
    settings.ingest_max_crawl_pages = 2
    try:
        response = client.post(
            "/api/ingest",
            json={
                "urls": ["https://support.oakland.edu"],
                "crawl": True,
                "max_pages": 3,
                "role_access": "all",
            },
        )
        assert response.status_code == 400
        assert "Crawl page limit exceeds configured max" in response.json()["detail"]
    finally:
        settings.ingest_max_crawl_pages = previous_limit


def test_build_quality_metrics_for_non_empty_chunks():
    chunks = [
        SourceChunk(text="a", source_url="https://support.oakland.edu/a", role_access="all", score=0.8),
        SourceChunk(text="b", source_url="https://support.oakland.edu/b", role_access="all", score=0.5),
    ]
    metrics = build_quality_metrics(chunks, min_confidence_score=0.6, score_scale=2.5)
    assert metrics["chunk_count"] == 2
    assert metrics["source_count"] == 2
    assert metrics["top_score"] == 0.8
    assert metrics["avg_score"] == 0.65
    assert metrics["confidence"] == 1.0
    assert abs(metrics["score_spread"] - 0.3) < 1e-9
    assert metrics["low_confidence"] is False


def test_should_trigger_handoff_when_low_confidence_or_grounding_violation():
    low_confidence_metrics = {
        "chunk_count": 1,
        "source_count": 1,
        "avg_score": 0.3,
        "top_score": 0.3,
        "score_spread": 0.0,
        "low_confidence": True,
    }
    assert should_trigger_handoff("Need wifi help", low_confidence_metrics, False) is True
    assert should_trigger_handoff("Need wifi help", {"low_confidence": False}, True) is True
    assert should_trigger_handoff("I need a human please", {"low_confidence": False}, False) is True
    assert should_trigger_handoff("Need wifi help", {"low_confidence": False}, False) is False


def test_rerank_chunks_promotes_keyword_overlap():
    query = "reset password portal"
    chunks = [
        SourceChunk(
            text="General information and office contacts.",
            source_url="https://support.oakland.edu/general",
            role_access="all",
            score=0.9,
        ),
        SourceChunk(
            text="Steps to reset your password for the student portal account access.",
            source_url="https://support.oakland.edu/password",
            role_access="all",
            score=0.75,
        ),
    ]
    ranked = rerank_chunks(query, chunks, top_k=2)
    assert ranked[0].source_url == "https://support.oakland.edu/password"


def test_rerank_chunks_penalizes_overly_short_chunks():
    query = "wifi setup"
    chunks = [
        SourceChunk(
            text="wifi",
            source_url="https://support.oakland.edu/short",
            role_access="all",
            score=0.85,
        ),
        SourceChunk(
            text="How to configure OU secure wifi on student devices with full setup steps.",
            source_url="https://support.oakland.edu/wifi",
            role_access="all",
            score=0.78,
        ),
    ]
    ranked = rerank_chunks(query, chunks, top_k=2)
    assert ranked[0].source_url == "https://support.oakland.edu/wifi"


def test_rerank_chunks_uses_source_url_keyword_signal():
    query = "help desk ticket"
    chunks = [
        SourceChunk(
            text="General OU IT guidance and office information for students.",
            source_url="https://support.oakland.edu/kb/ticket-request",
            role_access="all",
            score=0.65,
        ),
        SourceChunk(
            text="General OU IT guidance and office information for students.",
            source_url="https://support.oakland.edu/kb/general-support",
            role_access="all",
            score=0.65,
        ),
    ]
    ranked = rerank_chunks(query, chunks, top_k=2)
    assert ranked[0].source_url == "https://support.oakland.edu/kb/ticket-request"
