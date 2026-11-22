from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_router
from app.config import settings
from app.db import get_session, init_db
from app.models import DemoSite
from app.seed import seed_demo_data, seed_telegram_data
from app.services.account_pool import account_pool
from app.services.bot_runner import bot_runner
from app.services.jobs import fail_stale_jobs
from app.services.keep_alive import keep_alive_service
from app.services.telegram_service import telegram_manager
from app.services.warmup_worker import warmup_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Preload dynamic settings from Supabase app_settings (LLM config, bot tokens)
    try:
        from app.services.llm import load_llm_config_from_db
        await load_llm_config_from_db()
    except Exception as exc:
        logger.debug("Failed preloading llm_config: %s", exc)

    try:
        from app.models import AppSetting
        from app.db import SessionLocal
        async with SessionLocal() as db_session:
            bot_token_setting = await db_session.get(AppSetting, "telegram_bot_token")
            if bot_token_setting and bot_token_setting.value:
                if bot_token_setting.value.get("token"):
                    settings.telegram_bot_token = bot_token_setting.value["token"]
                if bot_token_setting.value.get("bot_username"):
                    settings.telegram_bot_username = bot_token_setting.value["bot_username"]

            blog_setting = await db_session.get(AppSetting, "channel_blog_settings")
            if blog_setting and blog_setting.value:
                b_val = blog_setting.value
                if "enabled" in b_val:
                    settings.channel_blog_enabled = b_val["enabled"]
                if "channel_id" in b_val:
                    settings.channel_blog_chat_id = b_val["channel_id"]
                if "interval_hours" in b_val:
                    settings.channel_blog_interval_hours = int(b_val["interval_hours"])
                if "last_post_at" in b_val:
                    settings.channel_blog_last_post_at = b_val["last_post_at"]
                if "next_post_at" in b_val:
                    settings.channel_blog_next_post_at = b_val["next_post_at"]

            tg_setting = await db_session.get(AppSetting, "telegram_settings")
            if tg_setting and tg_setting.value:
                tg_val = tg_setting.value
                if "portfolio_url" in tg_val:
                    settings.telegram_portfolio_url = tg_val["portfolio_url"]
                if "auto_response_enabled" in tg_val:
                    settings.telegram_auto_response_enabled = tg_val["auto_response_enabled"]
                if "auto_posting_enabled" in tg_val:
                    settings.telegram_auto_posting_enabled = tg_val["auto_posting_enabled"]
                if "working_hours_enabled" in tg_val:
                    settings.telegram_working_hours_enabled = tg_val["working_hours_enabled"]
                if "working_hours_start" in tg_val:
                    settings.telegram_working_hours_start = tg_val["working_hours_start"]
                if "working_hours_end" in tg_val:
                    settings.telegram_working_hours_end = tg_val["working_hours_end"]
                if "telegram_auto_response_delay_min" in tg_val:
                    settings.telegram_auto_response_delay_min = tg_val["telegram_auto_response_delay_min"]
                if "telegram_auto_response_delay_max" in tg_val:
                    settings.telegram_auto_response_delay_max = tg_val["telegram_auto_response_delay_max"]
                if "telegram_broadcast_interval_minutes" in tg_val:
                    settings.telegram_broadcast_interval_minutes = tg_val["telegram_broadcast_interval_minutes"]
                if "keywords" in tg_val:
                    settings.telegram_keywords = tg_val["keywords"]
                if "stop_words" in tg_val:
                    settings.telegram_stop_words = tg_val["stop_words"]
    except Exception as exc:
        logger.debug("Failed preloading settings from Supabase app_settings: %s", exc)

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
            tg_seeded = await seed_telegram_data()
            if tg_seeded.get("chats") or tg_seeded.get("orders"):
                logger.info("Telegram demo data seeded: %s", tg_seeded)
        except Exception:
            logger.exception("Failed to seed demo data")

    # Load all saved Telethon accounts from DB and start listening for PM events
    try:
        loaded_accounts = await account_pool.load_all_from_db()
        logger.info("Account pool ready: %d Telethon sessions loaded and listening for messages", loaded_accounts)
    except Exception:
        logger.exception("Failed to load saved accounts from DB on startup")

    # Initialize Telegram & Bot runner in background
    init_task = asyncio.create_task(telegram_manager.initialize())
    bot_runner.start()
    warmup_worker.start()
    try:
        await warmup_worker.initialize_from_db()
    except Exception as w_exc:
        logger.warning("Failed to initialize warmup worker from DB: %s", w_exc)
    keep_alive_service.start()
    try:
        yield
    finally:
        keep_alive_service.stop()
        warmup_worker.stop()
        bot_runner.stop()
        await account_pool.disconnect_all()
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
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Static files mount (for uploads, avatars, persisted media)
_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
(_static_dir / "uploads" / "media").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/demo/{demo_id}", response_class=HTMLResponse)
async def public_demo(demo_id: str, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    target_id = demo_id.strip()
    demo = await session.get(DemoSite, target_id)
    if demo is None:
        stmt = select(DemoSite).where(DemoSite.lead_id == target_id).order_by(DemoSite.created_at.desc())
        res = await session.execute(stmt)
        demo = res.scalars().first()

    if demo is None or not demo.published:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return HTMLResponse(
        content=demo.html,
        headers={"X-Robots-Tag": "noindex", "Cache-Control": "no-store"},
    )


@app.get("/api/debug-db")
async def debug_db():
    import traceback
    from app.db import DATABASE_URL, SessionLocal
    from sqlalchemy import text, select, func
    from app.models import Lead
    info = {
        "database_url_host": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL[:25],
        "is_sqlite": DATABASE_URL.startswith("sqlite"),
    }
    try:
        async with SessionLocal() as s:
            r = await s.execute(text("SELECT 1"))
            info["select_1"] = r.scalar()
            r2 = await s.scalar(select(func.count(Lead.id)))
            info["leads_count"] = r2
    except Exception as exc:
        info["error"] = str(exc)
        info["traceback"] = traceback.format_exc()
    return info


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/health",
        "api": "/api",
    }
