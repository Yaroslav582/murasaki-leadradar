from __future__ import annotations

import asyncio
import html
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import (
    AppSetting,
    DemoSite,
    Dialog,
    Lead,
    Message,
    OutreachLead,
    TgAccount,
    new_id,
    utcnow,
)
from app.services.account_pool import account_pool
from app.services.ai_router import ask_ai
from app.services.billing import check_and_spend

logger = logging.getLogger(__name__)

MSK_TZ = timezone(timedelta(hours=3))


def msk_now() -> datetime:
    """Return current Moscow time (UTC+3)."""
    return datetime.now(MSK_TZ)


def normalize_ru_phone(raw: str | None) -> str | None:
    """Normalize any phone string into clean +7XXXXXXXXXX format."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 10:
        return None
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) > 11 and digits.startswith("7"):
        digits = digits[:11]
    return f"+{digits}"


def _split_target_query(raw_query: str) -> tuple[str, str]:
    """Split 'Салон красоты Новороссийск' into (search_query, city)."""
    parts = [p for p in (raw_query or "").strip().split() if p]
    if len(parts) >= 2:
        city = parts[-1]
        query = " ".join(parts[:-1])
        return query, city
    return (raw_query.strip() or "Услуги"), "Краснодар"


class OutreachWorker:
    """
    Orchestrates both manual outreach campaigns and the autonomous background
    userbot outreach pipeline (lead discovery -> demo generation -> LLM pitch -> TG DM).
    """

    def __init__(self) -> None:
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._followup_task: asyncio.Task | None = None
        self._autonomous_task: asyncio.Task | None = None
        self._userbot_client: Any = None
        self._userbot_account_id: str | None = None
        self._userbot_account_label: str | None = None
        self._userbot_uses_env_session: bool = False
        self._paused_until: datetime | None = None
        self._peer_flood_streak: int = 0
        self._last_error: str | None = None
        self._last_limit_alert: dict[str, datetime] = {}
        self._last_recovery_probe: dict[str, datetime] = {}
        self._last_spambot_check: dict[str, datetime] = {}
        self._stats: dict[str, Any] = {
            "total_sent": 0,
            "total_failed": 0,
            "is_running": False,
            "current_lead": None,
        }

    @property
    def stats(self) -> dict[str, Any]:
        return self._stats

    # ── Autonomous Configuration & Status ─────────────────────────────────────

    def is_in_work_window(self, now_msk: datetime | None = None) -> bool:
        now = now_msk or msk_now()
        start_h = int(getattr(settings, "outreach_work_hours_start", 11))
        end_h = int(getattr(settings, "outreach_work_hours_end", 18))
        return start_h <= now.hour < end_h

    async def load_autonomous_state_from_db(self) -> None:
        """Restore persisted OUTREACH_ENABLED toggle from app_settings if present."""
        try:
            async with SessionLocal() as session:
                st = await session.get(AppSetting, "autonomous_outreach_config")
                if st and isinstance(st.value, dict) and "enabled" in st.value:
                    settings.outreach_enabled = bool(st.value["enabled"])
        except Exception as exc:
            logger.debug("Notice loading autonomous_outreach_config: %s", exc)

    async def set_autonomous_enabled(self, enabled: bool) -> dict[str, Any]:
        settings.outreach_enabled = bool(enabled)
        if enabled:
            self._paused_until = None
            self._peer_flood_streak = 0
            self._last_error = None
        try:
            async with SessionLocal() as session:
                st = await session.get(AppSetting, "autonomous_outreach_config")
                val = {"enabled": bool(enabled), "updated_at": utcnow().isoformat()}
                if st:
                    st.value = val
                else:
                    session.add(AppSetting(key="autonomous_outreach_config", value=val))
                await session.commit()
        except Exception as exc:
            logger.debug("Notice saving autonomous_outreach_config: %s", exc)
        return await self.get_autonomous_status()

    async def clear_pause(self) -> dict[str, Any]:
        """Manually clear flood pause so the autonomous worker resumes immediately."""
        self._paused_until = None
        self._peer_flood_streak = 0
        self._last_error = None
        settings.outreach_enabled = True
        # The resume button means "I checked @SpamBot, the account is fine" —
        # un-park accounts and clear temporary cooldowns so it tries again right away.
        try:
            async with SessionLocal() as session:
                res = await session.execute(
                    select(TgAccount).where(
                        or_(TgAccount.status == "spamblock", TgAccount.flood_until.isnot(None))
                    )
                )
                for acc in res.scalars().all():
                    if acc.status in ("spamblock", "floodwait"):
                        acc.status = "active"
                    acc.flood_until = None
                    acc.updated_at = utcnow()
                    session.add(acc)
                await session.commit()
        except Exception as exc:
            logger.debug("Notice clearing spamblock state: %s", exc)
        self._last_recovery_probe.clear()
        self._last_spambot_check.clear()
        return await self.get_autonomous_status()

    async def get_autonomous_status(self) -> dict[str, Any]:
        now_m = msk_now()
        day_start_msk = now_m.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_utc = day_start_msk.astimezone(timezone.utc)

        async with SessionLocal() as session:
            sent_today = int(
                await session.scalar(
                    select(func.count(OutreachLead.id)).where(
                        OutreachLead.status == "sent",
                        OutreachLead.sent_at >= day_start_utc,
                    )
                )
                or 0
            )
            queued_count = int(
                await session.scalar(
                    select(func.count(OutreachLead.id)).where(OutreachLead.status == "queued")
                )
                or 0
            )
            total_sent = int(
                await session.scalar(
                    select(func.count(OutreachLead.id)).where(OutreachLead.status == "sent")
                )
                or 0
            )
            skipped_no_tg = int(
                await session.scalar(
                    select(func.count(OutreachLead.id)).where(OutreachLead.status == "skipped_no_tg")
                )
                or 0
            )
            skipped_bad_quality = int(
                await session.scalar(
                    select(func.count(OutreachLead.id)).where(OutreachLead.status == "skipped_bad_quality")
                )
                or 0
            )
            available_accounts = int(
                await session.scalar(
                    select(func.count(TgAccount.id)).where(
                        TgAccount.status.in_(["active", "warming"]),
                        TgAccount.session_string.isnot(None),
                        TgAccount.session_string != "",
                    )
                )
                or 0
            )
            account_status: str | None = None
            account_flood_until: str | None = None
            if self._userbot_account_id:
                acc = await session.get(TgAccount, self._userbot_account_id)
                if acc:
                    account_status = acc.status
                    account_flood_until = acc.flood_until.isoformat() if acc.flood_until else None

        session_str = (getattr(settings, "outreach_session_string", None) or "").strip()
        session_label = "OUTREACH_SESSION_STRING (.env)" if session_str else None
        if not session_str:
            async with SessionLocal() as session:
                acc = await session.scalar(
                    select(TgAccount)
                    .where(
                        TgAccount.status.in_(["active", "warming"]),
                        TgAccount.session_string.isnot(None),
                        TgAccount.session_string != "",
                    )
                    .order_by(TgAccount.daily_actions_count.asc(), TgAccount.updated_at.asc())
                    .limit(1)
                )
                if acc:
                    session_label = f"@{acc.username}" if acc.username else acc.phone

        return {
            "enabled": bool(getattr(settings, "outreach_enabled", False)),
            "is_running": bool(self._autonomous_task and not self._autonomous_task.done()),
            "session_configured": bool(session_str or session_label),
            "session_label": session_label,
            "in_work_window": self.is_in_work_window(now_m),
            "work_hours": f"{settings.outreach_work_hours_start:02d}:00–{settings.outreach_work_hours_end:02d}:00 МСК",
            "paused_until": self._paused_until.isoformat() if self._paused_until else None,
            "sent_today": sent_today,
            "daily_limit": int(settings.outreach_daily_limit),
            "queued_count": queued_count,
            "total_sent": total_sent,
            "skipped_no_tg": skipped_no_tg,
            "skipped_bad_quality": skipped_bad_quality,
            "available_accounts": available_accounts,
            "account_status": account_status,
            "account_flood_until": account_flood_until,
            "last_error": self._last_error,
        }

    # ── Telethon Userbot Client & Incoming Reply Forwarder ────────────────────

    async def _probe_limited_account(self, session: AsyncSession) -> TgAccount | None:
        """Re-check accounts parked by Telegram via @SpamBot.

        Returns a recovered account (now messages strangers again) or None.
        Probes are throttled per account so @SpamBot is not hammered.
        """
        now = utcnow()
        probe_interval = timedelta(hours=max(1, int(settings.outreach_peer_flood_probe_hours)))
        stmt = (
            select(TgAccount)
            .where(
                TgAccount.status.in_(["spamblock", "floodwait"]),
                TgAccount.session_string.isnot(None),
                TgAccount.session_string != "",
            )
            .order_by(TgAccount.updated_at.asc())
            .limit(10)
        )
        accounts = list((await session.execute(stmt)).scalars().all())
        for acc in accounts:
            due = acc.flood_until
            if due is not None and due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            # Hard flood-wait is still running — respect it, don't even probe.
            if acc.status == "floodwait" and due is not None and due > now:
                continue
            last = self._last_recovery_probe.get(acc.id)
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last is not None and now - last < probe_interval:
                continue
            self._last_recovery_probe[acc.id] = now
            try:
                res = await account_pool.check_account_health(session, acc)
            except Exception as exc:
                logger.debug("Account health probe failed for %s: %s", acc.phone, exc)
                res = {}
            if res.get("status") == "active":
                logger.info("Account %s recovered from Telegram spam limit, resuming", acc.phone)
                self._last_error = None
                self._paused_until = None
                self._peer_flood_streak = 0
                try:
                    from app.services.lead_notifier import lead_notifier
                    label = f"@{acc.username}" if acc.username else acc.phone
                    await lead_notifier.send_admin_text(
                        f"✅ <b>Аккаунт {html.escape(label)} снова может писать!</b>\n"
                        "Ограничение Telegram снято — рассылка продолжается автоматически."
                    )
                except Exception:
                    pass
                return acc
            # Still limited: push flood_until forward so it is not probed again instantly.
            acc.flood_until = now + probe_interval
            session.add(acc)
            try:
                await session.commit()
            except Exception:
                pass
        return None

    async def _try_recover_accounts(self) -> bool:
        """Probe parked accounts while the worker is paused; True if one recovered."""
        try:
            async with SessionLocal() as db:
                acc = await self._probe_limited_account(db)
                return acc is not None
        except Exception as exc:
            logger.debug("Recovery probe notice: %s", exc)
            return False

    async def _get_userbot_client(self) -> Any | None:
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession

        session_str = (getattr(settings, "outreach_session_string", None) or "").strip()
        client: Any = None

        if session_str:
            self._userbot_account_id = None
            self._userbot_account_label = "OUTREACH_SESSION_STRING"
            self._userbot_uses_env_session = True
            if self._userbot_client is not None:
                try:
                    if not self._userbot_client.is_connected():
                        await self._userbot_client.connect()
                    if await self._userbot_client.is_user_authorized():
                        return self._userbot_client
                except Exception:
                    self._userbot_client = None

            api_id = int(settings.telegram_api_id or 2040)
            api_hash = settings.telegram_api_hash or "b18441a1ff607e10a989891a5462e627"

            proxy_cfg = None
            if settings.proxy_url and settings.proxy_url.strip():
                try:
                    from urllib.parse import urlparse
                    p = urlparse(settings.proxy_url.strip())
                    if p.hostname and p.port:
                        proxy_cfg = (p.scheme or "socks5", p.hostname, p.port, True, p.username, p.password)
                except Exception:
                    proxy_cfg = None

            client = TelegramClient(
                StringSession(session_str),
                api_id,
                api_hash,
                proxy=proxy_cfg,
                device_model="Samsung Galaxy S23",
                system_version="Android 14",
                app_version="10.8.0",
            )
            await client.connect()
            if not await client.is_user_authorized():
                logger.error("Autonomous outreach: OUTREACH_SESSION_STRING is unauthorized or expired")
                return None
        else:
            # Auto-fallback: pick a healthy account from tg_accounts pool (tab "Аккаунты").
            # Accounts parked by Telegram (spamblock/floodwait) and accounts that already
            # hit today's cold-DM budget are skipped, so one bad account can't block the pipeline.
            self._userbot_uses_env_session = False
            async with SessionLocal() as db:
                acc = await account_pool.get_available_account(
                    db, max_daily_outreach=int(settings.outreach_account_daily_limit)
                )
                if acc is None:
                    # Everything is parked: re-check via @SpamBot and resume if the limit lifted.
                    acc = await self._probe_limited_account(db)
                if not acc or not acc.session_string:
                    logger.warning(
                        "Autonomous outreach: no usable account in pool (all are parked by Telegram)"
                    )
                    self._userbot_account_id = None
                    self._userbot_account_label = None
                    return None
                client = await account_pool.get_client_for_account(acc)
                if not client.is_connected():
                    await client.connect()
                if not await client.is_user_authorized():
                    logger.warning("Autonomous outreach: pool account %s is not authorized", acc.phone)
                    try:
                        acc.status = "banned"
                        await db.commit()
                    except Exception:
                        pass
                    self._userbot_account_id = None
                    self._userbot_account_label = None
                    return None
                self._userbot_account_id = acc.id
                self._userbot_account_label = f"@{acc.username}" if acc.username else acc.phone

        if not getattr(client, "_outreach_reply_handler_attached", False):
            client._outreach_reply_handler_attached = True

            @client.on(events.NewMessage(incoming=True))
            async def _forward_incoming_reply(event):
                try:
                    if not event.is_private:
                        return
                    chat_id = event.chat_id
                    if chat_id in (777000, 4244, 4000000):
                        return
                    sender = await event.get_sender()
                    if getattr(sender, "bot", False):
                        return
                    text_body = (event.raw_text or "").strip()
                    if not text_body:
                        return

                    sender_id = getattr(sender, "id", None)
                    username = getattr(sender, "username", None)
                    full_name = f"{getattr(sender, 'first_name', '') or ''} {getattr(sender, 'last_name', '') or ''}".strip()

                    company_info = ""
                    async with SessionLocal() as db:
                        conds = []
                        if sender_id:
                            conds.append(OutreachLead.tg_user_id == int(sender_id))
                        if username:
                            conds.append(OutreachLead.tg_username == username)
                        if conds:
                            row = await db.scalar(select(OutreachLead).where(or_(*conds)))
                            if row:
                                company_info = f"\n🏢 <b>Компания:</b> {html.escape(row.company_name)} ({html.escape(row.city)})"
                                if row.demo_url:
                                    company_info += f"\n🔗 <b>Демо:</b> {html.escape(row.demo_url)}"

                    from app.services.lead_notifier import lead_notifier
                    handle_str = f"@{username}" if username else f"id:{sender_id}"
                    alert = (
                        "💬 <b>Новый ответ от клиента в аутрич-аккаунт!</b>\n"
                        f"👤 <b>От:</b> {html.escape(full_name or handle_str)} (<code>{html.escape(handle_str)}</code>)"
                        f"{company_info}\n\n"
                        f"📩 <b>Сообщение:</b>\n{html.escape(text_body[:1500])}"
                    )
                    await lead_notifier.send_admin_text(alert)
                except Exception as exc:
                    logger.debug("Reply forwarder notice: %s", exc)

        self._userbot_client = client
        return client

    # ── Pipeline Step 2: Replenish Queue ──────────────────────────────────────

    async def replenish_queue(self, session: AsyncSession) -> int:
        """Discover fresh businesses without a website and enqueue them with strict deduplication."""
        queued_count = int(
            await session.scalar(
                select(func.count(OutreachLead.id)).where(OutreachLead.status == "queued")
            )
            or 0
        )
        if queued_count >= 5:
            return 0

        raw_queries = [
            q.strip()
            for q in (getattr(settings, "outreach_target_queries", "") or "").split(",")
            if q.strip()
        ]
        if not raw_queries:
            raw_queries = ["Салон красоты Новороссийск", "Автосервис Новороссийск", "Кофейня Краснодар"]

        chosen = random.choice(raw_queries)
        query_term, city = _split_target_query(chosen)
        logger.info("Autonomous outreach: replenishing queue with '%s' in '%s'", query_term, city)

        places = []
        try:
            from app.providers.yandex_web import YandexMapsWebProvider
            places = await YandexMapsWebProvider().search(
                city=city, categories=[], query=query_term, limit=25
            )
        except Exception as exc:
            logger.warning("YandexMapsWebProvider replenish error: %s", exc)

        if not places:
            try:
                from app.providers.zoon import ZoonProvider
                places = await ZoonProvider().search(
                    city=city, categories=[], query=query_term, limit=20
                )
            except Exception as exc:
                logger.debug("Zoon fallback replenish notice: %s", exc)

        added = 0
        for p in places:
            if p.website_url and str(p.website_url).strip():
                continue

            norm_phone = normalize_ru_phone(p.phone)
            org_id = str(p.source_id or "").strip() or None
            tg_raw = (p.social_links or {}).get("telegram")
            tg_user = None
            if tg_raw:
                m = re.search(r"(?:t\.me/|@)([A-Za-z0-9_]{4,40})", str(tg_raw))
                if m:
                    tg_user = m.group(1)

            if not norm_phone and not tg_user:
                continue

            dedup_conds = []
            if org_id:
                dedup_conds.append(OutreachLead.yandex_org_id == org_id)
            if norm_phone:
                dedup_conds.append(OutreachLead.phone == norm_phone)
            if dedup_conds:
                exists = await session.scalar(select(OutreachLead.id).where(or_(*dedup_conds)))
                if exists:
                    continue

            item = OutreachLead(
                yandex_org_id=org_id,
                company_name=(p.name or "").strip(),
                category=(p.category or query_term).strip(),
                city=(p.city or city).strip(),
                address=(p.address or "").strip(),
                phone=norm_phone,
                tg_username=tg_user,
                rating=p.rating,
                reviews_count=p.reviews_count or 0,
                photos=list(p.photos or []),
                status="queued",
            )
            session.add(item)
            added += 1

        if added:
            await session.commit()
            logger.info("Autonomous outreach: enqueued %d new leads from '%s'", added, chosen)
        return added

    # ── Pipeline Step 3: Resolve Telegram Contact ─────────────────────────────

    async def _find_channel_admin(self, client: Any, channel_username: str) -> Any | None:
        """Resolve personal admin User from a channel's public t.me preview, or None."""
        from telethon.tl.types import User
        from app.services.telegram_channel_scraper import scrape_telegram_channel

        info = await scrape_telegram_channel(channel_username, limit_photos=0)
        admin_username = info.get("admin_username")
        if not admin_username:
            return None
        try:
            admin_entity = await client.get_entity(admin_username)
            if isinstance(admin_entity, User) and not getattr(admin_entity, "bot", False):
                return admin_entity
        except Exception as exc:
            logger.debug("Admin lookup failed for @%s (from @%s): %s", admin_username, channel_username, exc)
        return None

    async def resolve_outreach_contact(self, client: Any, item: OutreachLead) -> tuple[Any | None, bool]:
        """Resolve personal Telegram User entity. Returns (entity, imported_as_temp_contact)."""
        from telethon.tl.functions.contacts import DeleteContactsRequest, ImportContactsRequest
        from telethon.tl.types import InputPhoneContact, User

        if item.tg_username:
            try:
                entity = await client.get_entity(item.tg_username)
                if isinstance(entity, User) and not getattr(entity, "bot", False):
                    item.tg_user_id = int(entity.id)
                    item.tg_username = getattr(entity, "username", None) or item.tg_username
                    return entity, False

                # Non-user entity (channel/group) or bot -> try finding personal admin handle
                admin_entity = await self._find_channel_admin(client, item.tg_username)
                if admin_entity is not None:
                    item.tg_user_id = int(admin_entity.id)
                    item.tg_username = getattr(admin_entity, "username", None) or item.tg_username
                    return admin_entity, False

                item.error_detail = "Канал/бот без личного юзернейма админа"
                return None, False
            except Exception as exc:
                logger.debug("Username lookup failed for @%s: %s", item.tg_username, exc)

        if item.phone:
            contact = InputPhoneContact(
                client_id=0,
                phone=item.phone,
                first_name=(item.company_name or "Клиент")[:64],
                last_name="",
            )
            res = await client(ImportContactsRequest([contact]))
            users = getattr(res, "users", []) or []
            for u in users:
                if isinstance(u, User) and not getattr(u, "bot", False):
                    item.tg_user_id = int(u.id)
                    if getattr(u, "username", None):
                        item.tg_username = u.username
                    # Keep temporarily until send_message finishes, then delete cleanly
                    return u, True
            # No valid user found -> delete any residual contact immediately
            if users:
                try:
                    await client(DeleteContactsRequest(id=users))
                except Exception:
                    pass

        return None, False

    # ── Pipeline Step 5: LLM Pitch Generation ─────────────────────────────────

    async def generate_autonomous_pitch(self, item: OutreachLead, demo_url: str) -> str:
        """Generate a short, natural 3-4 sentence developer pitch via TEXT_MODELS_CHAIN."""
        system_prompt = (
            "Ты — частный веб-разработчик, пишешь владельцу локального бизнеса в Telegram. "
            "Нужно короткое, живое сообщение на 3–4 предложения: без канцеляризмов, без 'уникальных торговых предложений' "
            "и без спам-напора. Обращение уважительное на 'вы'."
        )
        user_prompt = (
            f"Компания: {item.company_name}\n"
            f"Ниша: {item.category}\n"
            f"Город: {item.city}\n"
            f"Ссылка на готовый демо-сайт: {demo_url}\n\n"
            "Обязательно включи:\n"
            "1. Упоминание компании и города.\n"
            "2. Ссылку на персональный демо-концепт.\n"
            "3. Предложение запустить сайт под ключ на их домене за 5 000 ₽ (собираешь свежие кейсы в портфолио).\n"
            "4. Короткий контакт/призыв ответить сюда в ЛС или в @Murasaki_website.\n"
            "Верни ТОЛЬКО готовый текст сообщения."
        )
        try:
            text = await ask_ai(
                user_prompt,
                system_prompt=system_prompt,
                task_type="fast",
                max_tokens=260,
                temperature=0.65,
            )
            if text and demo_url in text and len(text.strip()) >= 40:
                return text.strip()
        except Exception as exc:
            logger.debug("Autonomous pitch LLM fallback: %s", exc)

        return (
            f"Здравствуйте! Увидел «{item.company_name}» на картах в г. {item.city}, заметил, что у вас пока нет своего сайта. "
            f"Набросал для вас рабочий демо-концепт с прайсом и записью в мессенджер: {demo_url}\n\n"
            "Сейчас собираю свежие кейсы в портфолио, поэтому могу доработать и запустить сайт на вашем домене под ключ за 5 000 ₽. "
            "Если интересно — напишите здесь или в @Murasaki_website."
        )

    async def _prepare_demo(
        self, session: AsyncSession, item: OutreachLead
    ) -> tuple[Lead | None, str | None, str | None, str | None]:
        """Build a landing demo + pitch for a lead, or reuse one from a previous attempt.

        Reusing matters: a PeerFlood/FloodWait happens *after* the demo was generated,
        so retrying must not burn another LLM landing and create duplicate Lead/Demo rows.

        Returns ``(lead_row, demo_url, pitch_text, skip_reason)``. When ``skip_reason``
        is set the lead cannot be used (missing quality photos).
        """
        if item.demo_url and item.message_text:
            lead_row = None
            if item.demo_id:
                lead_row = await session.scalar(select(Lead).where(Lead.demo_id == item.demo_id))
            if lead_row is not None:
                logger.info("Autonomous outreach: reusing existing demo for '%s'", item.company_name)
                return lead_row, item.demo_url, item.message_text, None

        from app.services.demos import generate_unique_slug, public_demo_url
        from app.services.design_systems import resolve_style_id
        from app.services.landing import generate_landing_html
        from app.services.media_collector import collect_media

        lead_dict = {
            "id": item.id,
            "name": item.company_name,
            "category": item.category,
            "city": item.city,
            "address": item.address,
            "phone": item.phone,
            "website_url": None,
            "has_website": False,
            "rating": item.rating,
            "reviews_count": item.reviews_count,
            "social_links": {"telegram": f"https://t.me/{item.tg_username}"} if item.tg_username else {},
            "opening_hours": [],
            "photos": list(item.photos or []),
        }

        try:
            media_res = await collect_media(lead_dict, max_items=10)
            collected_photos = media_res.get("photos") or list(item.photos or [])
            real_photos = media_res.get("real_photos") if "real_photos" in media_res else collected_photos
        except Exception:
            collected_photos = list(item.photos or [])
            real_photos = [
                p for p in collected_photos
                if "images.unsplash.com" not in p and "/static/stock/" not in p
            ]

        if not collected_photos:
            return None, None, None, "No quality photos found"

        item.photos = collected_photos[:10]
        lead_dict["photos"] = item.photos
        lead_dict["hero_product"] = []
        lead_dict["work_captions"] = {}
        lead_dict["interior_photos"] = []
        lead_dict["rejected_photos"] = []

        if real_photos:
            try:
                from app.services.ai_router import sort_business_photos
                sorted_ph = await asyncio.wait_for(
                    sort_business_photos(
                        real_photos,
                        business_category=item.category,
                        business_name=item.company_name,
                    ),
                    timeout=25.0,
                )
                lead_dict["hero_product"] = sorted_ph.get("hero_product") or []
                lead_dict["work_captions"] = dict(sorted_ph.get("work_captions") or {})
                lead_dict["interior_photos"] = sorted_ph.get("interior") or []
                lead_dict["rejected_photos"] = sorted_ph.get("rejected") or sorted_ph.get("trash") or []
            except Exception:
                pass

        lead_row = Lead(
            name=item.company_name,
            category=item.category,
            city=item.city,
            address=item.address,
            phone=item.phone,
            has_website=False,
            rating=item.rating,
            reviews_count=item.reviews_count,
            social_links=lead_dict["social_links"],
            source="yandex_web",
            source_id=item.yandex_org_id,
            status="new",
            photos=item.photos,
        )
        session.add(lead_row)
        await session.flush()

        effective_style = resolve_style_id(None, item.category)
        demo_slug = await generate_unique_slug(session, item.company_name, item.city)
        demo_url = public_demo_url(demo_slug)
        demo_id = new_id()

        html_code, _engine = await generate_landing_html(
            lead_dict, style_id=effective_style, public_url=demo_url
        )

        pitch_text = await self.generate_autonomous_pitch(item, demo_url)

        demo = DemoSite(
            id=demo_id,
            lead_id=lead_row.id,
            slug=demo_slug,
            title=f"Демо для {item.company_name}",
            html=html_code,
            message=pitch_text,
            published=True,
            style=effective_style,
        )
        session.add(demo)
        lead_row.demo_id = demo.id
        item.demo_id = demo.id
        item.demo_url = demo_url
        item.status = "demo_generated"
        item.message_text = pitch_text
        await session.commit()
        return lead_row, demo_url, pitch_text, None

    # ── Single Autonomous Iteration ───────────────────────────────────────────

    async def run_autonomous_step(self) -> str:
        """Execute one autonomous outreach iteration."""
        if not getattr(settings, "outreach_enabled", False):
            return "disabled"

        now_utc = utcnow()
        if self._paused_until and now_utc < self._paused_until:
            # While paused, keep re-checking accounts parked by Telegram so the worker
            # resumes on its own as soon as the spam limit is lifted.
            if not await self._try_recover_accounts():
                return "paused"
        self._paused_until = None

        now_m = msk_now()
        if not self.is_in_work_window(now_m):
            return "outside_hours"

        day_start_utc = now_m.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

        async with SessionLocal() as session:
            sent_today = int(
                await session.scalar(
                    select(func.count(OutreachLead.id)).where(
                        OutreachLead.status == "sent",
                        OutreachLead.sent_at >= day_start_utc,
                    )
                )
                or 0
            )
            daily_limit = int(settings.outreach_daily_limit)
            if sent_today >= daily_limit:
                return "limit_reached"

            await self.replenish_queue(session)

            item = await session.scalar(
                select(OutreachLead)
                .where(OutreachLead.status == "queued")
                # Prefer leads with a public @username: no ImportContacts needed,
                # which is what most often triggers the new-chat anti-spam.
                .order_by(OutreachLead.tg_username.is_(None).asc(), OutreachLead.created_at.asc())
                .limit(1)
            )
            if item is None:
                return "empty_queue"

            client = await self._get_userbot_client()
            if client is None:
                return "no_client"

            try:
                resolved = await self.resolve_outreach_contact(client, item)
                if isinstance(resolved, tuple):
                    peer_entity, temp_imported = resolved
                else:
                    peer_entity, temp_imported = resolved, False
            except Exception as exc:
                from telethon.errors import FloodWaitError, PeerFloodError
                if isinstance(exc, PeerFloodError):
                    return await self._handle_peer_flood(session, item, exc, stage="ImportContacts")
                if isinstance(exc, FloodWaitError):
                    return await self._handle_flood_wait(exc)
                item.status = "error"
                item.error_detail = f"resolve_error: {exc}"
                session.add(item)
                await session.commit()
                return "error"

            if peer_entity is None:
                item.status = "skipped_no_tg"
                session.add(item)
                await session.commit()
                return "skipped_no_tg"

            # ImportContacts lookup is a Telegram action too — count it against the
            # account's daily budget, otherwise it never gets throttled.
            if temp_imported and self._userbot_account_id:
                try:
                    await account_pool.record_outreach_action(session, self._userbot_account_id)
                except Exception as rec_exc:
                    logger.debug("record_action notice: %s", rec_exc)

            async def _cleanup_temp_contact() -> None:
                if temp_imported:
                    try:
                        from telethon.tl.functions.contacts import DeleteContactsRequest
                        await client(DeleteContactsRequest(id=[peer_entity]))
                    except Exception:
                        pass

            if not (item.company_name and item.company_name.strip()) or not (item.category and item.category.strip()):
                await _cleanup_temp_contact()
                item.status = "skipped_bad_quality"
                item.error_detail = "Missing company_name or category"
                session.add(item)
                await session.commit()
                return "skipped_bad_quality"

            lead_row, demo_url, pitch_text, skip_reason = await self._prepare_demo(session, item)
            if skip_reason or not (demo_url and pitch_text):
                await _cleanup_temp_contact()
                item.status = "skipped_bad_quality"
                item.error_detail = skip_reason or "Demo generation failed"
                session.add(item)
                await session.commit()
                return "skipped_bad_quality"

            # Don't import a contact and message it in the same instant — that burst is
            # exactly what Telegram's new-chat anti-spam flags. Look like a human.
            if temp_imported:
                await asyncio.sleep(random.uniform(20.0, 45.0))

            try:
                await client.send_message(peer_entity, pitch_text, link_preview=False)
                await _cleanup_temp_contact()
                item.status = "sent"
                item.sent_at = utcnow()
                if lead_row is not None:
                    lead_row.status = "sent"
                    session.add(lead_row)
                session.add(item)
                await session.commit()

                # Count the cold DM against this account's daily budget so one
                # account cannot burn through the whole daily limit by itself.
                if self._userbot_account_id:
                    try:
                        await account_pool.record_outreach_action(session, self._userbot_account_id)
                    except Exception as rec_exc:
                        logger.debug("record_action notice: %s", rec_exc)

                self._stats["total_sent"] += 1
                self._peer_flood_streak = 0
                self._last_error = None

                from app.services.lead_notifier import lead_notifier
                new_sent_count = sent_today + 1
                tg_label = f"@{item.tg_username}" if item.tg_username else f"id:{item.tg_user_id}"
                account_line = f"\n📱 <b>Аккаунт:</b> <code>{html.escape(self._userbot_account_label or '—')}</code>"
                report = (
                    "📨 <b>Авто-аутрич: сообщение отправлено</b>\n"
                    f"🏢 <b>Компания:</b> {html.escape(item.company_name)} ({html.escape(item.city)})\n"
                    f"🏷 <b>Ниша:</b> {html.escape(item.category)}\n"
                    f"👤 <b>Контакт:</b> <code>{html.escape(tg_label)}</code>{account_line}\n"
                    f"🔗 <b>Демо:</b> {html.escape(demo_url)}\n"
                    f"📊 <b>Лимит за сегодня:</b> {new_sent_count}/{daily_limit}"
                )
                await lead_notifier.send_admin_text(report)
                return "sent"

            except Exception as exc:
                await _cleanup_temp_contact()
                from telethon.errors import (
                    ChatWriteForbiddenError,
                    FloodWaitError,
                    InputUserDeactivatedError,
                    PeerFloodError,
                    UserIsBlockedError,
                    UserNotMutualContactError,
                    UserPrivacyRestrictedError,
                )
                if isinstance(exc, PeerFloodError):
                    return await self._handle_peer_flood(session, item, exc, stage="send_message")
                if isinstance(exc, FloodWaitError):
                    return await self._handle_flood_wait(exc)
                if isinstance(
                    exc,
                    (
                        UserPrivacyRestrictedError,
                        UserNotMutualContactError,
                        UserIsBlockedError,
                        InputUserDeactivatedError,
                        ChatWriteForbiddenError,
                    ),
                ):
                    # Not a flood: this particular lead simply can't be messaged.
                    # Drop it from the queue instead of retrying it forever.
                    item.status = "skipped_no_tg"
                    item.error_detail = f"Нельзя написать в ЛС: {exc}"
                    session.add(item)
                    await session.commit()
                    logger.info("Outreach lead '%s' is not messageable: %s", item.company_name, exc)
                    return "skipped_no_tg"
                item.status = "error"
                item.error_detail = str(exc)
                session.add(item)
                await session.commit()
                self._last_error = str(exc)
                self._stats["total_failed"] += 1
                return "error"

    async def _handle_flood_wait(self, exc: Any) -> str:
        wait_sec = int(getattr(exc, "seconds", 120)) + 60
        self._last_error = f"FloodWaitError: sleeping {wait_sec}s"
        logger.warning("Autonomous outreach FloodWaitError: sleeping %d seconds", wait_sec)
        if self._userbot_account_id:
            try:
                async with SessionLocal() as db:
                    acc = await db.get(TgAccount, self._userbot_account_id)
                    if acc:
                        acc.status = "floodwait"
                        acc.flood_until = utcnow() + timedelta(seconds=wait_sec)
                        acc.updated_at = utcnow()
                        db.add(acc)
                        await db.commit()
            except Exception as mark_exc:
                logger.debug("Could not record FloodWait on account: %s", mark_exc)
        # A multi-hour wait must not block the loop task: pause instead of sleeping.
        if wait_sec > 900:
            self._paused_until = utcnow() + timedelta(seconds=wait_sec)
            return "flood_wait"
        await asyncio.sleep(wait_sec)
        return "flood_wait"

    async def _spambot_verdict(self, account_id: str) -> str:
        """Ask @SpamBot whether the account is really blocked.

        Returns ``"limited"`` (persistent spam block), ``"clean"`` (no block —
        PEER_FLOOD is just the dynamic anti-spam for new chats) or ``"unknown"``.
        Throttled: at most one check per 30 minutes per account.
        """
        now = utcnow()
        last = self._last_spambot_check.get(account_id)
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is not None and now - last < timedelta(minutes=30):
            return "unknown"
        self._last_spambot_check[account_id] = now
        try:
            async with SessionLocal() as db:
                acc = await db.get(TgAccount, account_id)
                if not acc:
                    return "unknown"
                res = await account_pool.check_account_health(db, acc)
                status = res.get("status")
            if status in ("spamblock", "banned"):
                return "limited"
            if status == "active":
                return "clean"
        except Exception as exc:
            logger.debug("SpamBot verdict failed for %s: %s", account_id, exc)
        return "unknown"

    async def _notify_peer_flood(self, account_label: str, stage: str, detail: str) -> None:
        """Alert the admin about a *persistent* spam block, at most once per few hours."""
        key = f"{account_label}:{stage}"
        now = utcnow()
        last = self._last_limit_alert.get(key)
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is not None and now - last < timedelta(hours=6):
            return
        self._last_limit_alert[key] = now
        try:
            from app.services.lead_notifier import lead_notifier
            await lead_notifier.send_admin_text(
                f"⚠️ <b>@SpamBot подтвердил ограничение аккаунта <code>{html.escape(account_label)}</code></b>\n"
                f"Ошибка <code>PEER_FLOOD</code> на этапе <code>{html.escape(stage)}</code>.\n\n"
                "С этого аккаунта холодные сообщения сейчас невозможны. Рассылка продолжится "
                "с другого аккаунта, если он добавлен, либо автоматически после снятия лимита.\n\n"
                f"🔍 <b>Ответ Telegram:</b> <code>{html.escape(detail[:200])}</code>",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "▶️ Снять паузу и продолжить", "callback_data": "outreach_resume"}]
                    ]
                },
            )
        except Exception:
            pass

    async def _handle_peer_flood(
        self, session: AsyncSession, item: OutreachLead, exc: Any, stage: str = "send"
    ) -> str:
        """Handle PEER_FLOOD: distinguish a real spam block from a temporary new-chat flood.

        Telegram returns PEER_FLOOD ("cannot message non-contacts") both when the account
        is genuinely spam-limited *and* when it is just sending to too many new people
        too fast (even though @SpamBot shows no restriction). Only the former needs the
        account to be parked; the latter is a short cooldown.
        """
        self._peer_flood_streak += 1
        self._stats["total_failed"] += 1
        detail = str(exc)
        account_label = self._userbot_account_label or (
            "OUTREACH_SESSION_STRING" if self._userbot_uses_env_session else "unknown"
        )

        # Keep the lead queued: it was not sent, another attempt will pick it up.
        item.status = "queued"
        item.error_detail = f"PeerFloodError ({stage}): {detail}"
        session.add(item)
        await session.commit()

        verdict = "unknown"
        if self._userbot_account_id:
            verdict = await self._spambot_verdict(self._userbot_account_id)
        persistent = verdict == "limited"

        cooldown_min = 0
        if self._userbot_account_id:
            parked_id = self._userbot_account_id
            if persistent:
                try:
                    await account_pool.mark_spam_limited(session, parked_id, hours=24)
                except Exception as park_exc:
                    logger.debug("Could not park limited account: %s", park_exc)
                self._last_recovery_probe[parked_id] = utcnow()
            else:
                # Temporary new-chat flood: cool the account down and keep it in rotation.
                base = max(10, int(settings.outreach_peer_flood_cooldown_min))
                cooldown_min = min(360, base * (2 ** max(0, self._peer_flood_streak - 1)))
                try:
                    acc = await session.get(TgAccount, parked_id)
                    if acc:
                        if acc.status == "spamblock":
                            acc.status = "active"
                        acc.flood_until = utcnow() + timedelta(minutes=cooldown_min)
                        acc.updated_at = utcnow()
                        session.add(acc)
                        await session.commit()
                except Exception as cool_exc:
                    logger.debug("Could not cool down account: %s", cool_exc)
            self._userbot_account_id = None
            self._userbot_client = None

        # Is another account ready to take over right now?
        next_available = False
        try:
            async with SessionLocal() as db:
                nxt = await account_pool.get_available_account(
                    db, max_daily_outreach=int(settings.outreach_account_daily_limit)
                )
                if nxt is None:
                    nxt = await self._probe_limited_account(db)
                next_available = nxt is not None
        except Exception as probe_exc:
            logger.debug("Account availability check failed: %s", probe_exc)

        if next_available:
            self._paused_until = None
            self._last_error = (
                f"PEER_FLOOD ({stage}): аккаунт {account_label} на паузе, переключаюсь на другой"
            )
            logger.warning(
                "Autonomous outreach PEER_FLOOD (%s) on %s — switching to another account",
                stage,
                account_label,
            )
        else:
            if self._userbot_uses_env_session:
                pause_min = cooldown_min or (120 if self._peer_flood_streak == 1 else 1440)
            else:
                pause_min = cooldown_min or 30
            self._paused_until = utcnow() + timedelta(minutes=pause_min)
            self._last_error = (
                f"PEER_FLOOD ({stage}): аккаунт {account_label} временно ограничен Telegram "
                f"по новым чатам, пауза {pause_min} мин"
                if not persistent
                else f"PEER_FLOOD ({stage}): аккаунт {account_label} заблокирован Telegram"
            )
            logger.warning(
                "Autonomous outreach PEER_FLOOD (%s) on %s — %s, paused %d min",
                stage,
                account_label,
                "persistent spam block" if persistent else "temporary new-chat flood",
                pause_min,
            )

        # Don't spam the admin with temporary floods — they are visible in /outreach_status.
        if persistent:
            await self._notify_peer_flood(account_label, stage, detail)
        return "peer_flood"

    async def requeue_peer_flood_leads(self) -> int:
        """Put leads back in the queue if they failed only because of a temporary PEER_FLOOD.

        Older worker versions marked them as ``error`` and never retried them.
        """
        try:
            async with SessionLocal() as session:
                res = await session.execute(
                    select(OutreachLead).where(
                        OutreachLead.status == "error",
                        OutreachLead.error_detail.ilike("%peerflood%"),
                    )
                )
                rows = list(res.scalars().all())
                for row in rows:
                    row.status = "queued"
                    row.error_detail = None
                    session.add(row)
                if rows:
                    await session.commit()
                    logger.info("Re-queued %d lead(s) previously lost to PEER_FLOOD", len(rows))
                return len(rows)
        except Exception as exc:
            logger.debug("PeerFlood re-queue notice: %s", exc)
            return 0

    def start_autonomous_loop(self) -> None:
        if self._autonomous_task and not self._autonomous_task.done():
            return

        async def _loop() -> None:
            await self.load_autonomous_state_from_db()
            await self.requeue_peer_flood_leads()
            while True:
                try:
                    outcome = await self.run_autonomous_step()
                    if outcome == "sent":
                        min_m = max(1, int(settings.outreach_min_delay_min))
                        max_m = max(min_m, int(settings.outreach_max_delay_min))
                        pause = random.randint(min_m * 60, max_m * 60)
                        logger.info("Autonomous outreach: sleeping %d min after send", pause // 60)
                        await asyncio.sleep(pause)
                    elif outcome == "skipped_no_tg":
                        # Pace ImportContacts lookups so Telegram doesn't trigger PeerFlood
                        await asyncio.sleep(random.randint(45, 90))
                    elif outcome == "skipped_bad_quality":
                        await asyncio.sleep(5)
                    elif outcome in ("disabled", "outside_hours", "paused"):
                        await asyncio.sleep(60)
                    elif outcome == "limit_reached":
                        await asyncio.sleep(600)
                    elif outcome in ("peer_flood", "no_client", "flood_wait"):
                        # New-chat anti-spam / no account left: back off, don't open
                        # a new chat every couple of minutes.
                        await asyncio.sleep(300)
                    else:
                        await asyncio.sleep(300)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    self._last_error = str(exc)
                    logger.warning("Autonomous outreach loop error: %s", exc)
                    await asyncio.sleep(120)

        self._autonomous_task = asyncio.create_task(_loop())

    def stop_autonomous_loop(self) -> None:
        if self._autonomous_task and not self._autonomous_task.done():
            self._autonomous_task.cancel()

    # ── Existing Manual Outreach & Follow-Up Logic ────────────────────────────

    async def personalize_message(self, lead: Lead, template: str) -> str:
        """Personalizes the outreach pitch using LLM or smart template substitution."""
        has_site_text = "есть сайт" if lead.has_website else "нет сайта"
        city_text = lead.city or "вашем городе"
        name_text = lead.name or "компания"

        system_prompt = (
            "Ты — опытный B2B аутрич-копирайтер веб-студии Murasaki. "
            "Твоя цель — переписать шаблон коротко (2-4 предложения), живо и дружелюбно, "
            "ненавязчиво упомянув детали о бизнесе собеседника. Без лишней воды, официоза и спам-фраз."
        )

        user_prompt = (
            f"Бизнес: {name_text}\n"
            f"Ниша: {lead.category or 'Услуги'}\n"
            f"Город: {city_text}\n"
            f"Статус сайта: {has_site_text}\n\n"
            f"Базовый шаблон сообщения:\n{template}\n\n"
            "Сгенерируй одно готовое уникальное персонализированное сообщение для отправки в Telegram:"
        )

        try:
            personalized = await ask_ai(user_prompt, system_prompt=system_prompt, task_type="fast", max_tokens=200, temperature=0.7)
            if personalized and len(personalized.strip()) > 20:
                return personalized.strip()
        except Exception as e:
            logger.info("LLM personalization fallback to template: %s", e)

        text = template
        text = text.replace("{company_name}", name_text)
        text = text.replace("{name}", name_text)
        text = text.replace("{city}", city_text)
        text = text.replace("{category}", lead.category or "бизнес")
        return text

    async def start_outreach_campaign(
        self,
        user_id: str,
        lead_ids: list[str],
        template: str,
        delay_min: int = 180,
        delay_max: int = 600,
    ) -> str:
        """Starts asynchronous campaign across selected leads."""
        campaign_id = f"camp_{utcnow().timestamp()}"
        task = asyncio.create_task(
            self._run_campaign(campaign_id, user_id, lead_ids, template, delay_min, delay_max)
        )
        self._active_tasks[campaign_id] = task
        self._stats["is_running"] = True
        return campaign_id

    async def _run_campaign(
        self,
        campaign_id: str,
        user_id: str,
        lead_ids: list[str],
        template: str,
        delay_min: int,
        delay_max: int,
    ) -> None:
        logger.info("Starting outreach campaign %s for %d leads", campaign_id, len(lead_ids))
        sent = 0
        failed = 0

        async with SessionLocal() as session:
            for lead_id in lead_ids:
                lead = await session.get(Lead, lead_id)
                if not lead:
                    continue

                self._stats["current_lead"] = lead.name

                target_peer = None
                if lead.social_links and isinstance(lead.social_links, dict):
                    tg = lead.social_links.get("telegram")
                    if tg:
                        target_peer = tg.replace("https://t.me/", "").replace("@", "").strip()

                if not target_peer and lead.phone:
                    target_peer = lead.phone

                if not target_peer:
                    logger.debug("Lead %s has no Telegram or phone, skipping", lead.name)
                    failed += 1
                    continue

                dup_stmt = select(Dialog.id).where(Dialog.lead_id == lead.id)
                if (await session.execute(dup_stmt)).first():
                    logger.info("Skipping duplicate outreach for lead %s (dialog exists)", lead.name)
                    continue

                try:
                    await check_and_spend(
                        session=session,
                        user_id=user_id,
                        amount=settings.credits_per_outreach,
                        module_name="outreach",
                        description=f"AI-касание лида {lead.name} ({target_peer})",
                    )
                except Exception as spend_err:
                    logger.warning("Outreach aborted due to credits error: %s", spend_err)
                    break

                account = await account_pool.get_available_account(
                    session, user_id, max_daily_outreach=int(settings.outreach_account_daily_limit)
                )
                if not account:
                    logger.warning("No available TG accounts in pool for outreach")
                    failed += 1
                    break

                message_text = await self.personalize_message(lead, template)

                try:
                    client = await account_pool.get_client_for_account(account)
                    await client.connect()

                    if await client.is_user_authorized():
                        peer_entity = await client.get_entity(target_peer)

                        preview_path = None
                        if lead.demo_id:
                            candidate = (
                                Path(__file__).resolve().parent.parent
                                / "static" / "uploads" / "demos" / f"{lead.demo_id}.png"
                            )
                            if candidate.exists():
                                preview_path = candidate

                        if preview_path is not None:
                            sent_msg = await client.send_file(
                                peer_entity,
                                str(preview_path),
                                caption=message_text[:1024],
                                parse_mode="md",
                            )
                        else:
                            sent_msg = await client.send_message(
                                peer_entity, message_text, parse_mode="md", link_preview=False
                            )

                        peer_id = str(getattr(peer_entity, "id", target_peer))
                        peer_username = getattr(peer_entity, "username", None)
                        peer_name = getattr(peer_entity, "title", None) or getattr(peer_entity, "first_name", None) or lead.name

                        dialog = Dialog(
                            account_id=account.id,
                            peer_id=peer_id,
                            peer_username=peer_username,
                            peer_name=peer_name,
                            lead_id=lead.id,
                            status="new",
                            unread_count=0,
                            last_message_at=utcnow(),
                            followup_step=0,
                            next_followup_at=utcnow() + timedelta(hours=48),
                        )
                        session.add(dialog)
                        await session.flush()

                        msg = Message(
                            dialog_id=dialog.id,
                            account_id=account.id,
                            direction="out",
                            text=message_text,
                            tg_message_id=getattr(sent_msg, "id", None),
                            is_ai_generated=True,
                        )
                        session.add(msg)

                        lead.status = "sent"
                        await account_pool.record_outreach_action(session, account.id)
                        await session.commit()

                        sent += 1
                        self._stats["total_sent"] += 1
                        logger.info("Sent outreach to %s via account %s", lead.name, account.phone)
                    else:
                        account.status = "banned"
                        await session.commit()
                except Exception as err:
                    logger.warning("Outreach send failed for %s: %s", lead.name, err)
                    await account_pool.rotate_on_error(session, account.id, err)
                    failed += 1
                    self._stats["total_failed"] += 1

                delay = random.uniform(float(delay_min), float(delay_max))
                logger.info("Waiting %.1f seconds before next outreach...", delay)
                await asyncio.sleep(delay)

        self._stats["is_running"] = False
        self._stats["current_lead"] = None
        self._active_tasks.pop(campaign_id, None)
        logger.info("Campaign %s finished. Sent: %d, Failed: %d", campaign_id, sent, failed)

    async def process_followups(self) -> int:
        """Send scheduled follow-ups for silent dialogs (48h and +72h)."""
        now = utcnow()
        sent_count = 0
        async with SessionLocal() as session:
            stmt = select(Dialog).where(
                Dialog.next_followup_at.isnot(None),
                Dialog.next_followup_at <= now,
                Dialog.followup_step < 2,
                Dialog.status.in_(("new", "ai_handling")),
            ).limit(15)
            dialogs = list((await session.execute(stmt)).scalars().all())
            for dialog in dialogs:
                lead = await session.get(Lead, dialog.lead_id) if dialog.lead_id else None
                biz_name = (lead.name if lead else None) or dialog.peer_name or "вашей компании"
                step = dialog.followup_step or 0

                if step == 0:
                    text = (
                        f"Добрый день! Подскажите, удалось ли посмотреть набросок сайта для «{biz_name}»? "
                        "Если нужно поправить цвета, текст или добавить прайс — сделаем бесплатно."
                    )
                    next_at = now + timedelta(hours=72)
                else:
                    text = (
                        f"Закрываю задачу по макету для «{biz_name}», чтобы не потерялась. "
                        "Ссылка на демо останется рабочей — напишите, если вернётесь к вопросу сайта 👍"
                    )
                    next_at = None

                account = await session.get(TgAccount, dialog.account_id)
                if not account:
                    dialog.next_followup_at = None
                    session.add(dialog)
                    await session.commit()
                    continue
                flood_until = account.flood_until
                if flood_until is not None and flood_until.tzinfo is None:
                    flood_until = flood_until.replace(tzinfo=timezone.utc)
                if account.status in ("floodwait", "spamblock") or (
                    flood_until is not None and flood_until > now
                ):
                    # Account is temporarily limited by Telegram: postpone, don't cancel.
                    dialog.next_followup_at = now + timedelta(hours=12)
                    session.add(dialog)
                    await session.commit()
                    continue
                if account.status != "active":
                    dialog.next_followup_at = None
                    session.add(dialog)
                    await session.commit()
                    continue

                try:
                    client = await account_pool.get_client_for_account(account)
                    await client.connect()
                    if await client.is_user_authorized():
                        target = dialog.peer_username or int(dialog.peer_id) if str(dialog.peer_id).lstrip("-").isdigit() else dialog.peer_id
                        sent_msg = await client.send_message(target, text, link_preview=False)
                        session.add(
                            Message(
                                dialog_id=dialog.id,
                                account_id=account.id,
                                direction="out",
                                text=text,
                                tg_message_id=getattr(sent_msg, "id", None),
                                is_ai_generated=True,
                            )
                        )
                        dialog.followup_step = step + 1
                        dialog.next_followup_at = next_at
                        dialog.last_message_at = now
                        session.add(dialog)
                        await account_pool.record_action(session, account.id)
                        await session.commit()
                        sent_count += 1
                        await asyncio.sleep(random.uniform(15.0, 40.0))
                except Exception as exc:
                    logger.warning("Follow-up failed for dialog %s: %s", dialog.id, exc)
                    from telethon.errors import PeerFloodError

                    if isinstance(exc, PeerFloodError):
                        try:
                            await account_pool.mark_spam_limited(session, account.id, hours=24)
                        except Exception:
                            pass
                    dialog.next_followup_at = now + timedelta(hours=12)
                    session.add(dialog)
                    await session.commit()
        return sent_count

    def start_followup_loop(self) -> None:
        if getattr(self, "_followup_task", None) and not self._followup_task.done():
            return

        async def _loop() -> None:
            while True:
                try:
                    await asyncio.sleep(1800)
                    await self.process_followups()
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("Follow-up loop notice: %s", exc)

        self._followup_task = asyncio.create_task(_loop())

    def stop_followup_loop(self) -> None:
        task = getattr(self, "_followup_task", None)
        if task and not task.done():
            task.cancel()


outreach_worker = OutreachWorker()
