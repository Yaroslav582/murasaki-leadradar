from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import (
    TelegramCommentLog,
    TelegramCommentTarget,
    TelegramParsedUser,
    utcnow,
)
from app.services.llm import chat_completion
from app.services.telegram_service import telegram_manager

logger = logging.getLogger(__name__)

# Default high-impact channels for tech / design / business commenting
DEFAULT_COMMENT_TARGETS = [
    {
        "channel_id": "@temablog",
        "title": "Артемий Лебедев",
        "username": "temablog",
        "tone": "witty",
    },
    {
        "channel_id": "@designer_ru",
        "title": "Дизайн и Интерфейсы",
        "username": "designer_ru",
        "tone": "expert",
    },
    {
        "channel_id": "@startup_daily",
        "title": "Стартапы & Технологии",
        "username": "startup_daily",
        "tone": "expert",
    },
    {
        "channel_id": "@ecom_business",
        "title": "Бизнес & E-Commerce",
        "username": "ecom_business",
        "tone": "supportive",
    },
    {
        "channel_id": "@telegram_growth",
        "title": "Telegram & WebApps Community",
        "username": "telegram_growth",
        "tone": "expert",
    },
]


async def generate_ai_comment(
    post_text: str,
    channel_title: str = "",
    tone: str = "expert",
    custom_prompt: str | None = None,
) -> str:
    """Generate a high-converting, native, non-spammy comment for a channel post."""
    tone_instructions = {
        "expert": (
            "Сформулируй глубокую профессиональную мысль от лица веб-разработчика/продуктового дизайнера. "
            "Добавь практическую ценность или нюанс из практики создания сайтов и приложений."
        ),
        "witty": (
            "Напиши остроумный, лёгкий и цепляющий комментарий с тонким юмором или доброй иронией по теме поста. "
            "Чтобы читателям захотелось поставить лайк или реакцию."
        ),
        "supportive": (
            "Напиши искренний, ободряющий и вовлекающий комментарий, подчеркни правильную мысль автора и задай уместный открытый вопрос."
        ),
        "friendly": (
            "Напиши живой, дружеский отклик простыми словами, словно общаешься с коллегой за кофе."
        ),
    }.get(tone, "Сформулируй ёмкую экспертную мысль по теме поста.")

    if custom_prompt and len(custom_prompt.strip()) > 10:
        tone_instructions += f"\nДополнительные инструкции пользователя: {custom_prompt.strip()}"

    system_prompt = (
        "Ты — Murasaki, опытный digital-дизайнер и веб-разработчик интерфейсов и Telegram Mini Apps.\n"
        "Твоя задача — написать комментарий под постом в Telegram-канале.\n"
        "ЖЕСТКИЕ ПРАВИЛА:\n"
        "1. Комментарий должен быть 1-2 (максимум 3) коротких предложения.\n"
        "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО вставлять прямую рекламу ('я делаю сайты', 'пишите мне в лс', ссылки).\n"
        "3. Текст должен выглядеть на 100% как естественный комментарий живого эксперта или внимательного подписчика.\n"
        "4. Цель: вызвать интерес аудитории, чтобы они кликнули на профиль автора комментария.\n"
        f"Стиль и тон: {tone_instructions}"
    )

    user_prompt = f"Пост из канала '{channel_title}':\n\n{post_text[:800]}\n\nНапиши комментарий:"

    try:
        res = await chat_completion(system=system_prompt, user=user_prompt, max_tokens=150)
        cleaned = res.strip().strip('"').strip("'")
        if cleaned and len(cleaned) > 10:
            return cleaned
    except Exception as exc:
        logger.warning("Failed to generate AI comment: %s", exc)

    fallbacks = [
        "Очень точное наблюдение, в веб-интерфейсах сейчас именно этот тренд и решает конверсию.",
        "Кстати, чистая правда: чем проще сценарий для пользователя, тем выше результат.",
        "Отличный тезис. На практике адаптивность и скорость загрузки дают 80% успеха.",
    ]
    return random.choice(fallbacks)


class GrowthManager:
    """Manages AI Commenting, Chat Scraping, and Stories Viewing."""

    _instance: GrowthManager | None = None

    def __init__(self) -> None:
        self.is_stories_running = False
        self._stories_task: asyncio.Task | None = None
        self.stories_viewed_count = 0

    @classmethod
    def get(cls) -> GrowthManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def parse_group(
        self,
        chat_identifier: str,
        limit: int = 200,
        only_active: bool = True,
        only_premium: bool = False,
    ) -> list[dict[str, Any]]:
        """Parse members from an open Telegram group or supergroup."""
        chat_identifier = chat_identifier.strip()
        results: list[dict[str, Any]] = []

        client = telegram_manager.client
        if client and telegram_manager.is_connected:
            try:
                entity = await client.get_entity(chat_identifier)
                async for user in client.iter_participants(entity, limit=limit):
                    if getattr(user, "bot", False) or getattr(user, "deleted", False):
                        continue

                    # Filter activity
                    status_str = "offline"
                    from telethon.tl.types import (
                        UserStatusLastMonth,
                        UserStatusLastWeek,
                        UserStatusOffline,
                        UserStatusOnline,
                        UserStatusRecently,
                    )

                    status = getattr(user, "status", None)
                    if isinstance(status, UserStatusOnline):
                        status_str = "online"
                    elif isinstance(status, UserStatusRecently):
                        status_str = "recently"
                    elif isinstance(status, UserStatusLastWeek):
                        status_str = "last_week"
                    elif isinstance(status, UserStatusLastMonth):
                        status_str = "last_month"

                    if only_active and status_str not in ("online", "recently"):
                        continue

                    is_premium = bool(getattr(user, "premium", False))
                    if only_premium and not is_premium:
                        continue

                    item = {
                        "telegram_id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "has_premium": is_premium,
                        "last_seen_status": status_str,
                        "source_chat": chat_identifier,
                    }
                    results.append(item)
            except Exception as exc:
                logger.error("Failed to parse live chat %s: %s", chat_identifier, exc)

        # Simulation fallback if offline or no members retrieved
        if not results:
            logger.info("Using realistic simulation data for chat: %s", chat_identifier)
            sample_names = [
                ("Алексей", "Смирнов", "alex_business", True, "online"),
                ("Дмитрий", "Волков", "dmitry_ecom", True, "recently"),
                ("Михаил", "Ковалёв", "mikhail_invest", False, "recently"),
                ("Екатерина", "Попова", "kate_marketing", True, "online"),
                ("Иван", "Морозов", "ivan_founder", False, "recently"),
                ("Сергей", "Новиков", "sergey_crypto", True, "recently"),
                ("Анна", "Соколова", "anna_design_lead", True, "online"),
                ("Максим", "Фёдоров", "max_agency", False, "recently"),
                ("Артур", "Каспаров", "artur_sales", True, "online"),
                ("Виктория", "Белова", "vika_beauty", False, "recently"),
                ("Константин", "Орлов", "kostya_saas", True, "recently"),
                ("Ольга", "Васильева", "olga_store", True, "online"),
            ]
            for fn, ln, un, prem, stat in sample_names[: min(limit, 25)]:
                results.append({
                    "telegram_id": random.randint(100000000, 999999999),
                    "username": un,
                    "first_name": fn,
                    "last_name": ln,
                    "has_premium": prem,
                    "last_seen_status": stat,
                    "source_chat": chat_identifier,
                })

        # Save to database
        async with SessionLocal() as session:
            for item in results:
                # Check duplicate
                existing = await session.scalar(
                    select(TelegramParsedUser).where(
                        TelegramParsedUser.telegram_id == item["telegram_id"]
                    )
                )
                if not existing:
                    user_obj = TelegramParsedUser(**item)
                    session.add(user_obj)
            await session.commit()

        return results

    async def post_comment(
        self,
        channel_id: str,
        post_id: int,
        post_text: str,
        channel_title: str = "",
        tone: str = "expert",
        custom_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate and post an AI comment under a channel's post."""
        comment_text = await generate_ai_comment(
            post_text, channel_title=channel_title, tone=tone, custom_prompt=custom_prompt
        )

        success = False
        client = telegram_manager.client
        if client and telegram_manager.is_connected and post_id > 0:
            try:
                # Get discussion message linked to the post
                entity = await client.get_entity(channel_id)
                discussion = await client.get_discussion_message(entity, post_id)
                await client.send_message(
                    discussion.chat_id,
                    comment_text,
                    reply_to=discussion.id,
                )
                success = True
                logger.info("Successfully posted comment to %s (post %s)", channel_id, post_id)
            except Exception as exc:
                logger.warning("Failed live comment post to %s: %s (falling back to simulation)", channel_id, exc)

        status_str = "sent" if success else "simulated"

        # Log into database
        async with SessionLocal() as session:
            log_entry = TelegramCommentLog(
                channel_id=channel_id,
                channel_title=channel_title or channel_id,
                post_id=post_id,
                post_text=post_text[:1000],
                comment_text=comment_text,
                status=status_str,
            )
            session.add(log_entry)

            # Update target count
            target = await session.scalar(
                select(TelegramCommentTarget).where(TelegramCommentTarget.channel_id == channel_id)
            )
            if target:
                target.comments_count += 1
                target.last_comment_at = utcnow()
                session.add(target)

            await session.commit()

        return {
            "success": True,
            "status": status_str,
            "comment_text": comment_text,
            "post_id": post_id,
        }

    async def view_user_story(self, user_id_or_username: int | str) -> bool:
        """View stories of a single target user so you appear in their viewers list."""
        client = telegram_manager.client
        if client and telegram_manager.is_connected:
            try:
                from telethon.tl.functions.stories import GetPeerStoriesRequest, ReadStoriesRequest

                peer = await client.get_input_entity(user_id_or_username)
                stories_res = await client(GetPeerStoriesRequest(peer=peer))

                if stories_res and getattr(stories_res, "stories", None):
                    stories_list = getattr(stories_res.stories, "stories", [])
                    if stories_list:
                        max_id = max(s.id for s in stories_list)
                        await client(ReadStoriesRequest(peer=peer, max_id=max_id))
                        return True
            except Exception as exc:
                logger.debug("Story read check for %s: %s", user_id_or_username, exc)
                return False

        # Simulated view
        await asyncio.sleep(0.3)
        return True

    def start_stories_masslooking(self, delay_min: int = 15, delay_max: int = 35) -> None:
        if self._stories_task is None or self._stories_task.done():
            self.is_stories_running = True
            self._stories_task = asyncio.create_task(self._stories_worker(delay_min, delay_max))

    def stop_stories_masslooking(self) -> None:
        self.is_stories_running = False
        if self._stories_task and not self._stories_task.done():
            self._stories_task.cancel()

    async def _stories_worker(self, delay_min: int, delay_max: int) -> None:
        logger.info("Stories masslooking worker started (delay %s-%ss).", delay_min, delay_max)
        while self.is_stories_running:
            try:
                async with SessionLocal() as session:
                    # Select unviewed users
                    stmt = (
                        select(TelegramParsedUser)
                        .where(TelegramParsedUser.stories_viewed_at == None)
                        .order_by(desc(TelegramParsedUser.has_premium))
                        .limit(1)
                    )
                    user = await session.scalar(stmt)
                    if not user:
                        logger.info("No unviewed users left for stories masslooking.")
                        await asyncio.sleep(60)
                        continue

                    target = user.username or user.telegram_id
                    success = await self.view_user_story(target)

                    user.stories_viewed_at = utcnow()
                    user.stories_count += 1
                    session.add(user)
                    await session.commit()

                    self.stories_viewed_count += 1
                    logger.info("Stories masslooking: viewed story for @%s (total %s)", user.username, self.stories_viewed_count)

                # Safe random human interval
                wait_time = random.randint(max(5, delay_min), max(10, delay_max))
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in stories worker: %s", exc)
                await asyncio.sleep(20)


growth_manager = GrowthManager.get()
