from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_router
from app.config import settings
from app.db import get_session, init_db
from app.models import DemoSite
from app.seed import seed_demo_data
from app.services.bot_runner import bot_runner
from app.services.jobs import fail_stale_jobs
from app.services.telegram_service import telegram_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if not settings.use_celery:
        try:
            stale = await fail_stale_jobs()
            if stale:
                logger.info("Marked %s stale parse jobs as failed", stale)
        except Exception:
            logger.exception("Failed to clean up stale parse jobs")
    if settings.seed_on_start:
        try:
            seeded = await seed_demo_data()
            if seeded:
                logger.info("Demo data seeded: %s leads", seeded)
        except Exception:
            logger.exception("Failed to seed demo data")
    # Initialize Telegram & Bot runner in background
    init_task = asyncio.create_task(telegram_manager.initialize())
    bot_runner.start()
    try:
        yield
    finally:
        bot_runner.stop()
        if getattr(telegram_manager, "_background_task", None) and not telegram_manager._background_task.done():
            telegram_manager._background_task.cancel()
        if not init_task.done():
            init_task.cancel()


app = FastAPI(
    title="LeadRadar API",
    description=(
        "Сбор лидов из карт, обогащение контактов, AI-генерация демо-лендингов "
        "и аутрич-сообщений."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/demo/{demo_id}", response_class=HTMLResponse)
async def public_demo(demo_id: str, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    demo = await session.get(DemoSite, demo_id)
    if demo is None or not demo.published:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return HTMLResponse(
        content=demo.html,
        headers={"X-Robots-Tag": "noindex", "Cache-Control": "no-store"},
    )


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/health",
        "api": "/api",
    }
