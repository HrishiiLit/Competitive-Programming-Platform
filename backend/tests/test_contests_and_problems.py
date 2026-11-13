from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth.service import AuthService


@pytest_asyncio.fixture
async def organizer_token(client: AsyncClient, db_session: AsyncSession) -> str:
    user = await AuthService.register_user(
        db=db_session,
        username="lead_organizer",
        email="organizer@example.com",
        password="OrganizerPassword123!",
        full_name="Chief Contest Organizer",
        roles=["ORGANIZER"],
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "lead_organizer", "password": "OrganizerPassword123!"},
    )
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def participant_token(client: AsyncClient, db_session: AsyncSession) -> str:
    user = await AuthService.register_user(
        db=db_session,
        username="contest_coder",
        email="coder@example.com",
        password="CoderPassword123!",
        full_name="Contest Participant",
        roles=["PARTICIPANT"],
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "contest_coder", "password": "CoderPassword123!"},
    )
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_server_time_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/contests/time")
    assert res.status_code == 200
    data = res.json()
    assert "server_time" in data
    assert "timestamp" in data
    assert data["timestamp"] > 0


@pytest.mark.asyncio
async def test_problem_creation_and_versioning(
    client: AsyncClient,
    organizer_token: str,
):
    headers = {"Authorization": f"Bearer {organizer_token}"}

    # 1. Create problem
    payload = {
        "code": "TWO_SUM",
        "title": "Two Sum Problem",
        "statement_markdown": "# Two Sum\nFind two numbers summing to target.",
        "time_limit_ms": 1000,
        "memory_limit_mb": 256,
        "input_format": "N followed by N integers",
        "output_format": "Two indices",
    }
    create_res = await client.post("/api/v1/problems", json=payload, headers=headers)
    assert create_res.status_code == 201
    prob = create_res.json()
    assert prob["code"] == "TWO_SUM"
    assert prob["current_version"]["title"] == "Two Sum Problem"
    assert prob["current_version"]["version_number"] == 1
    prob_id = prob["id"]

    # 2. Add version 2
    ver_payload = {
        "title": "Two Sum (Clarified Statement)",
        "statement_markdown": "# Two Sum Revised\n1-indexed indices.",
        "time_limit_ms": 2000,
        "memory_limit_mb": 512,
    }
    ver_res = await client.post(f"/api/v1/problems/{prob_id}/versions", json=ver_payload, headers=headers)
    assert ver_res.status_code == 201
    v2 = ver_res.json()
    assert v2["version_number"] == 2
    assert v2["title"] == "Two Sum (Clarified Statement)"


@pytest.mark.asyncio
async def test_testcase_management_and_confidentiality(
    client: AsyncClient,
    organizer_token: str,
    participant_token: str,
):
    org_headers = {"Authorization": f"Bearer {organizer_token}"}
    part_headers = {"Authorization": f"Bearer {participant_token}"}

    # Create problem
    create_res = await client.post(
        "/api/v1/problems",
        json={
            "code": "SORT_ARRAY",
            "title": "Sort an Array",
            "statement_markdown": "Sort N numbers ascending.",
        },
        headers=org_headers,
    )
    prob_data = create_res.json()
    prob_id = prob_data["id"]
    version_id = prob_data["current_version_id"]

    # Add sample testcase
    await client.post(
        f"/api/v1/problems/{prob_id}/versions/{version_id}/testcases",
        json={
            "input_data": "3\n3 1 2\n",
            "expected_output": "1 2 3\n",
            "is_sample": True,
            "explanation": "Sample array sorted.",
        },
        headers=org_headers,
    )

    # Add hidden testcase
    await client.post(
        f"/api/v1/problems/{prob_id}/versions/{version_id}/testcases",
        json={
            "input_data": "100000\n[giant input]\n",
            "expected_output": "[giant output]\n",
            "is_sample": False,
            "points": 50,
        },
        headers=org_headers,
    )

    # Participant fetches testcases -> MUST ONLY see sample testcase!
    p_res = await client.get(
        f"/api/v1/problems/{prob_id}/versions/{version_id}/testcases",
        headers=part_headers,
    )
    assert p_res.status_code == 200
    p_tests = p_res.json()
    assert len(p_tests) == 1
    assert p_tests[0]["is_sample"] is True
    assert p_tests[0]["explanation"] == "Sample array sorted."

    # Staff fetches testcases -> Sees both sample and hidden testcases
    o_res = await client.get(
        f"/api/v1/problems/{prob_id}/versions/{version_id}/testcases",
        headers=org_headers,
    )
    assert o_res.status_code == 200
    o_tests = o_res.json()
    assert len(o_tests) == 2


@pytest.mark.asyncio
async def test_contest_creation_validation_and_registration(
    client: AsyncClient,
    organizer_token: str,
    participant_token: str,
):
    org_headers = {"Authorization": f"Bearer {organizer_token}"}
    part_headers = {"Authorization": f"Bearer {participant_token}"}

    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=3)
    freeze = now + timedelta(hours=2)

    # Invalid start >= end
    invalid_res = await client.post(
        "/api/v1/contests",
        json={
            "title": "Invalid Contest",
            "slug": "invalid-contest",
            "start_time": end.isoformat(),
            "end_time": start.isoformat(),
        },
        headers=org_headers,
    )
    assert invalid_res.status_code == 400

    # Valid contest creation
    valid_res = await client.post(
        "/api/v1/contests",
        json={
            "title": "Spring Code Cup 2026",
            "slug": "spring-code-cup-2026",
            "description": "Annual algorithm competition.",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "freeze_time": freeze.isoformat(),
            "rules_type": "ICPC",
        },
        headers=org_headers,
    )
    assert valid_res.status_code == 201
    contest = valid_res.json()
    assert contest["slug"] == "spring-code-cup-2026"
    assert contest["status"] == "UPCOMING"
    contest_id = contest["id"]

    # Participant registration
    reg_res = await client.post(
        f"/api/v1/contests/{contest_id}/register",
        headers=part_headers,
    )
    assert reg_res.status_code == 200
    assert reg_res.json()["approved"] is True

    # Duplicate registration idempotency
    reg_res2 = await client.post(
        f"/api/v1/contests/{contest_id}/register",
        headers=part_headers,
    )
    assert reg_res2.status_code == 200


@pytest.mark.asyncio
async def test_contest_problem_assignment_and_confidentiality_guard(
    client: AsyncClient,
    organizer_token: str,
    participant_token: str,
):
    org_headers = {"Authorization": f"Bearer {organizer_token}"}
    part_headers = {"Authorization": f"Bearer {participant_token}"}

    # 1. Create 2 problems
    p1 = (await client.post(
        "/api/v1/problems",
        json={"code": "PROB_A", "title": "Problem Alpha", "statement_markdown": "Alpha text"},
        headers=org_headers,
    )).json()

    p2 = (await client.post(
        "/api/v1/problems",
        json={"code": "PROB_B", "title": "Problem Beta", "statement_markdown": "Beta text"},
        headers=org_headers,
    )).json()

    # 2. Create upcoming contest
    now = datetime.now(timezone.utc)
    contest = (await client.post(
        "/api/v1/contests",
        json={
            "title": "Confidential Cup",
            "slug": "confidential-cup",
            "start_time": (now + timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=4)).isoformat(),
        },
        headers=org_headers,
    )).json()
    contest_id = contest["id"]

    # 3. Add problems with order letters
    cp1 = await client.post(
        f"/api/v1/contests/{contest_id}/problems",
        json={"problem_id": p1["id"], "order_letter": "A", "points": 1},
        headers=org_headers,
    )
    assert cp1.status_code == 201

    cp2 = await client.post(
        f"/api/v1/contests/{contest_id}/problems",
        json={"problem_id": p2["id"], "order_letter": "B", "points": 2},
        headers=org_headers,
    )
    assert cp2.status_code == 201

    # Duplicate order letter rejection
    dup_res = await client.post(
        f"/api/v1/contests/{contest_id}/problems",
        json={"problem_id": p2["id"], "order_letter": "A"},
        headers=org_headers,
    )
    assert dup_res.status_code == 400

    # 4. Confidentiality check: Participant tries to view problems before start_time -> 403 Forbidden
    part_view = await client.get(
        f"/api/v1/contests/{contest_id}/problems",
        headers=part_headers,
    )
    assert part_view.status_code == 403
    assert "confidential" in part_view.json()["detail"].lower()

    # Organizer CAN view problems before start_time
    org_view = await client.get(
        f"/api/v1/contests/{contest_id}/problems",
        headers=org_headers,
    )
    assert org_view.status_code == 200
    assert len(org_view.json()) == 2


@pytest.mark.asyncio
async def test_problem_immutability_on_active_contest(
    client: AsyncClient,
    organizer_token: str,
):
    org_headers = {"Authorization": f"Bearer {organizer_token}"}

    # Create problem
    prob = (await client.post(
        "/api/v1/problems",
        json={"code": "IMMUTABLE_PROB", "title": "Immutable Problem", "statement_markdown": "Solve this."},
        headers=org_headers,
    )).json()
    prob_id = prob["id"]
    version_id = prob["current_version_id"]

    # Create currently ACTIVE contest (start_time in past, end_time in future)
    now = datetime.now(timezone.utc)
    active_contest = (await client.post(
        "/api/v1/contests",
        json={
            "title": "Live Championship",
            "slug": "live-championship",
            "start_time": (now - timedelta(minutes=30)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "status": "ACTIVE",
        },
        headers=org_headers,
    )).json()

    # Add problem to the active contest
    await client.post(
        f"/api/v1/contests/{active_contest['id']}/problems",
        json={"problem_id": prob_id, "order_letter": "A"},
        headers=org_headers,
    )

    # Attempting to mutate or add a testcase to this problem version MUST fail with 409 Conflict
    mutate_res = await client.post(
        f"/api/v1/problems/{prob_id}/versions/{version_id}/testcases",
        json={"input_data": "test\n", "expected_output": "out\n"},
        headers=org_headers,
    )
    assert mutate_res.status_code == 409
    assert "immutable" in mutate_res.json()["detail"].lower() or "locked" in mutate_res.json()["detail"].lower()
