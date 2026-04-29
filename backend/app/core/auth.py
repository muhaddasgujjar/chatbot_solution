import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Request

from app.core.config import settings


class AuthError(Exception):
    pass


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise AuthError("Missing bearer token.")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise AuthError("Missing bearer token.")
    return token


def _base64url_decode(data: str) -> bytes:
    padded = data + "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _parse_token(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Malformed JWT token.")
    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    header = json.loads(_base64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    signature = _base64url_decode(parts[2])
    return header, payload, signature, signing_input


def _validate_registered_claims(claims: dict[str, Any]) -> None:
    if settings.entra_issuer and claims.get("iss") != settings.entra_issuer:
        raise AuthError("Token issuer is invalid.")
    if settings.entra_audience:
        aud_claim = claims.get("aud")
        if isinstance(aud_claim, str):
            if aud_claim != settings.entra_audience:
                raise AuthError("Token audience is invalid.")
        elif isinstance(aud_claim, list):
            if settings.entra_audience not in aud_claim:
                raise AuthError("Token audience is invalid.")
        else:
            raise AuthError("Token audience is invalid.")

    exp = claims.get("exp")
    if exp is None:
        raise AuthError("Token is missing expiry claim.")
    if not isinstance(exp, (int, float)):
        raise AuthError("Token expiry claim is invalid.")
    if datetime.fromtimestamp(exp, tz=timezone.utc) <= datetime.now(timezone.utc):
        raise AuthError("Token has expired.")


def _validate_hs256(signature: bytes, signing_input: bytes) -> None:
    if not settings.entra_test_hs256_secret:
        raise AuthError("HS256 validation secret is not configured.")
    expected = hmac.new(
        settings.entra_test_hs256_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected):
        raise AuthError("Token signature or claims are invalid.")


def _fetch_jwks() -> dict[str, Any]:
    if not settings.entra_jwks_url:
        raise AuthError("JWKS URL is not configured.")
    try:
        response = httpx.get(settings.entra_jwks_url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise AuthError("Unable to fetch JWKS for token validation.") from exc
    if not isinstance(data, dict):
        raise AuthError("JWKS response is malformed.")
    return data


def _get_rsa_public_key_from_jwks(header: dict[str, Any]) -> tuple[int, int]:
    kid = str(header.get("kid", "")).strip()
    if not kid:
        raise AuthError("Token header missing key id (kid).")
    jwks = _fetch_jwks()
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise AuthError("JWKS response is malformed.")
    match = next((k for k in keys if isinstance(k, dict) and str(k.get("kid", "")) == kid), None)
    if not match:
        raise AuthError("No matching JWK found for token kid.")
    if str(match.get("kty", "")).upper() != "RSA":
        raise AuthError("Unsupported JWK key type.")
    n_raw = str(match.get("n", "")).strip()
    e_raw = str(match.get("e", "")).strip()
    if not n_raw or not e_raw:
        raise AuthError("JWK RSA key is missing modulus or exponent.")
    n = int.from_bytes(_base64url_decode(n_raw), byteorder="big")
    e = int.from_bytes(_base64url_decode(e_raw), byteorder="big")
    return n, e


def _validate_rs256(header: dict[str, Any], signature: bytes, signing_input: bytes) -> None:
    n, e = _get_rsa_public_key_from_jwks(header)
    key_len = (n.bit_length() + 7) // 8
    if len(signature) != key_len:
        raise AuthError("Token signature or claims are invalid.")

    sig_int = int.from_bytes(signature, byteorder="big")
    em = pow(sig_int, e, n).to_bytes(key_len, byteorder="big")
    digest = hashlib.sha256(signing_input).digest()
    digest_info_prefix = bytes.fromhex("3031300d060960864801650304020105000420")
    t = digest_info_prefix + digest
    ps_len = key_len - len(t) - 3
    if ps_len < 8:
        raise AuthError("Token signature or claims are invalid.")
    expected_em = b"\x00\x01" + (b"\xff" * ps_len) + b"\x00" + t
    if not hmac.compare_digest(em, expected_em):
        raise AuthError("Token signature or claims are invalid.")


def decode_and_validate_token(token: str) -> dict[str, Any]:
    algorithms = [algo.strip().upper() for algo in settings.entra_jwt_algorithms.split(",") if algo.strip()]
    header, claims, signature, signing_input = _parse_token(token)
    token_alg = str(header.get("alg", "")).upper()

    if token_alg not in algorithms:
        raise AuthError(f"Unsupported token algorithm '{token_alg}'.")

    if token_alg == "HS256":
        _validate_hs256(signature, signing_input)
    elif token_alg == "RS256":
        _validate_rs256(header, signature, signing_input)
    else:
        raise AuthError(f"Unsupported token algorithm '{token_alg}'.")

    _validate_registered_claims(claims)

    return claims


def get_auth_context_from_request(request: Request) -> dict[str, Any]:
    token = _get_bearer_token(request)
    claims = decode_and_validate_token(token)
    return {"claims": claims}
