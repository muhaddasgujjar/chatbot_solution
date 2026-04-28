from fastapi.testclient import TestClient

from app.main import app


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
