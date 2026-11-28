"""Failed-login limiter (in-memory, per process). Blocks a key (client IP + email) after too many failures in a window.
Fine for one API container. With several replicas move this to Redis (listed in the brief's optional stack)."""
import threading
import time
from collections import defaultdict, deque

from app.core.config import settings


class FailureLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._fails: dict[str, deque] = defaultdict(deque)

    def _prune(self, q: deque, now: float) -> None:
        while q and now - q[0] > settings.login_lock_seconds:
            q.popleft()

    def blocked(self, key: str) -> int:
        """Seconds until the key may try again (0 = not blocked)."""
        now = time.time()
        with self._lock:
            q = self._fails[key]
            self._prune(q, now)
            if len(q) >= settings.login_max_failures:
                return max(1, int(settings.login_lock_seconds - (now - q[0])))
            return 0

    def fail(self, key: str) -> None:
        with self._lock:
            self._fails[key].append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


login_limiter = FailureLimiter()
