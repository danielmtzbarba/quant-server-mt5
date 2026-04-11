import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures a unique X-Correlation-ID is present for every request.
    Binds the ID and Client IP to structlog contextvars for consistent logging.
    """

    async def dispatch(self, request: Request, call_next):
        # Clear contextvars from previous requests (important for concurrency)
        clear_contextvars()

        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        client_ip = request.client.host if request.client else "unknown"

        # Bind consistently to the request context
        bind_contextvars(correlation_id=correlation_id, client_ip=client_ip)

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs the start and finish of every request with metadata.
    """

    DEBUG_PATHS = {
        "/api/symbols",
        "/api/history",
        "/api/positions",
        "/api/health",
        "/health",
        "/sync_status",
        "/metrics",
    }

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        user_agent = request.headers.get("user-agent", "unknown")
        path = request.url.path

        # Determine log level based on path noise
        is_noisy = path in self.DEBUG_PATHS
        log_func = logger.debug if is_noisy else logger.info

        log_func(
            "request_started",
            method=request.method,
            path=path,
            user_agent=user_agent,
        )

        response = await call_next(request)

        process_time = time.perf_counter() - start_time
        log_func(
            "request_finished",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration=f"{process_time:.4f}s",
        )

        return response
