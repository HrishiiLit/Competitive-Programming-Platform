import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res_v1 = await client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["api_version"] == "v1"


@pytest.mark.asyncio
async def test_user_registration(client: AsyncClient):
    payload = {
        "username": "tourist_fan",
        "email": "tourist@example.com",
        "password": "SuperSecurePassword123!",
        "full_name": "Gennady Korotkevich Fan",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "tourist_fan"
    assert data["email"] == "tourist@example.com"
    assert data["full_name"] == "Gennady Korotkevich Fan"
    assert "PARTICIPANT" in data["roles"]
    assert data["account_status"] == "ACTIVE"
    assert data["email_verified"] is False


@pytest.mark.asyncio
async def test_user_registration_duplicate_username(client: AsyncClient):
    payload1 = {
        "username": "duplicate_user",
        "email": "user1@example.com",
        "password": "Password123!",
        "full_name": "First User",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "username": "duplicate_user",
        "email": "user2@example.com",
        "password": "Password123!",
        "full_name": "Second User",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 400
    assert "Username already taken" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_user_registration_duplicate_email(client: AsyncClient):
    payload1 = {
        "username": "user_one",
        "email": "same_email@example.com",
        "password": "Password123!",
        "full_name": "User One",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "username": "user_two",
        "email": "same_email@example.com",
        "password": "Password123!",
        "full_name": "User Two",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 400
    assert "Email already registered" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_user_registration_validation(client: AsyncClient):
    # Short password (< 8 chars)
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "short_pass",
            "email": "valid@example.com",
            "password": "short",
            "full_name": "Short Pass User",
        },
    )
    assert res.status_code == 422

    # Invalid email
    res2 = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "invalid_email_user",
            "email": "not-an-email",
            "password": "Password123!",
            "full_name": "Invalid Email",
        },
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_user_login_success(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "coder1",
            "email": "coder1@example.com",
            "password": "SecretPassword123!",
            "full_name": "Competitive Coder",
        },
    )

    # Login with username
    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "coder1",
            "password": "SecretPassword123!",
        },
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 900

    # Login with email
    login_email_res = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "coder1@example.com",
            "password": "SecretPassword123!",
        },
    )
    assert login_email_res.status_code == 200


@pytest.mark.asyncio
async def test_user_login_invalid_credentials(client: AsyncClient):
    # Non-existent user
    res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "unknown_user", "password": "Password123!"},
    )
    assert res.status_code == 401

    # Wrong password
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "coder2",
            "email": "coder2@example.com",
            "password": "CorrectPassword123!",
            "full_name": "Competitive Coder 2",
        },
    )
    wrong_res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "coder2", "password": "WrongPassword123!"},
    )
    assert wrong_res.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh_rotation(client: AsyncClient):
    # Register & Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "refresh_tester",
            "email": "refresh@example.com",
            "password": "Password123!",
            "full_name": "Refresh Tester",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "refresh_tester", "password": "Password123!"},
    )
    first_tokens = login_res.json()
    r1 = first_tokens["refresh_token"]

    # Rotate token
    rotate_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": r1},
    )
    assert rotate_res.status_code == 200
    second_tokens = rotate_res.json()
    r2 = second_tokens["refresh_token"]
    assert r1 != r2

    # Use second token -> should succeed
    rotate_res2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": r2},
    )
    assert rotate_res2.status_code == 200

    # Replay attack: Reuse first already-rotated token -> should trigger replay revocation!
    replay_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": r1},
    )
    assert replay_res.status_code == 401
    assert "replay" in replay_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_authenticated_me_profile(client: AsyncClient):
    # Unauthenticated -> 401
    res_unauth = await client.get("/api/v1/auth/me")
    assert res_unauth.status_code == 401

    # Register & Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "profile_user",
            "email": "profile@example.com",
            "password": "Password123!",
            "full_name": "Profile User",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "profile_user", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    # Authenticated -> 200
    headers = {"Authorization": f"Bearer {token}"}
    res_auth = await client.get("/api/v1/auth/me", headers=headers)
    assert res_auth.status_code == 200
    profile = res_auth.json()
    assert profile["username"] == "profile_user"
    assert profile["email"] == "profile@example.com"
    assert "PARTICIPANT" in profile["roles"]


@pytest.mark.asyncio
async def test_logout_revocation(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "logout_user",
            "email": "logout@example.com",
            "password": "Password123!",
            "full_name": "Logout User",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "logout_user", "password": "Password123!"},
    )
    tokens = login_res.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Logout
    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": refresh},
    )
    assert logout_res.status_code == 200
    assert "logged out" in logout_res.json()["message"].lower()

    # Attempting to use the revoked refresh token -> 401 replay/revoked
    attempt_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert attempt_res.status_code == 401
