from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request

from src.monitoring.metrics import REQUEST_COUNT, REQUEST_LATENCY


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def observability(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(request.method, request.url.path, "500").inc()
            structlog.contextvars.clear_contextvars()
            raise

        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = f"{elapsed * 1000:.2f}"
        structlog.contextvars.clear_contextvars()
        return response
