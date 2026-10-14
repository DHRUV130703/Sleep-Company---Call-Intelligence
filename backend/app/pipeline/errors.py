"""The one exception pipeline stages raise. The runner turns it into a retry, a skip or a failure."""

from app.errors import MESSAGES, ErrorCode


class StageError(Exception):
    """
    retryable → the job is queued again later (network blips, provider busy)
    skip      → the call is not an error, just not analysable (too short, silent, one-sided)
    otherwise → the call is marked failed with a plain-language message and a Retry button
    """

    def __init__(self, code: ErrorCode, *, detail: str = "", retryable: bool = False, skip: bool = False):
        self.code = code
        self.detail = detail
        self.retryable = retryable
        self.skip = skip
        super().__init__(f"{code}: {detail or MESSAGES[code]}")

    @property
    def message(self) -> str:
        base = MESSAGES[self.code]
        return f"{base} ({self.detail})" if self.detail and self.detail not in base else base


class StageWait(Exception):
    """Not an error: the stage is waiting on someone else (e.g. AssemblyAI is still transcribing).
    The runner puts the job back in the queue to run again after `seconds`, without counting an attempt."""

    def __init__(self, seconds: float, message: str):
        self.seconds = seconds
        self.message = message
        super().__init__(message)
