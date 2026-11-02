"""FastAPI application entry point: `uvicorn app.main:app`."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import dev, health, internal, webhook
from app.config import Settings, get_settings
from app.container import Container, build_container
from app.core.logging import configure_logging, request_id_var
from app.db.session import create_all
from app.services.seed import seed_content

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        c = container or build_container(settings)
        app.state.container = c
        if settings.auto_create_tables:
            await create_all(c.engine)
        if settings.seed_on_startup:
            async with c.sessionmaker() as session:
                await seed_content(session)
        scheduler = None
        if settings.enable_scheduler:
            from app.scheduler import start_scheduler

            scheduler = start_scheduler(c)
        logger.info("Started %s (env=%s, llm=%s, whatsapp=%s)", settings.app_name, settings.environment,
                    c.llm.available, settings.whatsapp_enabled)
        yield
        if scheduler:
            scheduler.shutdown(wait=False)
        await c.close()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered WhatsApp tutor for DSA (C++/Python) and Machine Learning",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        token = request_id_var.set(request.headers.get("X-Request-ID", uuid.uuid4().hex[:12]))
        try:
            return await call_next(request)
        finally:
            request_id_var.reset(token)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/", include_in_schema=False)
    async def root():
        return {"name": settings.app_name, "status": "running", "docs": "/docs", "health": "/health"}

    app.include_router(health.router)
    app.include_router(webhook.router)
    app.include_router(internal.router)
    if settings.dev_chat_enabled and settings.environment != "production":
        app.include_router(dev.router)
    return app


app = create_app()
