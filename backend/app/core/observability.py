"""Logging, request metrics and security headers (brief section 19: monitoring and logging, security testing)."""
import logging
import threading
import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

access_log = logging.getLogger("dermai.access")
SLOW_MS = 2000


def setup_logging() -> None:
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.started = time.time()
        self.by_status: dict[str, int] = defaultdict(int)
        self.by_route: dict[str, list] = defaultdict(lambda: [0, 0.0, 0.0])   # count, total ms, max ms
        self.slow = 0

    def observe(self, method: str, route: str, status: int, ms: float) -> None:
        with self._lock:
            self.by_status[f"{status // 100}xx"] += 1
            r = self.by_route[f"{method} {route}"]
            r[0] += 1; r[1] += ms; r[2] = max(r[2], ms)
            self.slow += ms > SLOW_MS

    def snapshot(self) -> dict:
        with self._lock:
            routes = {k: {"count": c, "mean_ms": round(t / c, 1), "max_ms": round(m, 1)} for k, (c, t, m) in self.by_route.items()}
            total = sum(self.by_status.values())
            return {"uptime_seconds": int(time.time() - self.started), "requests_total": total, "by_status": dict(self.by_status),
                    "slow_requests_over_2s": self.slow, "routes": dict(sorted(routes.items(), key=lambda kv: -kv[1]["count"])[:25])}


metrics = Metrics()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id", "")[:40] or uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            access_log.exception("%s %s -> unhandled error rid=%s", request.method, request.url.path, rid)
            metrics.observe(request.method, request.url.path, 500, (time.perf_counter() - t0) * 1000)
            raise
        ms = (time.perf_counter() - t0) * 1000
        route = getattr(request.scope.get("route"), "path", "unmatched")        # template, so /cases/7 and /cases/8 group together
        if not request.url.path.startswith("/assets"):
            metrics.observe(request.method, route, response.status_code, ms)
            access_log.log(logging.WARNING if ms > SLOW_MS or response.status_code >= 500 else logging.INFO,
                           "%s %s %s %.0fms rid=%s", request.method, request.url.path, response.status_code, ms, rid)
        h = response.headers
        h["X-Request-ID"] = rid
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"    # the web app captures photos with the camera
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        if settings.environment == "production":
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
