from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.problem import Problem, ProblemVersion, TestCase
from app.models.submission import Judge0Callback, OutboxEvent, Submission, SubmissionRun
from app.models.user import Language
from app.services.judging.comparator import compare_outputs
from app.services.judging.provider import (
    JudgeProvider,
    VERDICT_AC,
    VERDICT_CE,
    VERDICT_IE,
    VERDICT_MLE,
    VERDICT_OLE,
    VERDICT_PENDING,
    VERDICT_RE,
    VERDICT_RUNNING,
    VERDICT_TLE,
    VERDICT_WA,
    get_verdict_priority,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


TERMINAL_VERDICTS = {
    VERDICT_AC,
    VERDICT_WA,
    VERDICT_TLE,
    VERDICT_MLE,
    VERDICT_OLE,
    VERDICT_RE,
    VERDICT_CE,
    VERDICT_IE,
}


class JudgingService:
    @classmethod
    async def dispatch_submission(
        cls,
        db: AsyncSession,
        submission_id: uuid.UUID,
        provider: JudgeProvider,
        callback_url: Optional[str] = None,
    ) -> List[SubmissionRun]:
        """Dispatch all test cases of a submission in batch to Judge0."""
        stmt = (
            select(Submission)
            .where(Submission.id == submission_id)
            .options(
                selectinload(Submission.problem_version).selectinload(ProblemVersion.test_cases),
                selectinload(Submission.language),
            )
        )
        submission = (await db.execute(stmt)).scalar_one_or_none()
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        version = submission.problem_version
        if not version or not version.test_cases:
            submission.verdict = VERDICT_IE
            submission.judged_at = utc_now()
            submission.compile_output = "No test cases configured for problem"
            await db.commit()
            return []

        # Sort test cases by order_num
        test_cases = sorted(version.test_cases, key=lambda tc: tc.order_num)

        # Prepare batch executions
        executions = []
        for tc in test_cases:
            executions.append({
                "source_code": submission.source_code,
                "judge0_language_id": submission.language.judge0_language_id if submission.language else 54,
                "stdin": tc.input_data or "",
                "expected_output": tc.expected_output or "",
                "time_limit_ms": version.time_limit_ms,
                "memory_limit_mb": version.memory_limit_mb,
                "callback_url": callback_url,
            })

        submission.verdict = VERDICT_RUNNING

        try:
            tokens_response = await provider.create_batch(executions)
        except Exception as e:
            submission.verdict = VERDICT_IE
            submission.judged_at = utc_now()
            submission.compile_output = f"Execution dispatch failed: {str(e)}"
            await db.commit()
            raise

        runs = []
        for i, tc in enumerate(test_cases):
            token_info = tokens_response[i] if i < len(tokens_response) else {}
            token = token_info.get("token")
            run = SubmissionRun(
                id=uuid.uuid4(),
                submission_id=submission.id,
                test_case_id=tc.id,
                verdict=VERDICT_RUNNING,
                execution_time_ms=0,
                execution_memory_kb=0,
                judge0_token=token,
                created_at=utc_now(),
            )
            db.add(run)
            runs.append(run)

        await db.commit()
        return runs

    @classmethod
    async def handle_judge_callback(
        cls,
        db: AsyncSession,
        raw_body: bytes,
        signature_header: Optional[str],
        payload: Dict[str, Any],
        provider: JudgeProvider,
    ) -> Optional[SubmissionRun]:
        """Validate HMAC signature, record callback payload, update run, and aggregate if complete."""
        # 1. Validate signature
        if not provider.verify_callback_signature(raw_body, signature_header):
            raise ValueError("Invalid HMAC-SHA256 callback signature")

        token = payload.get("token")
        if not token:
            raise ValueError("Callback payload missing 'token'")

        status_obj = payload.get("status", {})
        status_id = payload.get("status_id") or status_obj.get("id", 13)

        # 2. Find matching SubmissionRun
        stmt = (
            select(SubmissionRun)
            .where(SubmissionRun.judge0_token == token)
            .options(
                selectinload(SubmissionRun.test_case),
                selectinload(SubmissionRun.submission),
            )
        )
        run = (await db.execute(stmt)).scalar_one_or_none()
        if not run:
            # Store callback record for auditing even if run is not found
            callback_record = Judge0Callback(
                id=uuid.uuid4(),
                judge0_token=token,
                submission_id=uuid.uuid4(),  # placeholder
                status_id=status_id,
                payload=payload,
                processed=False,
                created_at=utc_now(),
            )
            db.add(callback_record)
            await db.commit()
            return None

        # 3. Determine run verdict
        raw_verdict = provider.map_status_id(status_id) if hasattr(provider, "map_status_id") else JudgeProvider.map_status_id(status_id)
        verdict = raw_verdict

        # Evaluate deterministic comparator if stdout available
        stdout = payload.get("stdout")
        if stdout is not None and run.test_case and run.test_case.expected_output is not None:
            if verdict in (VERDICT_AC, VERDICT_WA):
                if compare_outputs(stdout, run.test_case.expected_output):
                    verdict = VERDICT_AC
                else:
                    verdict = VERDICT_WA

        # Extract execution metrics
        time_sec = payload.get("time")
        run.execution_time_ms = int(float(time_sec) * 1000) if time_sec else 0

        mem_kb = payload.get("memory")
        run.execution_memory_kb = int(mem_kb) if mem_kb else 0

        run.verdict = verdict

        # Store compile error output if present
        compile_output = payload.get("compile_output")
        if compile_output and run.submission and not run.submission.compile_output:
            run.submission.compile_output = compile_output

        # Record callback audit
        callback_record = Judge0Callback(
            id=uuid.uuid4(),
            judge0_token=token,
            submission_id=run.submission_id,
            status_id=status_id,
            payload=payload,
            processed=True,
            created_at=utc_now(),
        )
        db.add(callback_record)

        # 4. Check if all runs are complete
        all_runs_stmt = (
            select(SubmissionRun)
            .where(SubmissionRun.submission_id == run.submission_id)
            .options(selectinload(SubmissionRun.test_case))
            .order_by(SubmissionRun.created_at)
        )
        all_runs = (await db.execute(all_runs_stmt)).scalars().all()

        is_all_done = all(r.verdict in TERMINAL_VERDICTS for r in all_runs)
        if is_all_done:
            await cls.aggregate_verdicts(db, run.submission_id, list(all_runs))

        await db.commit()
        return run

    @classmethod
    async def aggregate_verdicts(
        cls,
        db: AsyncSession,
        submission_id: uuid.UUID,
        runs: Optional[List[SubmissionRun]] = None,
    ) -> Submission:
        """Evaluate verdict priority matrix:

        SYSTEM_ERROR > COMPILATION_ERROR > First Failing Test (TLE > MLE > OLE > RE > WA) > ACCEPTED
        """
        stmt = (
            select(Submission)
            .where(Submission.id == submission_id)
            .options(
                selectinload(Submission.runs).selectinload(SubmissionRun.test_case)
            )
        )
        submission = (await db.execute(stmt)).scalar_one_or_none()
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        runs_list = runs if runs is not None else list(submission.runs or [])
        if not runs_list:
            submission.verdict = VERDICT_IE
            submission.judged_at = utc_now()
            return submission

        max_time = max((r.execution_time_ms or 0 for r in runs_list), default=0)
        max_mem = max((r.execution_memory_kb or 0 for r in runs_list), default=0)

        # 1. System error takes absolute precedence
        ie_run = next((r for r in runs_list if r.verdict == VERDICT_IE), None)
        if ie_run:
            submission.verdict = VERDICT_IE
            submission.failed_test_case_num = ie_run.test_case.order_num if ie_run.test_case else None
            submission.execution_time_ms = max_time
            submission.execution_memory_kb = max_mem
            submission.judged_at = utc_now()
            return submission

        # 2. Compilation error aborts testing immediately
        ce_run = next((r for r in runs_list if r.verdict == VERDICT_CE), None)
        if ce_run:
            submission.verdict = VERDICT_CE
            submission.failed_test_case_num = None
            submission.execution_time_ms = max_time
            submission.execution_memory_kb = max_mem
            submission.judged_at = utc_now()
            return submission

        # 3. Check for failing tests
        failing_runs = [r for r in runs_list if r.verdict != VERDICT_AC]
        if not failing_runs:
            # 100% of test cases passed
            submission.verdict = VERDICT_AC
            submission.failed_test_case_num = None
            submission.execution_time_ms = max_time
            submission.execution_memory_kb = max_mem
            submission.judged_at = utc_now()
        else:
            # Sort failing tests: primary by test_case.order_num (first failing test),
            # tie-broken by verdict priority (TLE > MLE > OLE > RE > WA)
            failing_runs.sort(
                key=lambda r: (
                    r.test_case.order_num if (r.test_case and r.test_case.order_num is not None) else 0,
                    get_verdict_priority(r.verdict),
                )
            )
            primary_fail = failing_runs[0]
            submission.verdict = primary_fail.verdict
            submission.failed_test_case_num = primary_fail.test_case.order_num if primary_fail.test_case else None
            submission.execution_time_ms = max_time
            submission.execution_memory_kb = max_mem
            submission.judged_at = utc_now()

        # Record outbox event for judged submission
        outbox_event = OutboxEvent(
            id=uuid.uuid4(),
            event_type="submission.judged",
            aggregate_type="submission",
            aggregate_id=str(submission.id),
            payload={
                "submission_id": str(submission.id),
                "contest_id": str(submission.contest_id) if submission.contest_id else None,
                "problem_id": str(submission.problem_id),
                "user_id": str(submission.user_id),
                "verdict": submission.verdict,
                "execution_time_ms": submission.execution_time_ms,
                "execution_memory_kb": submission.execution_memory_kb,
                "failed_test_case_num": submission.failed_test_case_num,
            },
            status="PENDING",
            retry_count=0,
            created_at=utc_now(),
        )
        db.add(outbox_event)

        return submission

    @classmethod
    async def poll_pending_submission(
        cls,
        db: AsyncSession,
        submission_id: uuid.UUID,
        provider: JudgeProvider,
    ) -> Submission:
        """Poll Judge0 for incomplete runs to recover delayed or dropped callbacks."""
        stmt = (
            select(Submission)
            .where(Submission.id == submission_id)
            .options(
                selectinload(Submission.runs).selectinload(SubmissionRun.test_case)
            )
        )
        submission = (await db.execute(stmt)).scalar_one_or_none()
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        pending_runs = [r for r in submission.runs if r.verdict not in TERMINAL_VERDICTS]
        if not pending_runs:
            if submission.verdict not in TERMINAL_VERDICTS:
                await cls.aggregate_verdicts(db, submission.id, list(submission.runs))
                await db.commit()
            return submission

        tokens = [r.judge0_token for r in pending_runs if r.judge0_token]
        if not tokens:
            return submission

        try:
            batch_results = await provider.get_submissions_batch(tokens)
        except Exception:
            # Fall back to single queries
            batch_results = []
            for token in tokens:
                try:
                    res = await provider.get_submission(token)
                    batch_results.append(res)
                except Exception:
                    pass

        results_by_token = {res.get("token"): res for res in batch_results if res.get("token")}

        for run in pending_runs:
            res = results_by_token.get(run.judge0_token)
            if not res:
                continue

            status_obj = res.get("status", {})
            status_id = res.get("status_id") or status_obj.get("id")
            if not status_id or status_id in (1, 2):  # In Queue or Processing
                continue

            verdict = provider.map_status_id(status_id) if hasattr(provider, "map_status_id") else JudgeProvider.map_status_id(status_id)

            stdout = res.get("stdout")
            if stdout is not None and run.test_case and run.test_case.expected_output is not None:
                if verdict in (VERDICT_AC, VERDICT_WA):
                    if compare_outputs(stdout, run.test_case.expected_output):
                        verdict = VERDICT_AC
                    else:
                        verdict = VERDICT_WA

            time_sec = res.get("time")
            run.execution_time_ms = int(float(time_sec) * 1000) if time_sec else 0

            mem_kb = res.get("memory")
            run.execution_memory_kb = int(mem_kb) if mem_kb else 0

            run.verdict = verdict

            compile_output = res.get("compile_output")
            if compile_output and not submission.compile_output:
                submission.compile_output = compile_output

        # Re-check if all runs are complete
        if all(r.verdict in TERMINAL_VERDICTS for r in submission.runs):
            await cls.aggregate_verdicts(db, submission.id, list(submission.runs))

        await db.commit()
        return submission
