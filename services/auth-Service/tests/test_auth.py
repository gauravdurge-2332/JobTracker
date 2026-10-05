import time

import jwt

CREDS = {"email": "a@example.com", "password": "secret123"}


def signup(client, creds=CREDS):
    return client.post("/auth/signup", json=creds)


def login_token(client, creds=CREDS):
    signup(client, creds)
    resp = client.post("/auth/login", json=creds)
    return resp.json()["access_token"]


def test_signup_returns_201_without_password(client):
    resp = signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_duplicate_signup_returns_409(client):
    signup(client)
    assert signup(client).status_code == 409


def test_login_returns_bearer_token(client):
    signup(client)
    resp = client.post("/auth/login", json=CREDS)
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


def test_login_wrong_password_and_unknown_email_look_identical(client):
    signup(client)
    wrong = client.post("/auth/login", json={**CREDS, "password": "nope-nope"})
    unknown = client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "secret123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_verify_with_valid_token(client):
    token = login_token(client)
    resp = client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@example.com"
    assert "id" in resp.json()


def test_verify_without_token_is_rejected(client):
    assert client.get("/auth/verify").status_code in (401, 403)


def test_verify_with_garbled_token_returns_401(client):
    resp = client.get("/auth/verify", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_verify_with_expired_token_returns_401(client):
    user_id = signup(client).json()["id"]
    expired = jwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) - 60},
        "test-secret",
        algorithm="HS256",
    )
    resp = client.get("/auth/verify", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
