"""One retry helper shared by Claude, Jira and Google Sheets calls."""
import time


class RetryableError(Exception):
    """Raised for temporary problems (network, rate limit, server error)."""

    def __init__(self, message: str, wait: float | None = None):
        super().__init__(message)
        self.wait = wait


def parse_retry_after(value) -> float | None:
    try:
        return float(value) if value else None
    except (TypeError, ValueError):
        return None


def retry(fn, *, step: str, incidents, attempts: int, base_wait: float = 5):
    """Call fn(); on RetryableError wait (exponential backoff) and try again."""
    for attempt in range(1, attempts + 2):
        try:
            return fn()
        except RetryableError as error:
            if attempt > attempts:
                raise
            wait = error.wait or min(base_wait * 2 ** (attempt - 1), 120)
            incidents.log(step, "retry", f"{error} (attempt {attempt}/{attempts})", f"waiting {wait:.0f}s")
            time.sleep(wait)
