import base64
import hashlib
import hmac
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
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
)

# Judge0 CE status ID mappings
JUDGE0_STATUS_MAP = {
    1: VERDICT_PENDING,  # In Queue
    2: VERDICT_RUNNING,  # Processing
    3: VERDICT_AC,       # Accepted
    4: VERDICT_WA,       # Wrong Answer
    5: VERDICT_TLE,      # Time Limit Exceeded
    6: VERDICT_CE,       # Compilation Error
    7: VERDICT_RE,       # Runtime Error (SIGSEGV)
    8: VERDICT_OLE,      # Runtime Error (SIGXFSZ)
    9: VERDICT_RE,       # Runtime Error (SIGFPE)
    10: VERDICT_RE,      # Runtime Error (SIGABRT)
    11: VERDICT_RE,      # Runtime Error (NZEC)
    12: VERDICT_RE,      # Runtime Error (Other)
    13: VERDICT_IE,      # Internal Error
    14: VERDICT_IE,      # Exec Format Error
}


def encode_b64(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def decode_b64(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    try:
        return base64.b64decode(text.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return text


class Judge0Provider(JudgeProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        callback_secret: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.JUDGE0_URL).rstrip("/")
        self.callback_secret = (callback_secret or settings.JUDGE0_CALLBACK_SECRET).encode("utf-8")
        self.timeout_seconds = timeout_seconds or settings.JUDGE0_TIMEOUT_SECONDS

    def sign_payload(self, payload_bytes: bytes) -> str:
        """Generate HMAC-SHA256 signature for outgoing / test callbacks."""
        return hmac.new(self.callback_secret, payload_bytes, hashlib.sha256).hexdigest()

    def verify_callback_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Validate incoming callback webhook against shared secret."""
        if not signature_header:
            return False
        expected_sig = self.sign_payload(payload_bytes)
        return hmac.compare_digest(expected_sig, signature_header.strip())

    @staticmethod
    def map_status_id(status_id: int) -> str:
        return JUDGE0_STATUS_MAP.get(status_id, VERDICT_IE)

    async def create_batch(self, executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Submit a batch of executions to Judge0 with base64 encoded payload."""
        submissions_payload = []
        for item in executions:
            sub = {
                "source_code": encode_b64(item.get("source_code", "")),
                "language_id": item.get("judge0_language_id", 54),  # Default C++ GCC
                "stdin": encode_b64(item.get("stdin", "")),
                "expected_output": encode_b64(item.get("expected_output", "")),
                "cpu_time_limit": item.get("time_limit_ms", 1000) / 1000.0,
                "memory_limit": item.get("memory_limit_mb", 256) * 1024,  # KB
            }
            if item.get("callback_url"):
                sub["callback_url"] = item["callback_url"]
            submissions_payload.append(sub)

        url = f"{self.base_url}/submissions/batch?base64_encoded=true"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, json={"submissions": submissions_payload})
            resp.raise_for_status()
            return resp.json()

    async def get_submission(self, token: str) -> Dict[str, Any]:
        """Fetch single submission result from Judge0."""
        url = f"{self.base_url}/submissions/{token}?base64_encoded=true"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            # Decode b64 outputs
            if "stdout" in data:
                data["stdout"] = decode_b64(data["stdout"])
            if "stderr" in data:
                data["stderr"] = decode_b64(data["stderr"])
            if "compile_output" in data:
                data["compile_output"] = decode_b64(data["compile_output"])
            return data

    async def get_submissions_batch(self, tokens: List[str]) -> List[Dict[str, Any]]:
        """Fetch batch results from Judge0."""
        if not tokens:
            return []
        token_str = ",".join(tokens)
        url = f"{self.base_url}/submissions/batch?tokens={token_str}&base64_encoded=true"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw_batch = resp.json().get("submissions", [])
            for data in raw_batch:
                if "stdout" in data:
                    data["stdout"] = decode_b64(data["stdout"])
                if "stderr" in data:
                    data["stderr"] = decode_b64(data["stderr"])
                if "compile_output" in data:
                    data["compile_output"] = decode_b64(data["compile_output"])
            return raw_batch
