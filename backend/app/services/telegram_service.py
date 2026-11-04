from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DATA_DIR, settings
from app.db import SessionLocal
from app.models import TelegramBroadcast, TelegramChatTarget, TelegramOrder, utcnow
from app.services.llm import chat_completion

logger = logging.getLogger(__name__)

# Expanded list of high-activity Russian freelance channels & chats
DEFAULT_TARGETS = [
    {
        "chat_id": "@Murasaki_website",
        "title": "Murasaki | Собственный канал",
        "username": "Murasaki_website",
        "kind": "promo",
        "cooldown_minutes": 360,
        "auto_post_enabled": True,
        "custom_text": "⚡️ Разработка продающих сайтов, лендингов и Telegram Mini Apps под ключ.\n\nПортфолио проектов: {portfolio}\nСвязь и бесплатный аудит: @loves_kyni",
    },
    {
        "chat_id": "@freelancetavern",
        "title": "Фриланс Таверна (Заказы)",
        "username": "freelancetavern",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@finder_vc",
        "title": "Finder.vc — Удаленная работа & Проекты",
        "username": "finder_vc",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@distantsiya",
        "title": "Дистанция — фриланс и удаленка",
        "username": "distantsiya",
        "kind": "both",
        "cooldown_minutes": 120,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@freelance_chat_ru",
        "title": "Биржа фриланса и заказов",
        "username": "freelance_chat_ru",
        "kind": "promo",
        "cooldown_minutes": 90,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@forfreelance",
        "title": "Все о фрилансе | Заказы Web",
        "username": "forfreelance",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@it_recruiting_ru",
        "title": "IT Вакансии и Проекты РФ",
        "username": "it_recruiting_ru",
        "kind": "orders",
        "cooldown_minutes": 240,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@tabor_it",
        "title": "Табор IT — заказы и подработка",
        "username": "tabor_it",
        "kind": "both",
        "cooldown_minutes": 120,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@zakazy_freelance",
        "title": "Биржа заказов Freelance",
        "username": "zakazy_freelance",
        "kind": "both",
        "cooldown_minutes": 90,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@job_react",
        "title": "React & Web Frontend Gigs",
        "username": "job_react",
        "kind": "orders",
        "cooldown_minutes": 240,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@web_freelance_jobs",
        "title": "Веб-разработка | Сайты и лендинги",
        "username": "web_freelance_jobs",
        "kind": "both",
        "cooldown_minutes": 120,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@designer_jobs",
        "title": "Дизайн сайтов и интерфейсы",
        "username": "designer_jobs",
        "kind": "both",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@normrabota",
        "title": "Норм работа — Digital & IT",
        "username": "normrabota",
        "kind": "orders",
        "cooldown_minutes": 360,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@forwriters",
        "title": "Work for Web & Digital",
        "username": "forwriters",
        "kind": "both",
        "cooldown_minutes": 240,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@freelancefeed",
        "title": "Freelance Feed | Заказы сайтов",
        "username": "freelancefeed",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@freelance_zakazy",
        "title": "Биржа разовых заказов и проектов",
        "username": "freelance_zakazy",
        "kind": "orders",
        "cooldown_minutes": 150,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@digital_rabota",
        "title": "Digital Jobs: Сайты, UX/UI, Боты",
        "username": "digital_rabota",
        "kind": "both",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@it_freelance_chat",
        "title": "IT Freelance Чат & Биржа",
        "username": "it_freelance_chat",
        "kind": "both",
        "cooldown_minutes": 120,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@work_in_it",
        "title": "Работа и заказы в IT / Web",
        "username": "work_in_it",
        "kind": "orders",
        "cooldown_minutes": 240,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@part_time_it",
        "title": "Подработка и разовые IT-проекты",
        "username": "part_time_it",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@freelancechoice",
        "title": "Фриланс Выбор — Заказы на сайты",
        "username": "freelancechoice",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@tg_bots_orders",
        "title": "Заказы Telegram ботов и WebApps",
        "username": "tg_bots_orders",
        "kind": "orders",
        "cooldown_minutes": 150,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@webdev_jobs_ru",
        "title": "WebDev Jobs — Верстка и лендинги",
        "username": "webdev_jobs_ru",
        "kind": "orders",
        "cooldown_minutes": 210,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@remotework_ru",
        "title": "Удаленка & Проекты под ключ",
        "username": "remotework_ru",
        "kind": "both",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@frilans_zakazi",
        "title": "Фриланс заказы без посредников",
        "username": "frilans_zakazi",
        "kind": "both",
        "cooldown_minutes": 120,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@zakazy_na_freelance",
        "title": "Заказы на фрилансе: Web & Дизайн",
        "username": "zakazy_na_freelance",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@freelance_hub_ru",
        "title": "Freelance Hub | Заказы и резюме",
        "username": "freelance_hub_ru",
        "kind": "both",
        "cooldown_minutes": 150,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@landing_jobs",
        "title": "Заказы на разработку лендингов",
        "username": "landing_jobs",
        "kind": "orders",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
]

# High-converting, polite response templates
FALLBACK_RESPONSES = [
    "Здравствуйте! Увидел ваш заказ на {topic}. Могу взять в работу — делаю адаптивные сайты под ключ с чистым кодом и быстрым запуском за 3-5 дней. Если предложение актуально, напишите в ответ — скину пару примеров похожих работ.",
    "Добрый день! Могу помочь с {topic}. Занимаюсь разработкой современных лендингов и сайтов, соблюдаю дедлайны. Если задача еще открыта — дайте знать, покажу релевантные кейсы из портфолио.",
    "Приветствую! Заинтересовал ваш проект по {topic}. Стек подходящий, могу приступить в ближайшее время. Если интересно обсудить детали или взглянуть на примеры выполненных сайтов — пишите в ЛС.",
]

FALLBACK_PROMOS = [
    "Всем привет! Занимаюсь разработкой современных лендингов, продающих сайтов и Telegram Mini Apps под ключ. Чистая верстка, высокая скорость загрузки и адаптивность под мобилки. Беру 1-2 проекта на этой неделе.\n\nПортфолио: {portfolio}\nКому актуально освежить сайт или запустить новый — пишите в ЛС @loves_kyni, с радостью обсудим задачу!",
    "Здравствуйте! Помогаю предпринимателям и проектам упаковывать бизнес в конверсионные сайты и лендинги. Сроки — от 3 дней, прозрачный процесс и внимание к деталям.\n\nМои работы можно посмотреть тут: {portfolio}\nЕсли нужен сайт или хотите сделать аудит текущего — буду рад пообщаться в ЛС @loves_kyni.",
    "Привет! Свободен для 1-2 интересных проектов по веб-разработке и дизайну лендингов. Делаю аккуратно, быстро и без лишней воды.\n\nКейсы и примеры: {portfolio}\nПишите в личку @loves_kyni, обсудим вашу задачу и подберем оптимальный формат.",
]


def is_within_working_hours() -> tuple[bool, str]:
    """Check if current Moscow time (UTC+3) is within active working hours."""
    if not getattr(settings, "telegram_working_hours_enabled", True):
        return True, "Круглосуточный режим"

    now_moscow = datetime.now(timezone(timedelta(hours=3)))
    current_time_str = now_moscow.strftime("%H:%M")
    start = getattr(settings, "telegram_working_hours_start", "09:00") or "09:00"
    end = getattr(settings, "telegram_working_hours_end", "23:00") or "23:00"

    if start <= current_time_str <= end:
        return True, f"Активные часы ({start} - {end})"
    return False, f"Ночной режим отдыха ({start} - {end})"


def match_keywords(text: str) -> tuple[bool, str]:
    """Check whether a text looks like a freelance website order and lacks stop words."""
    lowered = text.lower()
    for stop in settings.telegram_stop_words_list:
        if stop in lowered:
            return False, f"Стоп-слово: '{stop}'"

    matched: list[str] = []
    for kw in settings.telegram_keywords_list:
        if kw in lowered:
            matched.append(kw)

    if matched:
        return True, f"Найдено: {', '.join(matched[:3])}"
    return False, "Ключевые слова не найдены"


async def generate_ai_response(order_text: str, category: str = "лендинг") -> str:
    """Generate a polite, non-pushy response using current LLM."""
    system_prompt = (
        "Ты профессиональный независимый веб-разработчик и дизайнер. Напиши короткий, тактичный, "
        "уважительный и абсолютно ненавязчивый отклик на заказ с биржи фриланса.\n"
        "ПРАВИЛА:\n"
        "1. Максимум 3-4 коротких предложения.\n"
        "2. Не хвали себя штампами ('я эксперт с 10-летним стажем').\n"
        "3. Сформулируй суть: задачу понял, опыт в таких проектах есть, сделаю аккуратно и в срок.\n"
        "4. В конце мягко предложи: 'Если интересно, могу прислать пару примеров похожих работ'.\n"
        "5. Никакого давления и спама."
    )
    user_prompt = f"Текст заказа:\n{order_text[:600]}\n\nНапиши персональный отклик:"

    try:
        res = await chat_completion(system=system_prompt, user=user_prompt, max_tokens=2000)
        if res and len(res.strip()) > 30:
            return res.strip()
    except Exception as exc:
        logger.warning("LLM response generation failed: %s, using fallback", exc)

    template = random.choice(FALLBACK_RESPONSES)
    topic = "разработке сайта" if "сайт" in order_text.lower() else "вашему проекту"
    return template.format(topic=topic)


async def generate_ai_promo(portfolio_url: str | None = None) -> str:
    """Generate a unique variation of the freelance pitch for promo broadcasting."""
    url = portfolio_url or getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/")
    system_prompt = (
        "Ты фрилансер веб-разработчик (Murasaki). Напиши привлекательный, живой пост-визитку для телеграм-канала "
        "или чата фриланса в ветку 'Услуги/Резюме'. Напиши от первого лица.\n"
        "Укажи, что делаешь современные продающие сайты, лендинги и Telegram Mini Apps под ключ, берешь 1-2 проекта.\n"
        f"Обязательно включи ссылку на портфолио: {url}.\n"
        "Укажи контакт для связи: @loves_kyni.\n"
        "Без клише и официоза, доброжелательный профессиональный тон."
    )
    user_prompt = f"Ссылка на портфолио: {url}. Напиши уникальный текст визитки:"

    try:
        res = await chat_completion(system=system_prompt, user=user_prompt, max_tokens=2000)
        if res and len(res.strip()) > 40:
            return res.strip()
    except Exception as exc:
        logger.warning("LLM promo generation failed: %s, using fallback", exc)

    template = random.choice(FALLBACK_PROMOS)
    return template.format(portfolio=url)


class TelegramClientManager:
    """Manages Telegram MTProto UserBot and Bot connections.

    Supports both live Telethon connection (when credentials are provided)
    and graceful offline / simulation mode for demo and UI testing.
    """

    _instance: TelegramClientManager | None = None

    def __init__(self) -> None:
        self.is_connected = False
        self.client = None
        self._background_task: asyncio.Task | None = None

    @classmethod
    def get(cls) -> TelegramClientManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def has_credentials(self) -> bool:
        return bool(settings.telegram_api_id and settings.telegram_api_hash)

    async def initialize(self) -> None:
        if not self.has_credentials:
            logger.info("Telegram: no API_ID/API_HASH configured yet. Operating in simulation mode.")
            self._ensure_background_worker()
            return

        try:
            from telethon import TelegramClient

            session_path = (DATA_DIR / "leadradar_user").as_posix()
            self.client = TelegramClient(
                session_path,
                settings.telegram_api_id,
                settings.telegram_api_hash,
                connection_retries=10,
                retry_delay=2,
                timeout=25,
            )
            await self.client.connect()
            if await self.client.is_user_authorized():
                self.is_connected = True
                me = await self.client.get_me()
                logger.info("Telegram: UserBot connected as %s (@%s)", me.first_name, getattr(me, "username", ""))
            else:
                logger.info("Telegram: client connected but authorization code is needed.")
        except Exception as exc:
            logger.warning("Telegram initialization failed: %s", exc)

        self._ensure_background_worker()

    def _ensure_background_worker(self) -> None:
        if self._background_task is None or self._background_task.done():
            self._background_task = asyncio.create_task(self._background_worker())

    async def _background_worker(self) -> None:
        """Periodic background processor for scheduled orders, auto-posting, and external freelance feeds."""
        logger.info("Telegram & Freelance automation background worker started.")
        ticks = 0
        while True:
            try:
                await asyncio.sleep(25)
                ticks += 1
                await self._process_scheduled_orders()
                await self._process_scheduled_posts()

                # Sync Kwork & FL.ru orders every ~3 minutes
                if ticks % 7 == 0:
                    try:
                        from app.services.freelance_fetcher import sync_external_freelance_orders
                        async with SessionLocal() as session:
                            await sync_external_freelance_orders(session)
                    except Exception as exc:
                        logger.warning("Periodic external freelance sync failed: %s", exc)

                # Check auto-blogger for user's channel every ~10 minutes
                if ticks % 24 == 0:
                    await self._process_channel_blog()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in telegram automation worker: %s", exc)

    async def _process_channel_blog(self) -> None:
        """Check if it is time to publish an expert blog post to the user's channel."""
        if not getattr(settings, "channel_blog_enabled", True):
            return

        now = utcnow()
        next_str = getattr(settings, "channel_blog_next_post_at", None)
        if next_str:
            try:
                next_dt = datetime.fromisoformat(next_str)
                if next_dt > now:
                    return
            except Exception:
                pass

        channel_id = getattr(settings, "channel_blog_chat_id", "@Murasaki_website") or "@Murasaki_website"
        try:
            from app.services.telegram_growth import publish_blog_post
            logger.info("Auto-blogger: publishing scheduled blog post to %s", channel_id)
            await publish_blog_post(channel_id=channel_id)
        except Exception as exc:
            logger.warning("Auto-blogger failed to publish post: %s", exc)

    async def _process_scheduled_orders(self) -> None:
        """Send pending responses if auto-response is enabled and within working hours."""
        if not getattr(settings, "telegram_auto_response_enabled", True):
            return

        is_active, _ = is_within_working_hours()
        if not is_active:
            return

        async with SessionLocal() as session:
            now = utcnow()
            stmt = select(TelegramOrder).where(
                TelegramOrder.status == "pending",
                TelegramOrder.scheduled_for <= now,
            )
            pending_orders = (await session.scalars(stmt)).all()

            for order in pending_orders:
                recipient = order.author_username or order.chat_id
                logger.info("Auto-sending outreach response for order %s to %s", order.id, recipient)
                success = await self.send_direct_message(recipient, order.response_text or "")
                order.status = "sent" if success else "failed"
                order.responded_at = utcnow()
                session.add(order)

            if pending_orders:
                await session.commit()

    async def _process_scheduled_posts(self) -> None:
        """Publish scheduled promos to channels that have reached their cooldown."""
        if not getattr(settings, "telegram_auto_posting_enabled", True):
            return

        async with SessionLocal() as session:
            now = utcnow()
            stmt = select(TelegramChatTarget).where(
                TelegramChatTarget.is_active == True,
                TelegramChatTarget.auto_post_enabled == True,
                TelegramChatTarget.kind.in_(("promo", "both")),
            )
            targets = (await session.scalars(stmt)).all()

            for target in targets:
                # Check if it is time to post
                if target.next_post_at and target.next_post_at > now:
                    continue

                portfolio = getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/")
                if target.custom_text and len(target.custom_text.strip()) > 10:
                    text = target.custom_text.replace("{portfolio}", portfolio)
                else:
                    text = await generate_ai_promo(portfolio)

                logger.info("Auto-posting promo to %s (%s)", target.chat_id, target.title)
                success = await self.broadcast_promo(target.chat_id, text)

                target.last_post_at = now
                cd = target.cooldown_minutes or 120
                target.next_post_at = now + timedelta(minutes=cd)
                session.add(target)

                broadcast = TelegramBroadcast(
                    chat_id=target.chat_id,
                    chat_title=target.title or target.chat_id,
                    message_text=text,
                    portfolio_url=portfolio,
                    status="sent" if success else "failed",
                )
                session.add(broadcast)

            if targets:
                await session.commit()

    async def send_direct_message(self, recipient: str, text: str) -> bool:
        """Send a message to a user or chat."""
        if self.is_connected and self.client:
            try:
                await self.client.send_message(recipient, text, parse_mode="md")
                return True
            except Exception as exc:
                logger.error("Failed to send TG message to %s: %s", recipient, exc)
                return False
        logger.info("[Dry Run / Offline] Would send TG message to %s:\n%s", recipient, text)
        return True

    async def broadcast_promo(self, chat_id: str, text: str) -> bool:
        """Post a promo message to a chat."""
        if self.is_connected and self.client:
            try:
                await self.client.send_message(chat_id, text, parse_mode="md")
                return True
            except Exception as exc:
                logger.error("Failed to broadcast promo to %s: %s", chat_id, exc)
                return False
        logger.info("[Dry Run / Offline] Would broadcast promo to %s:\n%s", chat_id, text)
        return True

    async def create_bot_via_botfather(self) -> dict:
        """Automate creating a Telegram Bot via @BotFather using the active user session."""
        if not self.is_connected or not self.client:
            return {"success": False, "error": "Telegram UserBot не подключен к сети"}

        try:
            botfather = await self.client.get_entity("BotFather")

            # Cancel any pending dialog
            await self.client.send_message(botfather, "/cancel")
            await asyncio.sleep(2)

            # Start new bot flow
            await self.client.send_message(botfather, "/newbot")
            await asyncio.sleep(2)

            # Bot name
            bot_name = "Murasaki LeadRadar"
            await self.client.send_message(botfather, bot_name)
            await asyncio.sleep(2)

            # Try generating a unique bot username
            token = None
            bot_username = ""
            for attempt in range(4):
                suffix = random.randint(100, 9999)
                bot_username = f"murasaki_radar_{suffix}_bot"
                await self.client.send_message(botfather, bot_username)
                await asyncio.sleep(3)

                msgs = await self.client.get_messages(botfather, limit=3)
                for m in msgs:
                    match = re.search(r"(\d{8,11}:[a-zA-Z0-9_-]{35})", m.text or "")
                    if match:
                        token = match.group(1)
                        break
                if token:
                    break

            if token:
                settings.telegram_bot_token = token
                env_path = DATA_DIR.parent / ".env"
                if env_path.exists():
                    content = env_path.read_text(encoding="utf-8")
                    if "TELEGRAM_BOT_TOKEN=" in content:
                        content = re.sub(r"TELEGRAM_BOT_TOKEN=.*", f"TELEGRAM_BOT_TOKEN={token}", content)
                    else:
                        content += f"\nTELEGRAM_BOT_TOKEN={token}\n"
                    env_path.write_text(content, encoding="utf-8")

                return {
                    "success": True,
                    "token": token,
                    "bot_username": bot_username,
                    "bot_url": f"https://t.me/{bot_username}",
                }
            return {"success": False, "error": "Не удалось распознать токен из ответа @BotFather"}
        except Exception as exc:
            logger.error("Error creating bot via BotFather: %s", exc)
            return {"success": False, "error": str(exc)}

    async def set_bot_avatar(self, avatar_path: str, bot_username: str = "murasaki_radar_1438_bot") -> dict:
        """Upload a profile avatar to the bot via @BotFather."""
        if not self.is_connected or not self.client:
            return {"success": False, "error": "Telegram UserBot не подключен к сети"}

        p = Path(avatar_path)
        if not p.exists():
            return {"success": False, "error": f"Файл не найден: {avatar_path}"}

        uname = bot_username if bot_username.startswith("@") else f"@{bot_username}"

        try:
            botfather = await self.client.get_entity("BotFather")

            # Cancel dialog
            await self.client.send_message(botfather, "/cancel")
            await asyncio.sleep(2)

            # /setuserpic
            await self.client.send_message(botfather, "/setuserpic")
            await asyncio.sleep(2)

            # Send bot username
            await self.client.send_message(botfather, uname)
            await asyncio.sleep(2)

            # Send image file
            await self.client.send_file(botfather, str(p.resolve()))
            await asyncio.sleep(3)

            # Read latest response
            msgs = await self.client.get_messages(botfather, limit=2)
            last_text = msgs[0].text if msgs else ""
            logger.info("BotFather avatar response: %s", last_text)
            return {"success": True, "message": last_text}
        except Exception as exc:
            logger.error("Error setting bot avatar via BotFather: %s", exc)
            return {"success": False, "error": str(exc)}


# Global manager instance
telegram_manager = TelegramClientManager.get()
