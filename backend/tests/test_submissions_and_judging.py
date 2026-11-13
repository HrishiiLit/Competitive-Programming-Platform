from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contest import Contest, ContestProblem, ContestRegistration
from app.models.problem import Problem, ProblemVersion, TestCase
from app.models.submission import OutboxEvent, Submission, SubmissionRun
from app.models.user import Language, User
from app.services.auth.service import AuthService
from app.services.judging.comparator import compare_outputs, normalize_output
from app.services.judging.judge0 import Judge0Provider
from app.services.judging.provider import (
    JudgeProvider,
    VERDICT_AC,
    VERDICT_CE,
    VERDICT_IE,
    VERDICT_MLE,
    VERDICT_OLE,
    VERDICT_RE,
    VERDICT_TLE,
    VERDICT_WA,
    get_verdict_priority,
)
from app.services.judging.service import JudgingService
from app.services.submissions.service import (
    ContestRegistrationError,
    ContestWindowError,
    RateLimitExceeded,
    SubmissionService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MockJudgeProvider(JudgeProvider):
    """In-memory mock judge provider for fast unit/integration testing."""

    def __init__(self, secret: str = "mock_secret"):
        self.secret = secret.encode("utf-8")
        self.submissions_store: Dict[str, Dict[str, Any]] = {}

    def sign_payload(self, payload_bytes: bytes) -> str:
        import hashlib
        import hmac
        return hmac.new(self.secret, payload_bytes, hashlib.sha256).hexdigest()

    def verify_callback_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        if not signature_header:
            return False
        import hmac
        expected = self.sign_payload(payload_bytes)
        return hmac.compare_digest(expected, signature_header.strip())

    def map_status_id(self, status_id: int) -> str:
        return Judge0Provider.map_status_id(status_id)

    async def create_batch(self, executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        batch = []
        for i, exec_item in enumerate(executions):
            token = f"mock_tok_{uuid.uuid4().hex[:8]}"
            self.submissions_store[token] = {
                "token": token,
                "status_id": 3,  # AC
                "stdout": exec_item.get("expected_output", ""),
                "time": "0.05",
                "memory": 1024,
            }
            batch.append({"token": token})
        return batch

    async def get_submission(self, token: str) -> Dict[str, Any]:
        return self.submissions_store.get(token, {"token": token, "status_id": 13})

    async def get_submissions_batch(self, tokens: List[str]) -> List[Dict[str, Any]]:
        return [self.submissions_store.get(t, {"token": t, "status_id": 13}) for t in tokens]


@pytest_asyncio.fixture
async def sample_language(db_session: AsyncSession) -> Language:
    lang = Language(
        id=uuid.uuid4(),
        judge0_language_id=54,
        name="C++ (GCC 9.2.0)",
        version="9.2.0",
        extension="cpp",
        enabled=True,
    )
    db_session.add(lang)
    await db_session.commit()
    await db_session.refresh(lang)
    return lang


@pytest_asyncio.fixture
async def organizer_user(db_session: AsyncSession) -> User:
    return await AuthService.register_user(
        db=db_session,
        username="organizer_test",
        email="org@test.com",
        password="Password123!",
        full_name="Contest Organizer",
        roles=["ORGANIZER"],
    )


@pytest_asyncio.fixture
async def participant_user(db_session: AsyncSession) -> User:
    return await AuthService.register_user(
        db=db_session,
        username="coder_test",
        email="coder@test.com",
        password="Password123!",
        full_name="Contest Coder",
        roles=["PARTICIPANT"],
    )


@pytest_asyncio.fixture
async def participant_token(client: AsyncClient, participant_user: User) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": participant_user.username, "password": "Password123!"},
    )
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def organizer_token(client: AsyncClient, organizer_user: User) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": organizer_user.username, "password": "Password123!"},
    )
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def sample_problem(db_session: AsyncSession, organizer_user: User) -> Problem:
    prob_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    now = utc_now()

    prob = Problem(
        id=prob_id,
        code="SUM_TWO",
        author_id=organizer_user.id,
        current_version_id=ver_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(prob)

    version = ProblemVersion(
        id=ver_id,
        problem_id=prob_id,
        version_number=1,
        title="Sum Two Numbers",
        statement_markdown="Given A and B, print A + B.",
        time_limit_ms=1000,
        memory_limit_mb=256,
        is_published=True,
        created_at=now,
    )
    db_session.add(version)

    tc1 = TestCase(
        id=uuid.uuid4(),
        problem_version_id=ver_id,
        order_num=1,
        input_data="1 2\n",
        expected_output="3\n",
        is_sample=True,
        points=50,
        created_at=now,
    )
    tc2 = TestCase(
        id=uuid.uuid4(),
        problem_version_id=ver_id,
        order_num=2,
        input_data="10 20\n",
        expected_output="30\n",
        is_sample=False,
        points=50,
        created_at=now,
    )
    db_session.add_all([tc1, tc2])

    await db_session.commit()
    await db_session.refresh(prob)
    return prob


# ============================================================================
# 1. Output Comparator Tests
# ============================================================================

def test_output_comparator_crlf_and_whitespace():
    # CRLF vs LF
    assert compare_outputs("1 2\r\n3\r\n", "1 2\n3\n")
    # Trailing line spaces
    assert compare_outputs("1 2   \n3  ", "1 2\n3")
    # Trailing empty lines
    assert compare_outputs("hello\n\n\n", "hello")
    # Mixed CRLF and spaces
    assert compare_outputs("result: 42   \r\n\r\n", "result: 42")
    # Unequal outputs
    assert not compare_outputs("1 2", "1 3")
    # Leading whitespace difference should NOT match
    assert not compare_outputs("  42\n", "42\n")


# ============================================================================
# 2. Verdict Priority Matrix Tests
# ============================================================================

def test_verdict_priority_indices():
    assert get_verdict_priority(VERDICT_IE) < get_verdict_priority(VERDICT_CE)
    assert get_verdict_priority(VERDICT_CE) < get_verdict_priority(VERDICT_TLE)
    assert get_verdict_priority(VERDICT_TLE) < get_verdict_priority(VERDICT_MLE)
    assert get_verdict_priority(VERDICT_MLE) < get_verdict_priority(VERDICT_OLE)
    assert get_verdict_priority(VERDICT_OLE) < get_verdict_priority(VERDICT_RE)
    assert get_verdict_priority(VERDICT_RE) < get_verdict_priority(VERDICT_WA)
    assert get_verdict_priority(VERDICT_WA) < get_verdict_priority(VERDICT_AC)


@pytest.mark.asyncio
async def test_verdict_aggregation_priority(db_session: AsyncSession, sample_problem: Problem, participant_user: User, sample_language: Language):
    # Setup a dummy submission
    sub = Submission(
        id=uuid.uuid4(),
        problem_id=sample_problem.id,
        problem_version_id=sample_problem.current_version_id,
        user_id=participant_user.id,
        language_id=sample_language.id,
        source_code="print(1)",
        verdict="RUNNING",
    )
    db_session.add(sub)
    await db_session.commit()

    tc_a = TestCase(id=uuid.uuid4(), problem_version_id=sample_problem.current_version_id, order_num=1)
    tc_b = TestCase(id=uuid.uuid4(), problem_version_id=sample_problem.current_version_id, order_num=2)

    # 1. 100% AC
    runs_ac = [
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_a.id, verdict=VERDICT_AC, execution_time_ms=10, test_case=tc_a),
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_b.id, verdict=VERDICT_AC, execution_time_ms=20, test_case=tc_b),
    ]
    res = await JudgingService.aggregate_verdicts(db_session, sub.id, runs_ac)
    assert res.verdict == VERDICT_AC
    assert res.failed_test_case_num is None
    assert res.execution_time_ms == 20

    # 2. WA on test 2
    runs_wa = [
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_a.id, verdict=VERDICT_AC, execution_time_ms=10, test_case=tc_a),
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_b.id, verdict=VERDICT_WA, execution_time_ms=15, test_case=tc_b),
    ]
    res = await JudgingService.aggregate_verdicts(db_session, sub.id, runs_wa)
    assert res.verdict == VERDICT_WA
    assert res.failed_test_case_num == 2

    # 3. First failing test order: test 1 failed with TLE, test 2 with WA
    runs_first_fail = [
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_a.id, verdict=VERDICT_TLE, execution_time_ms=1000, test_case=tc_a),
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_b.id, verdict=VERDICT_WA, execution_time_ms=50, test_case=tc_b),
    ]
    res = await JudgingService.aggregate_verdicts(db_session, sub.id, runs_first_fail)
    assert res.verdict == VERDICT_TLE
    assert res.failed_test_case_num == 1

    # 4. CE overrides execution errors
    runs_ce = [
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_a.id, verdict=VERDICT_CE, execution_time_ms=0, test_case=tc_a),
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_b.id, verdict=VERDICT_WA, execution_time_ms=50, test_case=tc_b),
    ]
    res = await JudgingService.aggregate_verdicts(db_session, sub.id, runs_ce)
    assert res.verdict == VERDICT_CE

    # 5. IE overrides CE and everything
    runs_ie = [
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_a.id, verdict=VERDICT_CE, execution_time_ms=0, test_case=tc_a),
        SubmissionRun(id=uuid.uuid4(), submission_id=sub.id, test_case_id=tc_b.id, verdict=VERDICT_IE, execution_time_ms=0, test_case=tc_b),
    ]
    res = await JudgingService.aggregate_verdicts(db_session, sub.id, runs_ie)
    assert res.verdict == VERDICT_IE


# ============================================================================
# 3. Submission Ingestion & Transactional Outbox Tests
# ============================================================================

@pytest.mark.asyncio
async def test_submission_ingestion_and_outbox_atomicity(
    db_session: AsyncSession,
    sample_problem: Problem,
    participant_user: User,
    sample_language: Language,
):
    sub = await SubmissionService.create_submission(
        db=db_session,
        user_id=participant_user.id,
        problem_id=sample_problem.id,
        language_id=sample_language.id,
        source_code="#include <iostream>\nint main(){ return 0; }",
        client_ip="127.0.0.1",
    )
    assert sub.id is not None
    assert sub.verdict == "PENDING"

    # Verify OutboxEvent exists in DB
    outbox_stmt = select(OutboxEvent).where(OutboxEvent.aggregate_id == str(sub.id))
    outbox_event = (await db_session.execute(outbox_stmt)).scalar_one_or_none()
    assert outbox_event is not None
    assert outbox_event.event_type == "submission.created"
    assert outbox_event.aggregate_type == "submission"
    assert outbox_event.status == "PENDING"
    assert outbox_event.payload["submission_id"] == str(sub.id)
    assert outbox_event.payload["user_id"] == str(participant_user.id)


# ============================================================================
# 4. Rate Limiting Tests
# ============================================================================

@pytest.mark.asyncio
async def test_submission_rate_limiting(
    db_session: AsyncSession,
    sample_problem: Problem,
    participant_user: User,
    sample_language: Language,
):
    # 1. First submission succeeds
    await SubmissionService.create_submission(
        db=db_session,
        user_id=participant_user.id,
        problem_id=sample_problem.id,
        language_id=sample_language.id,
        source_code="first attempt",
    )

    # 2. Immediate second submission to same problem must raise RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        await SubmissionService.create_submission(
            db=db_session,
            user_id=participant_user.id,
            problem_id=sample_problem.id,
            language_id=sample_language.id,
            source_code="second attempt too fast",
        )
    assert "rate limit exceeded" in str(exc_info.value).lower()


# ============================================================================
# 5. Contest Window & Registration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_contest_submission_window_and_registration(
    db_session: AsyncSession,
    organizer_user: User,
    participant_user: User,
    sample_problem: Problem,
    sample_language: Language,
):
    now = utc_now()

    # Contest 1: UPCOMING contest
    upcoming_contest = Contest(
        id=uuid.uuid4(),
        title="Upcoming Contest",
        slug="upcoming-contest",
        organizer_id=organizer_user.id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        status="UPCOMING",
    )
    db_session.add(upcoming_contest)
    cp1 = ContestProblem(id=uuid.uuid4(), contest_id=upcoming_contest.id, problem_id=sample_problem.id, order_letter="A")
    reg1 = ContestRegistration(id=uuid.uuid4(), contest_id=upcoming_contest.id, user_id=participant_user.id, approved=True)
    db_session.add_all([cp1, reg1])

    # Contest 2: COMPLETED contest
    completed_contest = Contest(
        id=uuid.uuid4(),
        title="Finished Contest",
        slug="finished-contest",
        organizer_id=organizer_user.id,
        start_time=now - timedelta(hours=4),
        end_time=now - timedelta(hours=2),
        status="COMPLETED",
    )
    db_session.add(completed_contest)
    cp2 = ContestProblem(id=uuid.uuid4(), contest_id=completed_contest.id, problem_id=sample_problem.id, order_letter="A")
    reg2 = ContestRegistration(id=uuid.uuid4(), contest_id=completed_contest.id, user_id=participant_user.id, approved=True)
    db_session.add_all([cp2, reg2])

    # Contest 3: ACTIVE contest
    active_contest = Contest(
        id=uuid.uuid4(),
        title="Active Contest",
        slug="active-contest",
        organizer_id=organizer_user.id,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(hours=2),
        status="ACTIVE",
    )
    db_session.add(active_contest)
    cp3 = ContestProblem(id=uuid.uuid4(), contest_id=active_contest.id, problem_id=sample_problem.id, order_letter="A")
    db_session.add(cp3)

    await db_session.commit()

    # Attempt submission to UPCOMING contest -> rejected
    with pytest.raises(ContestWindowError):
        await SubmissionService.create_submission(
            db=db_session,
            user_id=participant_user.id,
            problem_id=sample_problem.id,
            language_id=sample_language.id,
            source_code="code",
            contest_id=upcoming_contest.id,
        )

    # Attempt submission to COMPLETED contest -> rejected
    with pytest.raises(ContestWindowError):
        await SubmissionService.create_submission(
            db=db_session,
            user_id=participant_user.id,
            problem_id=sample_problem.id,
            language_id=sample_language.id,
            source_code="code",
            contest_id=completed_contest.id,
        )

    # Attempt submission to ACTIVE contest WITHOUT registration -> rejected
    with pytest.raises(ContestRegistrationError):
        await SubmissionService.create_submission(
            db=db_session,
            user_id=participant_user.id,
            problem_id=sample_problem.id,
            language_id=sample_language.id,
            source_code="code",
            contest_id=active_contest.id,
        )

    # Register user to active contest -> now submission succeeds
    reg3 = ContestRegistration(id=uuid.uuid4(), contest_id=active_contest.id, user_id=participant_user.id, approved=True)
    db_session.add(reg3)
    await db_session.commit()

    sub = await SubmissionService.create_submission(
        db=db_session,
        user_id=participant_user.id,
        problem_id=sample_problem.id,
        language_id=sample_language.id,
        source_code="code",
        contest_id=active_contest.id,
    )
    assert sub.contest_id == active_contest.id


# ============================================================================
# 6. Mocked Judge0 Dispatch, HMAC Webhook & Polling Flow
# ============================================================================

@pytest.mark.asyncio
async def test_judging_dispatch_callback_and_polling(
    db_session: AsyncSession,
    sample_problem: Problem,
    participant_user: User,
    sample_language: Language,
):
    provider = MockJudgeProvider(secret="super_secret_test_key")

    # 1. Create submission
    sub = await SubmissionService.create_submission(
        db=db_session,
        user_id=participant_user.id,
        problem_id=sample_problem.id,
        language_id=sample_language.id,
        source_code="main() {}",
    )

    # 2. Dispatch submission
    runs = await JudgingService.dispatch_submission(db_session, sub.id, provider)
    assert len(runs) == 2
    assert sub.verdict == "RUNNING"
    for r in runs:
        assert r.judge0_token.startswith("mock_tok_")
        assert r.verdict == "RUNNING"

    # 3. Process HMAC callback for testcase 1
    run1 = runs[0]
    payload1 = {
        "token": run1.judge0_token,
        "status_id": 3,  # AC
        "stdout": "3\n",
        "time": "0.020",
        "memory": 2048,
    }
    raw_bytes1 = str(payload1).encode("utf-8")
    sig1 = provider.sign_payload(raw_bytes1)

    # Invalid signature check
    with pytest.raises(ValueError):
        await JudgingService.handle_judge_callback(
            db=db_session,
            raw_body=raw_bytes1,
            signature_header="wrong_signature",
            payload=payload1,
            provider=provider,
        )

    # Valid signature for run 1
    updated_run1 = await JudgingService.handle_judge_callback(
        db=db_session,
        raw_body=raw_bytes1,
        signature_header=sig1,
        payload=payload1,
        provider=provider,
    )
    assert updated_run1.verdict == VERDICT_AC
    assert updated_run1.execution_time_ms == 20
    # Submission is still RUNNING because run 2 is pending
    await db_session.refresh(sub)
    assert sub.verdict == "RUNNING"

    # 4. Simulate Polling Fallback for run 2 (recovers dropped webhook)
    run2 = runs[1]
    # Set mock provider's stored result for run 2
    provider.submissions_store[run2.judge0_token] = {
        "token": run2.judge0_token,
        "status_id": 3,
        "stdout": "30\n",
        "time": "0.035",
        "memory": 4096,
    }
    polled_sub = await JudgingService.poll_pending_submission(db_session, sub.id, provider)
    assert polled_sub.verdict == VERDICT_AC
    assert polled_sub.execution_time_ms == 35
    assert polled_sub.execution_memory_kb == 4096


# ============================================================================
# 7. REST Endpoints Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_submission_api_endpoints(
    client: AsyncClient,
    participant_token: str,
    organizer_token: str,
    sample_problem: Problem,
    sample_language: Language,
):
    part_headers = {"Authorization": f"Bearer {participant_token}"}
    org_headers = {"Authorization": f"Bearer {organizer_token}"}

    # 1. POST /api/v1/submissions
    create_res = await client.post(
        "/api/v1/submissions",
        json={
            "problem_id": str(sample_problem.id),
            "language_id": str(sample_language.id),
            "source_code": "#include <iostream>\nint main(){ std::cout << 3 << std::endl; }",
        },
        headers=part_headers,
    )
    assert create_res.status_code == 201
    sub_data = create_res.json()
    sub_id = sub_data["id"]
    assert sub_data["verdict"] == "PENDING"
    assert sub_data["problem_id"] == str(sample_problem.id)

    # 2. Rate limiting check via API (immediate second submission -> 429)
    rate_res = await client.post(
        "/api/v1/submissions",
        json={
            "problem_id": str(sample_problem.id),
            "language_id": str(sample_language.id),
            "source_code": "print(2)",
        },
        headers=part_headers,
    )
    assert rate_res.status_code == 429

    # 3. GET /api/v1/submissions/{id}
    get_res = await client.get(f"/api/v1/submissions/{sub_id}", headers=part_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sub_id

    # 4. GET /api/v1/submissions
    list_res = await client.get("/api/v1/submissions", headers=part_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1


@pytest.mark.asyncio
async def test_judge0_webhook_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_problem: Problem,
    participant_user: User,
    sample_language: Language,
):
    provider = Judge0Provider()

    # Create submission and a run with known token
    sub = Submission(
        id=uuid.uuid4(),
        problem_id=sample_problem.id,
        problem_version_id=sample_problem.current_version_id,
        user_id=participant_user.id,
        language_id=sample_language.id,
        source_code="code",
        verdict="RUNNING",
    )
    db_session.add(sub)
    await db_session.commit()

    run = SubmissionRun(
        id=uuid.uuid4(),
        submission_id=sub.id,
        test_case_id=sample_problem.current_version_id,  # dummy reference
        verdict="RUNNING",
        judge0_token="test_webhook_token_123",
        created_at=utc_now(),
    )
    db_session.add(run)
    await db_session.commit()

    import json
    payload = {
        "token": "test_webhook_token_123",
        "status_id": 3,
        "stdout": "output",
        "time": "0.01",
        "memory": 512,
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = provider.sign_payload(raw_bytes)

    # 1. Invalid signature -> 403
    bad_res = await client.post(
        "/api/v1/internal/judge-callbacks",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Judge0-Signature": "invalid_sig"},
    )
    assert bad_res.status_code == 403

    # 2. Valid signature -> 200
    good_res = await client.post(
        "/api/v1/internal/judge-callbacks",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Judge0-Signature": sig},
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "success"
