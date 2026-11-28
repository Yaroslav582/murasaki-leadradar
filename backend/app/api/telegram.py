from __future__ import annotations

import logging
import os
import random
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DATA_DIR, settings
from app.db import get_session
from app.models import TelegramBroadcast, TelegramChatTarget, TelegramOrder, utcnow
from app.services.billing import check_and_spend, get_or_create_user
from app.services.freelance_fetcher import sync_external_freelance_orders
from app.services.telegram_service import (
    DEFAULT_TARGETS,
    build_kwork_proposal,
    extract_order_summary,
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


class TGStatStatusOut(BaseModel):
    has_token: bool
    token_preview: str | None = None
    default_keywords: list[str]
    default_categories: list[str]
    queue_count: int = 0


class TGStatItem(BaseModel):
    username_or_link: str
    title: str = ""
    category: str = ""
    members_count: int = 0
    is_already_added: bool = False


class TGStatSearchIn(BaseModel):
    keywords: str = ""
    category: str = "all"
    min_ci: float = 5.0
    min_members: int = 100
    token: str | None = None
    auto_add: bool = False


class TGStatSearchOut(BaseModel):
    total_found: int
    saved_count: int = 0
    used_token: bool = False
    items: list[TGStatItem]


class TGStatAddTargetsIn(BaseModel):
    items: list[TGStatItem]
    kind: str = "both"  # orders, promo, both
    cooldown_minutes: int = 120
    auto_post_enabled: bool = False


class TGStatTokenIn(BaseModel):
    token: str


# --- Endpoints ---
@router.get("/status", response_model=TelegramStatusOut)
async def get_status(session: AsyncSession = Depends(get_session)) -> TelegramStatusOut:
    from app.models import AppSetting

    # Load persistent settings from Supabase app_settings
    st = await session.get(AppSetting, "telegram_settings")
    if st and st.value:
        tg_val = st.value
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
        (
            "Требуется разработать современный корпоративный сайт для логистической компании. "
            "Калькулятор доставки, интеграция заявок в CRM и адаптивная верстка. Бюджет 70 000 руб. Связь @dmitry_logist.",
            "Сайт для логистической компании",
            "70 000 ₽",
            "dmitry_logist",
            "Дмитрий (Логистика)",
            "@freelancefeed",
            "Freelance Feed | Заказы сайтов",
        ),
        (
            "Нужен Telegram Mini App (TMA) для доставки пиццы и суши: меню с корзиной, выбор адреса и оплата. "
            "Кто уже делал WebApp ботов в TG, скиньте портфолио в лс @pizzaman_chef.",
            "Telegram Mini App доставки еды",
            "60 000 ₽",
            "pizzaman_chef",
            "Шеф Пицца",
            "@tg_bots_orders",
            "Заказы Telegram ботов и WebApps",
        ),
        (
            "Ищем веб-мастера для создания конверсионного лендинга для стоматологической клиники. "
            "Светлый эстетичный дизайн, форма записи на прием, блок с врачами и до/после. Бюджет 50 000 руб. ЛС @stoma_clinic.",
            "Лендинг для стоматологии",
            "50 000 ₽",
            "stoma_clinic",
            "Клиника Дент",
            "@digital_rabota",
            "Digital Jobs: Сайты, UX/UI, Боты",
        ),
        (
            "Срочно нужен стильный сайт-портфолио для архитектурного бюро. "
            "Минимализм, анимации при скролле, галерея готовых объектов в высоком качестве. Писать @arch_modern.",
            "Сайт для архитектурного бюро",
            "55 000 ₽",
            "arch_modern",
            "Arch Bureau",
            "@freelancechoice",
            "Фриланс Выбор — Заказы на сайты",
        ),
        (
            "Разработка интернет-магазина одежды на React/Next.js. "
            "Каталог с фильтрами, карточки товаров, корзина и админка. Бюджет 90 000 руб. Отклики в лс @fashion_store_brand.",
            "Интернет-магазин одежды на Next.js",
            "90 000 ₽",
            "fashion_store_brand",
            "Fashion Brand",
            "@webdev_jobs_ru",
            "WebDev Jobs — Верстка и лендинги",
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

    # Dispatch alert to owner's Telegram with inline action buttons
    try:
        from app.services.lead_notifier import lead_notifier
        await lead_notifier.notify_new_order(order)
    except Exception as n_err:
        logger.warning("Could not dispatch simulated order notification: %s", n_err)

    return TelegramOrderOut.model_validate(order)


@router.post("/orders/{order_id}/respond", response_model=TelegramOrderOut)
async def trigger_order_response(order_id: str, session: AsyncSession = Depends(get_session)) -> TelegramOrderOut:
    order = await session.get(TelegramOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Deduct 1 credit for AI response
    user = await get_or_create_user(session)
    await check_and_spend(
        session=session,
        user_id=user.id,
        amount=settings.credits_per_outreach,
        module_name="ai_response",
        description=f"AI-отклик на заказ {order.summary or order.id}",
    )

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


class KworkDraftRequest(BaseModel):
    order_text: str = Field(..., min_length=10, max_length=6000)
    style: str = Field(default="balanced")
    portfolio_url: str | None = None
    price_hint: str | None = None
    deadline_hint: str | None = None
    include_portfolio: bool = True
    save_to_history: bool = True


class KworkDraftOut(BaseModel):
    proposal: str
    style: str
    char_count: int
    order_id: str | None = None


@router.post("/kwork/draft", response_model=KworkDraftOut)
async def create_kwork_proposal_draft(
    payload: KworkDraftRequest,
    session: AsyncSession = Depends(get_session),
) -> KworkDraftOut:
    """Generate a tailored Kwork bid/proposal from pasted order text."""
    norm_style = payload.style if payload.style in ("balanced", "short", "demo_first", "expert") else "balanced"
    proposal = await build_kwork_proposal(
        order_text=payload.order_text,
        style=norm_style,
        portfolio_url=payload.portfolio_url,
        price_hint=payload.price_hint,
        deadline_hint=payload.deadline_hint,
        include_portfolio=payload.include_portfolio,
    )

    saved_id: str | None = None
    if payload.save_to_history:
        order = TelegramOrder(
            chat_id="kwork.ru",
            chat_title="Kwork — Конструктор",
            source="kwork",
            message_id=random.randint(100000, 999999),
            author_username=None,
            author_name="Ручная заявка Kwork",
            raw_text=payload.order_text.strip(),
            summary=extract_order_summary(payload.order_text),
            category="Kwork отклик",
            budget=payload.price_hint.strip() if payload.price_hint and payload.price_hint.strip() else None,
            response_text=proposal,
            status="draft",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        saved_id = order.id

    return KworkDraftOut(
        proposal=proposal,
        style=norm_style,
        char_count=len(proposal),
        order_id=saved_id,
    )


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

    success, error_msg = await telegram_manager.broadcast_promo(chat_id, message_text)

    broadcast = TelegramBroadcast(
        chat_id=chat_id,
        chat_title=chat_title,
        message_text=message_text,
        portfolio_url=portfolio,
        status="sent" if success else "failed",
        error=error_msg,
    )
    session.add(broadcast)

    if success and target:
        target.last_post_at = utcnow()
        cd = target.cooldown_minutes or 120
        target.next_post_at = utcnow() + timedelta(minutes=cd)
        session.add(target)

    await session.commit()
    await session.refresh(broadcast)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось опубликовать пост в Telegram: {error_msg or 'неизвестная ошибка'}",
        )

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
    target = await session.scalar(
        select(TelegramChatTarget).where(
            (TelegramChatTarget.id == chat_id) | (TelegramChatTarget.chat_id == chat_id)
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Канал не найден")

    portfolio = getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/")
    if target.custom_text and len(target.custom_text.strip()) > 10:
        message_text = target.custom_text.replace("{portfolio}", portfolio)
    else:
        message_text = await generate_ai_promo(portfolio)

    success, error_msg = await telegram_manager.broadcast_promo(target.chat_id, message_text)

    broadcast = TelegramBroadcast(
        chat_id=target.chat_id,
        chat_title=target.title or target.chat_id,
        message_text=message_text,
        portfolio_url=portfolio,
        status="sent" if success else "failed",
        error=error_msg,
    )
    session.add(broadcast)

    if success:
        target.last_post_at = utcnow()
        cd = target.cooldown_minutes or 120
        target.next_post_at = utcnow() + timedelta(minutes=cd)
        session.add(target)

    await session.commit()
    await session.refresh(broadcast)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось опубликовать пост в Telegram: {error_msg or 'неизвестная ошибка'}",
        )

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
async def update_settings(payload: TelegramSettingsUpdate, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models import AppSetting

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

    # Save to Supabase app_settings table
    val = {
        "portfolio_url": settings.telegram_portfolio_url,
        "auto_response_enabled": settings.telegram_auto_response_enabled,
        "auto_posting_enabled": settings.telegram_auto_posting_enabled,
        "working_hours_enabled": settings.telegram_working_hours_enabled,
        "working_hours_start": settings.telegram_working_hours_start,
        "working_hours_end": settings.telegram_working_hours_end,
        "telegram_auto_response_delay_min": settings.telegram_auto_response_delay_min,
        "telegram_auto_response_delay_max": settings.telegram_auto_response_delay_max,
        "telegram_broadcast_interval_minutes": settings.telegram_broadcast_interval_minutes,
        "keywords": settings.telegram_keywords,
        "stop_words": settings.telegram_stop_words,
    }
    st = await session.get(AppSetting, "telegram_settings")
    if st:
        st.value = val
    else:
        session.add(AppSetting(key="telegram_settings", value=val))
    await session.commit()

    return {"status": "ok", "message": "Настройки Telegram сохранены в Supabase"}


@router.get("/portfolio-screenshot")
async def get_portfolio_screenshot():
    """Serves the current portfolio screenshot image."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    static_file = Path(__file__).resolve().parent.parent / "static" / "portfolio_hero.png"
    if static_file.is_file():
        return FileResponse(static_file.as_posix(), media_type="image/png")
    data_file = DATA_DIR / "portfolio_hero.png"
    if data_file.is_file():
        return FileResponse(data_file.as_posix(), media_type="image/png")
    raise HTTPException(status_code=404, detail="Скриншот портфолио пока не создан")


@router.post("/portfolio-screenshot/refresh")
async def refresh_portfolio_screenshot() -> dict:
    """Takes a fresh high-res screenshot of the first page of the portfolio."""
    import urllib.request
    import json
    from pathlib import Path

    target = getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/") or "https://murasaki-portfolio.vercel.app/"
    try:
        api_url = f"https://api.microlink.io/?url={target}&screenshot=true"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            img_url = data.get("data", {}).get("screenshot", {}).get("url")

        if not img_url:
            raise ValueError("Не удалось получить снимок через сервис рендеринга")

        img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(img_req, timeout=20) as img_resp:
            content = img_resp.read()

        static_dir = Path(__file__).resolve().parent.parent / "static"
        for folder in [static_dir, DATA_DIR]:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "portfolio_hero.png").write_bytes(content)

        return {"status": "ok", "message": "Скриншот первой страницы портфолио успешно обновлен!"}
    except Exception as exc:
        logger.error("Failed refreshing portfolio screenshot: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ошибка создания скриншота: {exc}")


@router.post("/portfolio-screenshot/upload")
async def upload_portfolio_screenshot(file: UploadFile = File(...)) -> dict:
    """Allows uploading a custom image/screenshot for Telegram promo posts."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл пустой")

    from pathlib import Path
    static_dir = Path(__file__).resolve().parent.parent / "static"
    for folder in [static_dir, DATA_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "portfolio_hero.png").write_bytes(content)

    return {"status": "ok", "message": "Новое изображение для постов успешно сохранено!"}


# --- TGStat Discovery Endpoints ---
@router.get("/tgstat/status", response_model=TGStatStatusOut)
async def get_tgstat_status(session: AsyncSession = Depends(get_session)) -> TGStatStatusOut:
    from app.models import AppSetting, JoinQueue
    setting = await session.get(AppSetting, "tgstat_token")
    token = (setting.value.get("token") if setting and setting.value else None) or os.getenv("TGSTAT_TOKEN")
    preview = f"{token[:4]}...{token[-4:]}" if token and len(token) > 8 else (token if token else None)

    try:
        queue_count = await session.scalar(select(func.count(JoinQueue.id))) or 0
    except Exception:
        queue_count = 0

    from tgstat_collector import DEFAULT_CATEGORIES, DEFAULT_KEYWORDS
    return TGStatStatusOut(
        has_token=bool(token),
        token_preview=preview,
        default_keywords=DEFAULT_KEYWORDS,
        default_categories=DEFAULT_CATEGORIES,
        queue_count=queue_count,
    )


@router.post("/tgstat/token")
async def save_tgstat_token(payload: TGStatTokenIn, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models import AppSetting
    token = payload.token.strip()
    setting = await session.get(AppSetting, "tgstat_token")
    if not setting:
        setting = AppSetting(key="tgstat_token", value={"token": token})
        session.add(setting)
    else:
        setting.value = {"token": token}
        session.add(setting)
    await session.commit()
    return {"saved": True, "has_token": bool(token)}


@router.post("/tgstat/search", response_model=TGStatSearchOut)
async def search_tgstat(payload: TGStatSearchIn, session: AsyncSession = Depends(get_session)) -> TGStatSearchOut:
    from app.models import AppSetting, TelegramChatTarget
    from tgstat_collector import (
        TGStatCollector,
        DEFAULT_KEYWORDS,
        DEFAULT_CATEGORIES,
        CURATED_DEMO_CHATS,
        clean_username_or_link,
    )

    # 1. Determine token
    token = payload.token.strip() if payload.token else None
    if not token:
        setting = await session.get(AppSetting, "tgstat_token")
        if setting and setting.value:
            token = setting.value.get("token")
    if not token:
        token = os.getenv("TGSTAT_TOKEN") or ""

    # Parse keywords
    kw_raw = payload.keywords.strip()
    if kw_raw:
        keywords = [k.strip() for k in re.split(r"[,;\n]+", kw_raw) if k.strip()]
    else:
        keywords = DEFAULT_KEYWORDS[:3]

    categories = [payload.category] if payload.category and payload.category != "all" else DEFAULT_CATEGORIES[:2]

    # Existing targets
    collector = TGStatCollector(token=token, min_ci=payload.min_ci, min_members=payload.min_members)
    existing = await collector.get_existing_targets()

    items: list[TGStatItem] = []
    total_found = 0
    used_token = False

    if token:
        used_token = True
        try:
            async with collector:
                raw_items = []
                for kw in keywords:
                    res = await collector.search_query(query=kw, peer_type="chat")
                    raw_items.extend(res)
                if payload.category and payload.category != "all":
                    res = await collector.search_query(category=payload.category, peer_type="all")
                    raw_items.extend(res)

                total_found = len(raw_items)
                extracted = await collector.filter_and_extract_targets(
                    raw_items, set(), category_label=payload.category if payload.category != "all" else "freelance"
                )

                seen = set()
                for e in extracted:
                    uname = e["username_or_link"]
                    norm = uname.lower()
                    if norm in seen:
                        continue
                    seen.add(norm)
                    title = e.get("title") or uname.lstrip("@").replace("_", " ").title()
                    is_added = norm in existing
                    items.append(
                        TGStatItem(
                            username_or_link=uname,
                            title=title,
                            category=e.get("category") or "фриланс",
                            members_count=e.get("members_count", 0),
                            is_already_added=is_added,
                        )
                    )
        except Exception as exc:
            logger.warning("Error querying live TGStat: %s", exc)

    # If no token or no items from live API (or demo/fallback)
    if not items:
        total_found = len(CURATED_DEMO_CHATS)
        for d in CURATED_DEMO_CHATS:
            uname = d["username_or_link"]
            norm = uname.lower()
            title = uname.lstrip("@").replace("_", " ").title()
            is_added = norm in existing
            items.append(
                TGStatItem(
                    username_or_link=uname,
                    title=title,
                    category=d.get("category", "фриланс"),
                    members_count=d.get("members_count", 15000),
                    is_already_added=is_added,
                )
            )

    saved_count = 0
    if payload.auto_add and items:
        for it in items:
            if not it.is_already_added:
                new_target = TelegramChatTarget(
                    chat_id=it.username_or_link,
                    title=it.title or it.username_or_link,
                    username=it.username_or_link.lstrip("@"),
                    kind="both",
                    cooldown_minutes=120,
                    is_active=True,
                )
                session.add(new_target)
                it.is_already_added = True
                saved_count += 1
        await session.commit()

    return TGStatSearchOut(
        total_found=total_found,
        saved_count=saved_count,
        used_token=used_token,
        items=items,
    )


@router.post("/tgstat/add-targets")
async def add_tgstat_targets(payload: TGStatAddTargetsIn, session: AsyncSession = Depends(get_session)) -> dict:
    from app.models import TelegramChatTarget, JoinQueue
    from tgstat_collector import clean_username_or_link

    added_count = 0
    for it in payload.items:
        clean_handle = clean_username_or_link(it.username_or_link)
        if not clean_handle:
            continue
        existing = await session.scalar(
            select(TelegramChatTarget).where(
                (TelegramChatTarget.chat_id == clean_handle) | (TelegramChatTarget.username == clean_handle.lstrip("@"))
            )
        )
        if not existing:
            target = TelegramChatTarget(
                chat_id=clean_handle,
                title=it.title or clean_handle,
                username=clean_handle.lstrip("@"),
                kind=payload.kind,
                cooldown_minutes=payload.cooldown_minutes,
                auto_post_enabled=payload.auto_post_enabled,
                is_active=True,
            )
            session.add(target)
            added_count += 1

        try:
            jq_existing = await session.scalar(
                select(JoinQueue).where(JoinQueue.username_or_link == clean_handle)
            )
            if not jq_existing:
                jq_entry = JoinQueue(
                    username_or_link=clean_handle,
                    category=it.category or "freelance",
                    members_count=it.members_count or 0,
                    status="pending",
                )
                session.add(jq_entry)
        except Exception as e:
            logger.debug("JoinQueue insert note: %s", e)

    await session.commit()
    return {"added_count": added_count}
