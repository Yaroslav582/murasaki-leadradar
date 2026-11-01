from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import TelegramBroadcast, TelegramChatTarget, TelegramOrder, utcnow
from app.services.freelance_fetcher import sync_external_freelance_orders
from app.services.telegram_service import (
    DEFAULT_TARGETS,
    generate_ai_promo,
    generate_ai_response,
    is_within_working_hours,
    match_keywords,
    telegram_manager,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])


# --- Schemas ---
class TelegramStatusOut(BaseModel):
    is_connected: bool
    has_credentials: bool
    portfolio_url: str
    auto_response_enabled: bool
    auto_posting_enabled: bool
    working_hours_enabled: bool
    working_hours_start: str
    working_hours_end: str
    is_in_working_hours: bool
    working_hours_status_text: str
    auto_response_delay_min: int
    auto_response_delay_max: int
    broadcast_interval_minutes: int
    keywords: list[str]
    stop_words: list[str]
    orders_count: int
    broadcasts_count: int
    chats_count: int


class TelegramOrderOut(BaseModel):
    id: str
    chat_id: str
    chat_title: str
    source: str = "telegram"
    source_url: str | None = None
    message_id: int
    author_username: str | None
    author_name: str | None
    raw_text: str
    summary: str
    category: str
    budget: str | None
    response_text: str | None
    scheduled_for: datetime | None
    responded_at: datetime | None
    status: str
    error: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TelegramBroadcastOut(BaseModel):
    id: str
    chat_id: str
    chat_title: str
    message_text: str
    portfolio_url: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TelegramChatTargetIn(BaseModel):
    chat_id: str
    title: str = ""
    username: str | None = None
    kind: str = "both"  # orders, promo, both
    cooldown_minutes: int = 120
    custom_text: str | None = None
    auto_post_enabled: bool = False


class TelegramChatTargetUpdate(BaseModel):
    title: str | None = None
    kind: str | None = None
    is_active: bool | None = None
    cooldown_minutes: int | None = None
    custom_text: str | None = None
    auto_post_enabled: bool | None = None


class TelegramChatTargetOut(BaseModel):
    id: str
    chat_id: str
    title: str
    username: str | None
    kind: str
    is_active: bool
    cooldown_minutes: int = 120
    custom_text: str | None = None
    auto_post_enabled: bool = False
    last_post_at: datetime | None
    next_post_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TelegramSettingsUpdate(BaseModel):
    portfolio_url: str | None = None
    auto_response_enabled: bool | None = None
    auto_posting_enabled: bool | None = None
    working_hours_enabled: bool | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    telegram_auto_response_delay_min: int | None = None
    telegram_auto_response_delay_max: int | None = None
    telegram_broadcast_interval_minutes: int | None = None
    keywords: str | None = None
    stop_words: str | None = None


# --- Endpoints ---
@router.get("/status", response_model=TelegramStatusOut)
async def get_status(session: AsyncSession = Depends(get_session)) -> TelegramStatusOut:
    orders_count = len((await session.scalars(select(TelegramOrder.id))).all())
    broadcasts_count = len((await session.scalars(select(TelegramBroadcast.id))).all())
    chats_count = len((await session.scalars(select(TelegramChatTarget.id))).all())

    in_work, work_text = is_within_working_hours()

    return TelegramStatusOut(
        is_connected=telegram_manager.is_connected,
        has_credentials=telegram_manager.has_credentials,
        portfolio_url=getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/"),
        auto_response_enabled=getattr(settings, "telegram_auto_response_enabled", True),
        auto_posting_enabled=getattr(settings, "telegram_auto_posting_enabled", True),
        working_hours_enabled=getattr(settings, "telegram_working_hours_enabled", True),
        working_hours_start=getattr(settings, "telegram_working_hours_start", "09:00"),
        working_hours_end=getattr(settings, "telegram_working_hours_end", "23:00"),
        is_in_working_hours=in_work,
        working_hours_status_text=work_text,
        auto_response_delay_min=settings.telegram_auto_response_delay_min,
        auto_response_delay_max=settings.telegram_auto_response_delay_max,
        broadcast_interval_minutes=settings.telegram_broadcast_interval_minutes,
        keywords=settings.telegram_keywords_list,
        stop_words=settings.telegram_stop_words_list,
        orders_count=orders_count,
        broadcasts_count=broadcasts_count,
        chats_count=chats_count,
    )


@router.get("/orders", response_model=list[TelegramOrderOut])
async def list_orders(
    limit: int = Query(default=50, ge=1, le=100),
    status_filter: str | None = None,
    source_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[TelegramOrderOut]:
    stmt = select(TelegramOrder).order_by(desc(TelegramOrder.created_at)).limit(limit)
    if status_filter:
        stmt = stmt.where(TelegramOrder.status == status_filter)
    if source_filter:
        stmt = stmt.where(TelegramOrder.source == source_filter)
    orders = (await session.scalars(stmt)).all()
    return [TelegramOrderOut.model_validate(o) for o in orders]


@router.post("/orders/sync-external")
async def sync_external_orders(session: AsyncSession = Depends(get_session)) -> dict:
    """Fetch live freelance projects from Kwork and FL.ru into the radar."""
    new_count = await sync_external_freelance_orders(session)
    return {"status": "ok", "synced": new_count}


@router.post("/orders/simulate", response_model=TelegramOrderOut)
async def simulate_incoming_order(session: AsyncSession = Depends(get_session)) -> TelegramOrderOut:
    """Generate a realistic test freelance order from a Telegram channel."""
    sample_orders = [
        (
            "Ищем веб-дизайнера / разработчика для создания лендинга под ключ для премиального салона красоты. "
            "Нужен чистый современный дизайн, адаптив под смартфоны, подключение формы заявки в Telegram. "
            "Бюджет 35 000 - 50 000 руб. Сроки до 1 недели. Ждем отклики с примерами работ в ЛС @ekaterina_pro.",
            "Лендинг для салона красоты",
            "35 000 - 50 000 ₽",
            "ekaterina_pro",
            "Екатерина (Салон Beauty)",
            "@freelancetavern",
            "Фриланс Таверна (Заказы)",
        ),
        (
            "Нужен сайт для автосервиса и шиномонтажа в Краснодаре. 4 блока: услуги, прайс, отзывы, контакты и кнопка вызова эвакуатора/записи. "
            "Дизайн строгий, темная тема. Кто может взяться за пару дней, напишите в ЛС ваши кейсы @mikhail_auto.",
            "Сайт автосервиса под ключ",
            "25 000 ₽",
            "mikhail_auto",
            "Михаил",
            "@zakazy_freelance",
            "Биржа заказов Freelance",
        ),
        (
            "Срочно требуется специалист переверстать существующий лендинг компании по ремонту квартир. "
            "Старый сайт грузится медленно и криво открывается с айфона. "
            "Нужно сделать стильно и быстро. Контакт: @artem_build.",
            "Редизайн лендинга по ремонту",
            "40 000 ₽",
            "artem_build",
            "Артём Строительство",
            "@finder_vc",
            "Finder.vc — Удаленка и заказы",
        ),
        (
            "Ищу разработчика сделать Telegram Mini App (визитка + каталог услуг с онлайн-записью) для студии йоги. "
            "Важно, чтобы работало быстро прямо внутри Телеграма. Бюджет 45к. Писать @elena_yoga.",
            "Telegram Mini App для студии йоги",
            "45 000 ₽",
            "elena_yoga",
            "Елена Yoga",
            "@web_freelance_jobs",
            "Веб-разработка | Сайты и лендинги",
        ),
    ]

    text, summary, budget, username, name, channel_id, channel_title = random.choice(sample_orders)
    ai_response = await generate_ai_response(text)
    delay_sec = random.randint(settings.telegram_auto_response_delay_min, settings.telegram_auto_response_delay_max)
    scheduled_time = utcnow() + timedelta(seconds=delay_sec)

    order = TelegramOrder(
        chat_id=channel_id,
        chat_title=channel_title,
        message_id=random.randint(10000, 99999),
        author_username=username,
        author_name=name,
        raw_text=text,
        summary=summary,
        category="Веб-сайт",
        budget=budget,
        response_text=ai_response,
        scheduled_for=scheduled_time,
        status="pending",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return TelegramOrderOut.model_validate(order)


@router.post("/orders/{order_id}/respond", response_model=TelegramOrderOut)
async def trigger_order_response(order_id: str, session: AsyncSession = Depends(get_session)) -> TelegramOrderOut:
    order = await session.get(TelegramOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    recipient = order.author_username or order.chat_id
    success = await telegram_manager.send_direct_message(recipient, order.response_text or "")

    order.status = "sent" if success else "failed"
    order.responded_at = utcnow()
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return TelegramOrderOut.model_validate(order)


@router.post("/orders/{order_id}/skip", response_model=TelegramOrderOut)
async def skip_order_response(order_id: str, session: AsyncSession = Depends(get_session)) -> TelegramOrderOut:
    order = await session.get(TelegramOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    order.status = "skipped"
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return TelegramOrderOut.model_validate(order)


@router.get("/broadcasts", response_model=list[TelegramBroadcastOut])
async def list_broadcasts(
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[TelegramBroadcastOut]:
    stmt = select(TelegramBroadcast).order_by(desc(TelegramBroadcast.created_at)).limit(limit)
    rows = (await session.scalars(stmt)).all()
    return [TelegramBroadcastOut.model_validate(b) for b in rows]


@router.post("/broadcasts/trigger", response_model=TelegramBroadcastOut)
async def trigger_broadcast(session: AsyncSession = Depends(get_session)) -> TelegramBroadcastOut:
    """Generate an AI variation of freelance portfolio pitch and broadcast to target chats."""
    target = await session.scalar(
        select(TelegramChatTarget)
        .where(TelegramChatTarget.is_active == True, TelegramChatTarget.kind.in_(("promo", "both")))
        .order_by(TelegramChatTarget.last_post_at.asc().nullsfirst())
    )
    chat_id = target.chat_id if target else "@Murasaki_website"
    chat_title = target.title if target else "Murasaki | Собственный канал"

    portfolio = getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/")
    if target and target.custom_text and len(target.custom_text.strip()) > 10:
        message_text = target.custom_text.replace("{portfolio}", portfolio)
    else:
        message_text = await generate_ai_promo(portfolio)

    success = await telegram_manager.broadcast_promo(chat_id, message_text)

    broadcast = TelegramBroadcast(
        chat_id=chat_id,
        chat_title=chat_title,
        message_text=message_text,
        portfolio_url=portfolio,
        status="sent" if success else "failed",
    )
    session.add(broadcast)

    if target:
        target.last_post_at = utcnow()
        cd = target.cooldown_minutes or 120
        target.next_post_at = utcnow() + timedelta(minutes=cd)
        session.add(target)

    await session.commit()
    await session.refresh(broadcast)
    return TelegramBroadcastOut.model_validate(broadcast)


@router.get("/chats", response_model=list[TelegramChatTargetOut])
async def list_chats(session: AsyncSession = Depends(get_session)) -> list[TelegramChatTargetOut]:
    chats = (await session.scalars(select(TelegramChatTarget).order_by(TelegramChatTarget.title))).all()
    
    # Check if we should seed/expand default targets
    existing_chat_ids = {c.chat_id for c in chats}
    added_new = False
    for d in DEFAULT_TARGETS:
        if d["chat_id"] not in existing_chat_ids:
            session.add(TelegramChatTarget(**d))
            added_new = True
            
    if added_new:
        await session.commit()
        chats = (await session.scalars(select(TelegramChatTarget).order_by(TelegramChatTarget.title))).all()

    return [TelegramChatTargetOut.model_validate(c) for c in chats]


@router.post("/chats", response_model=TelegramChatTargetOut, status_code=status.HTTP_201_CREATED)
async def add_chat(payload: TelegramChatTargetIn, session: AsyncSession = Depends(get_session)) -> TelegramChatTargetOut:
    chat_id = payload.chat_id.strip()
    existing = await session.scalar(select(TelegramChatTarget).where(TelegramChatTarget.chat_id == chat_id))
    if existing:
        raise HTTPException(status_code=400, detail="Этот канал/чат уже добавлен")

    target = TelegramChatTarget(
        chat_id=chat_id,
        title=payload.title.strip() or chat_id,
        username=payload.username.strip() if payload.username else chat_id.lstrip("@"),
        kind=payload.kind,
        cooldown_minutes=payload.cooldown_minutes,
        custom_text=payload.custom_text,
        auto_post_enabled=payload.auto_post_enabled,
        is_active=True,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return TelegramChatTargetOut.model_validate(target)


@router.patch("/chats/{chat_id}", response_model=TelegramChatTargetOut)
async def update_chat(
    chat_id: str,
    payload: TelegramChatTargetUpdate,
    session: AsyncSession = Depends(get_session),
) -> TelegramChatTargetOut:
    target = await session.scalar(select(TelegramChatTarget).where(TelegramChatTarget.id == chat_id))
    if not target:
        raise HTTPException(status_code=404, detail="Канал не найден")

    if payload.title is not None:
        target.title = payload.title.strip()
    if payload.kind is not None:
        target.kind = payload.kind
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.cooldown_minutes is not None:
        target.cooldown_minutes = max(5, payload.cooldown_minutes)
    if payload.custom_text is not None:
        target.custom_text = payload.custom_text.strip() or None
    if payload.auto_post_enabled is not None:
        target.auto_post_enabled = payload.auto_post_enabled
        if payload.auto_post_enabled and target.next_post_at is None:
            # Schedule initial post after a brief jitter
            target.next_post_at = utcnow() + timedelta(minutes=random.randint(1, 5))

    session.add(target)
    await session.commit()
    await session.refresh(target)
    return TelegramChatTargetOut.model_validate(target)


@router.post("/chats/{chat_id}/post-now", response_model=TelegramBroadcastOut)
async def post_now_to_chat(
    chat_id: str,
    session: AsyncSession = Depends(get_session),
) -> TelegramBroadcastOut:
    """Instantly post to a specific channel."""
    target = await session.scalar(select(TelegramChatTarget).where(TelegramChatTarget.id == chat_id))
    if not target:
        raise HTTPException(status_code=404, detail="Канал не найден")

    portfolio = getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/")
    if target.custom_text and len(target.custom_text.strip()) > 10:
        message_text = target.custom_text.replace("{portfolio}", portfolio)
    else:
        message_text = await generate_ai_promo(portfolio)

    success = await telegram_manager.broadcast_promo(target.chat_id, message_text)

    target.last_post_at = utcnow()
    cd = target.cooldown_minutes or 120
    target.next_post_at = utcnow() + timedelta(minutes=cd)
    session.add(target)

    broadcast = TelegramBroadcast(
        chat_id=target.chat_id,
        chat_title=target.title or target.chat_id,
        message_text=message_text,
        portfolio_url=portfolio,
        status="sent" if success else "failed",
    )
    session.add(broadcast)
    await session.commit()
    await session.refresh(broadcast)
    return TelegramBroadcastOut.model_validate(broadcast)


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    target = await session.scalar(select(TelegramChatTarget).where(TelegramChatTarget.id == chat_id))
    if not target:
        raise HTTPException(status_code=404, detail="Чат не найден")
    await session.delete(target)
    await session.commit()
    return {"status": "ok"}


@router.post("/bot/create")
async def create_bot_endpoint() -> dict:
    """Create a new bot automatically via @BotFather using user session."""
    return await telegram_manager.create_bot_via_botfather()


@router.post("/settings")
async def update_settings(payload: TelegramSettingsUpdate) -> dict:
    if payload.portfolio_url is not None:
        settings.telegram_portfolio_url = payload.portfolio_url.strip()
    if payload.auto_response_enabled is not None:
        settings.telegram_auto_response_enabled = payload.auto_response_enabled
    if payload.auto_posting_enabled is not None:
        settings.telegram_auto_posting_enabled = payload.auto_posting_enabled
    if payload.working_hours_enabled is not None:
        settings.telegram_working_hours_enabled = payload.working_hours_enabled
    if payload.working_hours_start is not None:
        settings.telegram_working_hours_start = payload.working_hours_start.strip()
    if payload.working_hours_end is not None:
        settings.telegram_working_hours_end = payload.working_hours_end.strip()
    if payload.telegram_auto_response_delay_min is not None:
        settings.telegram_auto_response_delay_min = payload.telegram_auto_response_delay_min
    if payload.telegram_auto_response_delay_max is not None:
        settings.telegram_auto_response_delay_max = payload.telegram_auto_response_delay_max
    if payload.telegram_broadcast_interval_minutes is not None:
        settings.telegram_broadcast_interval_minutes = payload.telegram_broadcast_interval_minutes
    if payload.keywords is not None:
        settings.telegram_keywords = payload.keywords
    if payload.stop_words is not None:
        settings.telegram_stop_words = payload.stop_words

    return {"status": "ok", "message": "Настройки Telegram обновлены"}
