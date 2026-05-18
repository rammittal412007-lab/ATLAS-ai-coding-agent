"""
AgentForge — Main FastAPI Application
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from app.api.routes import auth, chat, diffs, executions, health, memory, repos, tasks, websockets
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.core.redis import redis_client

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    configure_logging()
    logger.info("AgentForge starting", env=settings.ENVIRONMENT)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await redis_client.connect()
    logger.info("Redis connected")

    from app.services.indexing.vector_store import VectorStore
    vs = VectorStore()
    await vs.ensure_collections()
    logger.info("Qdrant collections ready")

    yield

    await redis_client.disconnect()
    await engine.dispose()
    logger.info("AgentForge shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentForge API",
        description="Autonomous AI Software Engineering Agent Platform",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    PREFIX = "/api/v1"
    app.include_router(health.router, prefix=PREFIX, tags=["Health"])
    app.include_router(auth.router, prefix=PREFIX, tags=["Auth"])
    app.include_router(repos.router, prefix=PREFIX, tags=["Repositories"])
    app.include_router(tasks.router, prefix=PREFIX, tags=["Tasks"])
    app.include_router(chat.router, prefix=PREFIX, tags=["Chat"])
    app.include_router(executions.router, prefix=PREFIX, tags=["Executions"])
    app.include_router(diffs.router, prefix=PREFIX, tags=["Diffs"])
    app.include_router(memory.router, prefix=PREFIX, tags=["Memory"])
    app.include_router(websockets.router, prefix="/ws", tags=["WebSockets"])

    return app


app = create_app()
