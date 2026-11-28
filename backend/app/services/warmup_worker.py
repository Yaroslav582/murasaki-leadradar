from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Dialog, Message, TgAccount, User, utcnow
from app.services.account_pool import account_pool, mask_phone
from app.services.billing import check_and_spend

logger = logging.getLogger(__name__)

# Neutral message templates for cross-dialogues inside the farm
FARM_CHAT_TEMPLATES = [
    ("Привет, как успехи сегодня?", "Привет! Всё отлично, работаю по задачам."),
    ("Слушай, видел последние новости по Telegram?", "Да, обновления выкатили интересные."),
    ("Добрый день! На связи если что.", "Добрый! Принято, спасибо."),
    ("Как думаешь, стоит обновлять софт?", "Думаю да, стабильнее работать будет."),
    ("Привет, скинь пожалуйста ссылку когда освободишься.", "Окей, чуть позже отправлю."),
    ("Отличного продуктивного дня!", "Взаимно, спасибо! 👍"),
]


class WarmupWorker:
    """Async background worker for automated account warm-up according to trust presets."""

    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_session_time: dict[str, datetime] = {}
        self._last_cross_chat_day: dict[str, str] = {}
        self._last_billing_day: dict[str, str] = {}

    def start(self) -> None:
        """Starts background warmup worker loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("WarmupWorker started")

    async def initialize_from_db(self) -> int:
        """Loads and activates all accounts configured for auto-warmup from Supabase."""
        async with SessionLocal() as session:
            stmt = select(TgAccount).where(
                TgAccount.auto_warmup == True,
                TgAccount.status.in_(["active", "warming"]),
            )
            res = await session.execute(stmt)
            accounts = res.scalars().all()
            initialized_count = 0
            for account in accounts:
                try:
                    client = await account_pool.get_client_for_account(account)
                    if client:
                        initialized_count += 1
                        logger.info(
                            "Auto-warmup worker active for account %s (%s, preset=%s)",
                            account.phone,
                            account.id,
                            account.warmup_preset,
                        )
                except Exception as e:
                    logger.warning("Could not pre-initialize warmup client for %s: %s", account.phone, e)
            logger.info("WarmupWorker initialized: %d accounts active with auto_warmup=True from Supabase", len(accounts))
            return len(accounts)

    def stop(self) -> None:
        """Stops background warmup worker loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("WarmupWorker stopped")

    async def _main_loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in warmup worker tick: %s", e)
            await asyncio.sleep(60)  # Check every 60 seconds

    async def tick(self) -> None:
        """Checks accounts needing warmup sessions."""
        async with SessionLocal() as session:
            stmt = select(TgAccount).where(
                TgAccount.auto_warmup == True,
                TgAccount.status.in_(["active", "warming"]),
            )
            res = await session.execute(stmt)
            accounts = res.scalars().all()

            if not accounts:
                return

            now = utcnow()
            today_str = now.strftime("%Y-%m-%d")

            for account in accounts:
                due = account.flood_until
                if due is not None and due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
                if due and due > now:
                    continue

                if account_pool.is_account_busy(account.id):
                    logger.debug(
                        "Skipping warmup for busy account %s (%s)",
                        mask_phone(account.phone),
                        account.id,
                    )
                    continue

                # Check billing for daily warmup: 2 credits per account per day
                already_billed_today = False
                if account.daily_actions_reset_at:
                    try:
                        already_billed_today = (account.daily_actions_reset_at.strftime("%Y-%m-%d") == today_str)
                    except Exception:
                        pass
                if not already_billed_today and self._last_billing_day.get(account.id) == today_str:
                    already_billed_today = True

                if account.user_id and not already_billed_today:
                    try:
                        await check_and_spend(
                            session=session,
                            user_id=account.user_id,
                            amount=settings.credits_per_warmup_day,
                            module_name="warmup",
                            description=f"Автопрогрев аккаунта {mask_phone(account.phone)} (1 день)",
                        )
                        self._last_billing_day[account.id] = today_str
                        account.daily_actions_reset_at = now
                        await session.commit()
                    except Exception as bill_err:
                        err_msg = str(bill_err).lower()
                        # Only pause auto_warmup if balance is explicitly insufficient
                        if "недостаточно кредитов" in err_msg or "insufficient" in err_msg:
                            logger.warning(
                                "Auto-warmup paused for %s due to insufficient credits: %s",
                                mask_phone(account.phone),
                                bill_err,
                            )
                            account.auto_warmup = False
                            await session.commit()
                            continue
                        else:
                            # Transient database, network or auth issue: do NOT reset user's auto_warmup flag!
                            logger.warning(
                                "Warmup billing transient note for %s: %s",
                                mask_phone(account.phone),
                                bill_err,
                            )

                # Determine session interval by preset
                preset = account.warmup_preset or "optimal"
                # light: 1-2 sessions/day (~12h), optimal: 3-4 sessions/day (~6h), active: 5-6 sessions/day (~4h)
                interval_hours = 12 if preset == "light" else (6 if preset == "optimal" else 4)

                last_time = self._last_session_time.get(account.id)
                if last_time and (now - last_time).total_seconds() < interval_hours * 3600:
                    continue

                logger.info(
                    "Starting warmup session for account %s (%s, preset=%s)",
                    mask_phone(account.phone),
                    account.id,
                    preset,
                )
                try:
                    await self._run_warmup_session(session, account)
                    self._last_session_time[account.id] = now
                except Exception as acc_err:
                    logger.warning(
                        "Warmup tick error for %s (%s): %s",
                        mask_phone(account.phone),
                        account.id,
                        acc_err,
                    )

            # If farm has >= 2 idle accounts, perform cross-dialogue once a day
            idle_accounts = [a for a in accounts if not account_pool.is_account_busy(a.id)]
            if len(idle_accounts) >= 2:
                farm_key = "farm_cross_dialogue"
                if self._last_cross_chat_day.get(farm_key) != today_str:
                    try:
                        await self._perform_farm_cross_chat(session, idle_accounts)
                        self._last_cross_chat_day[farm_key] = today_str
                    except Exception as fce:
                        logger.warning("Farm cross chat failed: %s", fce)

    async def _run_warmup_session(self, session: AsyncSession, account: TgAccount) -> None:
        """Executes a simulated human reading/reaction session in trusted channels."""
        channels = settings.warmup_channels_list
        if not channels:
            channels = ["@telegram", "@durov", "@thebell_io", "@rbc_news", "@ria_novosti"]

        if account_pool.is_account_busy(account.id):
            logger.debug("Skipping warmup session because account %s is busy", account.id)
            return

        try:
            async with account_pool.acquire_account(account.id, owner="warmup"):
                client = await account_pool.get_client_for_account(account)
                await client.connect()

                if not await client.is_user_authorized():
                    account.status = "banned"
                    await session.commit()
                    return

                from telethon.tl.functions.messages import GetMessagesViewsRequest, SendReactionRequest
                from telethon.tl.types import ReactionEmoji

                # 1. Read 3-7 posts from random trusted channel
                target_channel = random.choice(channels)
                post_count = random.randint(3, 7)

                entity = await client.get_entity(target_channel)
                messages = await client.get_messages(entity, limit=post_count)

                if messages:
                    msg_ids = [m.id for m in messages if m and m.id]
                    if msg_ids:
                        try:
                            await client(GetMessagesViewsRequest(peer=entity, id=msg_ids, increment=True))
                        except Exception as ve:
                            logger.debug("View request info: %s", ve)

                    # Send 1-2 random reactions with realistic pauses
                    reaction_emojis = ["👍", "🔥", "❤️", "👏"]
                    for msg in messages[:2]:
                        try:
                            chosen_emoji = random.choice(reaction_emojis)
                            await client(SendReactionRequest(
                                peer=entity,
                                msg_id=msg.id,
                                reaction=[ReactionEmoji(emoticon=chosen_emoji)]
                            ))
                        except Exception:
                            pass
                        # Sleep 15-45 sec realistic delay
                        delay = random.uniform(2.0, 5.0)  # slightly sped up for server responsiveness
                        await asyncio.sleep(delay)

                # 2. Join 1 channel if below max channels
                if random.random() < 0.3:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    try:
                        await client(JoinChannelRequest(entity))
                        logger.info(
                            "Account %s subscribed to channel %s",
                            mask_phone(account.phone),
                            target_channel,
                        )
                    except Exception as je:
                        logger.debug("Join channel skipped: %s", je)

            # 3. Increase warmup_level by 5-10% up to 100%
            increase = random.randint(5, 10)
            account.warmup_level = min(100, account.warmup_level + increase)
            if account.warmup_level >= 100:
                account.status = "active"

            account.daily_actions_count += 1
            account.updated_at = utcnow()
            await session.commit()
            logger.info(
                "Warmup session completed for %s. New level: %d%%",
                mask_phone(account.phone),
                account.warmup_level,
            )

        except Exception as err:
            exc_name = type(err).__name__
            logger.warning("Warmup session error (%s) for %s: %s", exc_name, mask_phone(account.phone), err)
            if any(
                marker in exc_name
                for marker in ("FloodWait", "PeerFlood", "Spam", "UserBanned", "UserDeactivated", "AuthKey")
            ):
                await account_pool.rotate_on_error(session, account.id, err)

    async def _perform_farm_cross_chat(self, session: AsyncSession, accounts: list[TgAccount]) -> None:
        """Exchanges neutral friendly messages between farm accounts to build peer trust."""
        if len(accounts) < 2:
            return

        acc1, acc2 = random.sample(accounts, 2)
        phrase1, phrase2 = random.choice(FARM_CHAT_TEMPLATES)

        # Generate unique human dialogue via AI router if available
        try:
            from app.services.ai_router import ask_ai
            ai_dialog = await ask_ai(
                "Придумай очень короткий живой нейтральный диалог из двух реплик (вопрос и ответ) между двумя знакомыми в Telegram. "
                "Каждая реплика 1 короткое предложение до 8 слов. Формат строго: Реплика 1 | Реплика 2",
                task_type="fast",
                max_tokens=60,
            )
            if "|" in ai_dialog:
                p1, p2 = [p.strip().strip('"').strip("'") for p in ai_dialog.split("|", 1)]
                if len(p1) > 3 and len(p2) > 3:
                    phrase1, phrase2 = p1, p2
        except Exception as ai_err:
            logger.debug("AI cross-chat generation fallback to template: %s", ai_err)

        try:
            first, second = sorted([acc1, acc2], key=lambda a: a.id)
            async with account_pool.acquire_account(first.id, owner="warmup_cross"), account_pool.acquire_account(second.id, owner="warmup_cross"):
                client1 = await account_pool.get_client_for_account(acc1)
                await client1.connect()
                if not await client1.is_user_authorized():
                    return

                client2 = await account_pool.get_client_for_account(acc2)
                await client2.connect()
                if not await client2.is_user_authorized():
                    return

                # acc1 sends phrase1 to acc2
                peer2 = await client1.get_entity(acc2.phone)
                await client1.send_message(peer2, phrase1)
                logger.info("Farm cross-dialogue: %s -> %s", mask_phone(acc1.phone), mask_phone(acc2.phone))

                # Delay 5-15 sec then reply
                await asyncio.sleep(random.uniform(5.0, 15.0))

                peer1 = await client2.get_entity(acc1.phone)
                await client2.send_message(peer1, phrase2)
                logger.info("Farm cross-dialogue: %s -> %s", mask_phone(acc2.phone), mask_phone(acc1.phone))

        except Exception as e:
            logger.debug("Farm cross-chat skipped: %s", e)


warmup_worker = WarmupWorker()
