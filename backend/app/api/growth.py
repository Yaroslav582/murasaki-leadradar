from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import (
    TelegramCommentLog,
    TelegramCommentTarget,
    TelegramParsedUser,
    utcnow,
)
from app.services.telegram_growth import (
    BLOG_TOPICS,
    DEFAULT_COMMENT_TARGETS,
    generate_ai_blog_post,
    generate_ai_comment,
    growth_manager,
    publish_blog_post,
)

router = APIRouter(prefix="/growth", tags=["growth"])


# --- Schemas ---
class CommentTargetIn(BaseModel):
    channel_id: str
    title: str = ""
    username: str | None = None
    tone: str = "expert"
    custom_prompt: str | None = None


class CommentTargetOut(BaseModel):
    id: str
    channel_id: str
    title: str
    username: str | None
    is_active: bool
    tone: str
    custom_prompt: str | None
    comments_count: int
    last_comment_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class CommentGenerateIn(BaseModel):
    post_text: str
    channel_id: str = "@channel"
    channel_title: str = "Телеграм Канал"
    post_id: int = 0
    tone: str = "expert"
    custom_prompt: str | None = None


class ParseChatIn(BaseModel):
    chat_identifier: str
    limit: int = Field(default=100, ge=10, le=1000)
    only_active: bool = True
    only_premium: bool = False


class ParsedUserOut(BaseModel):
    id: str
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    source_chat: str
    has_premium: bool
    last_seen_status: str | None
    stories_viewed_at: datetime | None
    stories_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class StoriesStatusOut(BaseModel):
    is_running: bool
    viewed_count: int
    total_users: int
    unviewed_count: int


# --- Endpoints: Нейрокомментинг ---

@router.get("/comment-targets", response_model=list[CommentTargetOut])
async def list_comment_targets(session: AsyncSession = Depends(get_session)) -> list[CommentTargetOut]:
    targets = (await session.scalars(select(TelegramCommentTarget).order_by(TelegramCommentTarget.title))).all()

    # Seed defaults if empty
    existing_ids = {t.channel_id for t in targets}
    added_new = False
    for d in DEFAULT_COMMENT_TARGETS:
        if d["channel_id"] not in existing_ids:
            session.add(TelegramCommentTarget(**d))
            added_new = True

    if added_new:
        await session.commit()
        targets = (await session.scalars(select(TelegramCommentTarget).order_by(TelegramCommentTarget.title))).all()

    return [CommentTargetOut.model_validate(t) for t in targets]


@router.post("/comment-targets", response_model=CommentTargetOut, status_code=status.HTTP_201_CREATED)
async def add_comment_target(payload: CommentTargetIn, session: AsyncSession = Depends(get_session)) -> CommentTargetOut:
    cid = payload.channel_id.strip()
    if not cid.startswith("@") and not cid.startswith("-100"):
        cid = f"@{cid}"

    existing = await session.scalar(select(TelegramCommentTarget).where(TelegramCommentTarget.channel_id == cid))
    if existing:
        raise HTTPException(status_code=400, detail="Этот канал уже добавлен в список комментинга")

    target = TelegramCommentTarget(
        channel_id=cid,
        title=payload.title.strip() or cid,
        username=payload.username or cid.lstrip("@"),
        tone=payload.tone,
        custom_prompt=payload.custom_prompt,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return CommentTargetOut.model_validate(target)


@router.delete("/comment-targets/{target_id}")
async def delete_comment_target(target_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    target = await session.get(TelegramCommentTarget, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Канал не найден")
    await session.delete(target)
    await session.commit()
    return {"status": "ok"}


@router.post("/comment-targets/generate")
async def generate_comment_preview(payload: CommentGenerateIn) -> dict[str, Any]:
    """Generate an AI comment for testing or posting directly."""
    res = await growth_manager.post_comment(
        channel_id=payload.channel_id,
        post_id=payload.post_id,
        post_text=payload.post_text,
        channel_title=payload.channel_title,
        tone=payload.tone,
        custom_prompt=payload.custom_prompt,
    )
    return res


@router.get("/comment-logs")
async def list_comment_logs(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    logs = (await session.scalars(select(TelegramCommentLog).order_by(desc(TelegramCommentLog.created_at)).limit(limit))).all()
    return [
        {
            "id": l.id,
            "channel_id": l.channel_id,
            "channel_title": l.channel_title,
            "post_id": l.post_id,
            "post_text": l.post_text,
            "comment_text": l.comment_text,
            "status": l.status,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


# --- Endpoints: Парсер участников ---

@router.post("/parse-chat", response_model=list[ParsedUserOut])
async def parse_chat_endpoint(payload: ParseChatIn, session: AsyncSession = Depends(get_session)) -> list[ParsedUserOut]:
    users = await growth_manager.parse_group(
        chat_identifier=payload.chat_identifier,
        limit=payload.limit,
        only_active=payload.only_active,
        only_premium=payload.only_premium,
    )
    stmt = (
        select(TelegramParsedUser)
        .where(TelegramParsedUser.source_chat == payload.chat_identifier.strip())
        .order_by(desc(TelegramParsedUser.created_at))
        .limit(payload.limit)
    )
    db_users = (await session.scalars(stmt)).all()
    return [ParsedUserOut.model_validate(u) for u in db_users]


@router.get("/parsed-users", response_model=list[ParsedUserOut])
async def list_parsed_users(
    limit: int = Query(default=100, le=500),
    source_chat: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ParsedUserOut]:
    stmt = select(TelegramParsedUser).order_by(desc(TelegramParsedUser.created_at)).limit(limit)
    if source_chat:
        stmt = stmt.where(TelegramParsedUser.source_chat == source_chat.strip())
    users = (await session.scalars(stmt)).all()
    return [ParsedUserOut.model_validate(u) for u in users]


@router.delete("/parsed-users/{user_id}")
async def delete_parsed_user(user_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    u = await session.get(TelegramParsedUser, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    await session.delete(u)
    await session.commit()
    return {"status": "ok"}


@router.post("/parsed-users/clear")
async def clear_parsed_users(session: AsyncSession = Depends(get_session)) -> dict:
    await session.execute(delete(TelegramParsedUser))
    await session.commit()
    return {"status": "ok"}


# --- Endpoints: Просмотр историй (Stories Masslooking) ---

@router.get("/stories/status", response_model=StoriesStatusOut)
async def get_stories_status(session: AsyncSession = Depends(get_session)) -> StoriesStatusOut:
    total = (await session.scalar(select(func.count(TelegramParsedUser.id)))) or 0
    unviewed = (
        await session.scalar(
            select(func.count(TelegramParsedUser.id)).where(TelegramParsedUser.stories_viewed_at == None)
        )
    ) or 0

    return StoriesStatusOut(
        is_running=growth_manager.is_stories_running,
        viewed_count=growth_manager.stories_viewed_count,
        total_users=total,
        unviewed_count=unviewed,
    )


@router.post("/stories/toggle")
async def toggle_stories_masslooking(
    enable: bool = Query(...),
    delay_min: int = Query(default=15),
    delay_max: int = Query(default=35),
) -> dict[str, Any]:
    if enable:
        growth_manager.start_stories_masslooking(delay_min, delay_max)
    else:
        growth_manager.stop_stories_masslooking()
    return {"status": "ok", "is_running": growth_manager.is_stories_running}


# --- Endpoints: AI-Автоблогер для Telegram канала ---

class BlogSettingsIn(BaseModel):
    enabled: bool | None = None
    channel_id: str | None = None
    interval_hours: int | None = None


class BlogGenerateIn(BaseModel):
    topic_hint: str | None = None
    channel_id: str = "@Murasaki_website"


@router.get("/blog/status")
async def get_blog_status(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    from app.config import settings
    from app.models import AppSetting

    # Load from Supabase app_settings
    st = await session.get(AppSetting, "channel_blog_settings")
    db_val = st.value if (st and st.value) else {}

    enabled = db_val.get("enabled", getattr(settings, "channel_blog_enabled", True))
    channel_id = db_val.get("channel_id", getattr(settings, "channel_blog_chat_id", "@Murasaki_website"))
    interval_hours = db_val.get("interval_hours", getattr(settings, "channel_blog_interval_hours", 24))
    last_post_at = db_val.get("last_post_at", getattr(settings, "channel_blog_last_post_at", None))
    next_post_at = db_val.get("next_post_at", getattr(settings, "channel_blog_next_post_at", None))

    # Keep settings synchronized
    settings.channel_blog_enabled = enabled
    settings.channel_blog_chat_id = channel_id
    settings.channel_blog_interval_hours = interval_hours
    settings.channel_blog_last_post_at = last_post_at
    settings.channel_blog_next_post_at = next_post_at

    return {
        "enabled": enabled,
        "channel_id": channel_id,
        "interval_hours": interval_hours,
        "last_post_at": last_post_at,
        "next_post_at": next_post_at,
        "topics": BLOG_TOPICS,
    }


@router.post("/blog/settings")
async def update_blog_settings(payload: BlogSettingsIn, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    from datetime import datetime, timedelta
    from app.config import settings
    from app.models import AppSetting, utcnow

    st = await session.get(AppSetting, "channel_blog_settings")
    cur_val = dict(st.value) if (st and st.value) else {}

    enabled = cur_val.get("enabled", getattr(settings, "channel_blog_enabled", True))
    channel_id = cur_val.get("channel_id", getattr(settings, "channel_blog_chat_id", "@Murasaki_website"))
    interval_hours = cur_val.get("interval_hours", getattr(settings, "channel_blog_interval_hours", 24))
    last_post_at = cur_val.get("last_post_at", getattr(settings, "channel_blog_last_post_at", None))
    next_post_at = cur_val.get("next_post_at", getattr(settings, "channel_blog_next_post_at", None))

    if payload.enabled is not None:
        enabled = payload.enabled
    if payload.channel_id is not None and payload.channel_id.strip():
        cid = payload.channel_id.strip()
        channel_id = cid if cid.startswith("@") or cid.startswith("-100") else f"@{cid}"

    interval_changed = False
    if payload.interval_hours is not None:
        new_interval = max(1, min(168, payload.interval_hours))
        if new_interval != interval_hours:
            interval_changed = True
        interval_hours = new_interval

    now = utcnow()
    # Recalculate next_post_at if interval changed or if next_post_at is missing or in past
    if interval_changed or next_post_at is None:
        if last_post_at:
            try:
                last_dt = datetime.fromisoformat(last_post_at)
                computed_next = last_dt + timedelta(hours=interval_hours)
                if computed_next <= now:
                    computed_next = now + timedelta(hours=interval_hours)
                next_post_at = computed_next.isoformat()
            except Exception:
                next_post_at = (now + timedelta(hours=interval_hours)).isoformat()
        else:
            next_post_at = (now + timedelta(hours=interval_hours)).isoformat()

    updated_val = {
        "enabled": enabled,
        "channel_id": channel_id,
        "interval_hours": interval_hours,
        "last_post_at": last_post_at,
        "next_post_at": next_post_at,
    }

    # Save to Supabase AppSetting table
    if st:
        st.value = updated_val
    else:
        st = AppSetting(key="channel_blog_settings", value=updated_val)
        session.add(st)
    await session.commit()

    # Sync in-memory settings
    settings.channel_blog_enabled = enabled
    settings.channel_blog_chat_id = channel_id
    settings.channel_blog_interval_hours = interval_hours
    settings.channel_blog_last_post_at = last_post_at
    settings.channel_blog_next_post_at = next_post_at

    return {
        "status": "ok",
        "enabled": enabled,
        "channel_id": channel_id,
        "interval_hours": interval_hours,
        "last_post_at": last_post_at,
        "next_post_at": next_post_at,
    }


@router.post("/blog/generate-preview")
async def generate_blog_preview(payload: BlogGenerateIn) -> dict[str, Any]:
    title, text = await generate_ai_blog_post(topic_hint=payload.topic_hint)
    return {
        "title": title,
        "text": text,
        "topic": payload.topic_hint or "Случайная экспертная тема",
    }


@router.post("/blog/publish-now")
async def publish_blog_now(payload: BlogGenerateIn) -> dict[str, Any]:
    cid = payload.channel_id or getattr(settings, "channel_blog_chat_id", "@Murasaki_website")
    res = await publish_blog_post(channel_id=cid, topic_hint=payload.topic_hint)
    return res
