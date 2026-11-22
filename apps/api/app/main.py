from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.middleware import install_middleware
from app.routers import (
    admin,
    agent,
    catalog,
    compatibility,
    documents,
    forecast,
    health,
    retrieval,
    vision,
)
from src.common.config import settings
from src.common.db import init_db
from src.common.logging import configure_logging, get_logger
from src.common.utils import utcnow

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings.ensure_dirs()
    init_db()
    log.info("api_started", env=settings.app_env, version=settings.app_version)
    yield
    log.info("api_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PartScope API",
        description=(
            "Industrial parts intelligence: catalog search, vision identification, "
            "compatibility graph, grounded retrieval, demand forecasting and agent orchestration."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_middleware(app)

    api = "/api/v1"
    app.include_router(health.router, prefix=api)
    app.include_router(catalog.router, prefix=api)
    app.include_router(vision.router, prefix=api)
    app.include_router(compatibility.router, prefix=api)
    app.include_router(retrieval.router, prefix=api)
    app.include_router(documents.router, prefix=api)
    app.include_router(forecast.router, prefix=api)
    app.include_router(agent.router, prefix=api)
    app.include_router(admin.router, prefix=api)

    app.mount("/metrics", make_asgi_app())

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "request_id": getattr(request.state, "request_id", None)},
        )

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "PartScope API",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/v1/health/ready",
            "time": utcnow().isoformat(),
        }

    return app


app = create_app()
