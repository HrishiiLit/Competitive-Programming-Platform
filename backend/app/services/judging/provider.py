from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Canonical domain verdicts (docs/judging.md section 5)
VERDICT_AC = "AC"      # Accepted (100% test cases pass)
VERDICT_WA = "WA"      # Wrong Answer
VERDICT_TLE = "TLE"    # Time Limit Exceeded
VERDICT_MLE = "MLE"    # Memory Limit Exceeded
VERDICT_OLE = "OLE"    # Output Limit Exceeded
VERDICT_RE = "RE"      # Runtime Error
VERDICT_CE = "CE"      # Compilation Error
VERDICT_IE = "IE"      # Internal / System Error
VERDICT_PENDING = "PENDING"
VERDICT_RUNNING = "RUNNING"

# Priority rank when aggregating multiple test cases:
# Lower index = higher priority precedence
VERDICT_PRIORITY = [
    VERDICT_IE,   # Infrastructure/System error takes absolute precedence
    VERDICT_CE,   # Compilation error aborts testing immediately
    VERDICT_TLE,  # First failing execution error
    VERDICT_MLE,
    VERDICT_OLE,
    VERDICT_RE,
    VERDICT_WA,
    VERDICT_AC,
]


def get_verdict_priority(verdict: str) -> int:
    try:
        return VERDICT_PRIORITY.index(verdict)
    except ValueError:
        return 999


class JudgeProvider(ABC):
    """Abstract interface for external code execution engines."""

    @abstractmethod
    async def create_batch(self, executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Submit a batch of test executions to the judging engine.

        Returns list of objects containing token references, e.g. [{"token": "tk_1"}, ...]
        """
        pass

    @abstractmethod
    async def get_submission(self, token: str) -> Dict[str, Any]:
        """Poll the execution status and output for a given token."""
        pass

    @abstractmethod
    async def get_submissions_batch(self, tokens: List[str]) -> List[Dict[str, Any]]:
        """Poll the execution status and output for multiple tokens."""
        pass

    @abstractmethod
    def verify_callback_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Validate HMAC-SHA256 signature on incoming callback webhook."""
        pass
