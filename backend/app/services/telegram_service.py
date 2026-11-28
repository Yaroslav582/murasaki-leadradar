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
from app.services.ai_router import ask_ai

logger = logging.getLogger(__name__)

# Verified active freelance channels & chats
DEFAULT_TARGETS = [
    {
        "chat_id": "@Murasaki_website",
        "title": "Murasaki | Собственный канал",
        "username": "Murasaki_website",
        "kind": "promo",
        "cooldown_minutes": 1440,
        "auto_post_enabled": False,
        "custom_text": None,
    },
    {
        "chat_id": "@freelancetavern",
        "title": "Freelance Tavern (Заказы)",
        "username": "freelancetavern",
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
        "title": "Фриланс чат | Вакансии",
        "username": "freelance_chat_ru",
        "kind": "both",
        "cooldown_minutes": 90,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@zakazy_freelance",
        "title": "Заказы для фрилансеров",
        "username": "zakazy_freelance",
        "kind": "both",
        "cooldown_minutes": 90,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@designer_jobs",
        "title": "Вакансии и заказы на дизайн",
        "username": "designer_jobs",
        "kind": "both",
        "cooldown_minutes": 180,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@digital_rabota",
        "title": "Я работаю в digital, детка",
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
        "chat_id": "@frilans_zakazi",
        "title": "Удаленная работа | фриланс заказы",
        "username": "frilans_zakazi",
        "kind": "both",
        "cooldown_minutes": 120,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@temalebedev",
        "title": "Артемий Лебедев",
        "username": "temalebedev",
        "kind": "promo",
        "cooldown_minutes": 240,
        "auto_post_enabled": False,
    },
    {
        "chat_id": "@designer_ru",
        "title": "ИЩУ_ДИЗАЙНЕРА",
        "username": "designer_ru",
        "kind": "both",
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
    "Создаю Telegram Mini Apps и интерактивные сайты для бизнеса: онлайн-запись, каталоги и оформление заявок прямо внутри Telegram в 2 клика.\n\nПримеры кейсов: {portfolio}\nНужен бот или Mini App для вашего проекта? Напишите мне в ЛС @loves_kyni — подскажу варианты реализации.",
    "Планируете запуск продукта или редизайн сайта? Делаю быстрые адаптивные лендинги с понятной структурой и высокой конверсией в заявки.\n\nОзнакомиться с портфолио: {portfolio}\nДля бесплатного аудита и консультации пишите в ЛС @loves_kyni.",
    "Разработка сайтов и Telegram Mini Apps для сферы услуг, e-commerce и экспертов. От первого прототипа до полного запуска.\n\nСмотрите работы в портфолио: {portfolio}\nОбсудить задачу или узнать сроки: @loves_kyni",
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
        res = await ask_ai(user_prompt, system_prompt=system_prompt, task_type="smart", max_tokens=300)
        if res and len(res.strip()) > 30:
            return res.strip()
    except Exception as exc:
        logger.warning("LLM response generation failed: %s, using fallback", exc)

    template = random.choice(FALLBACK_RESPONSES)
    topic = "разработке сайта" if "сайт" in order_text.lower() else "вашему проекту"
    return template.format(topic=topic)


KWORK_STYLE_GUIDANCE = {
    "balanced": (
        "Стиль «Деловой оптимальный» (500–800 символов):\n"
        "- Первая строка сразу показывает, что ты прочитал заявку (упомяни конкретную деталь/цель из текста заказа).\n"
        "- Кратко опиши 2–3 понятных шага, как решишь задачу и какой будет результат.\n"
        "- Задай 1 точный уточняющий вопрос по ТЗ, чтобы заказчик ответил в диалог."
    ),
    "short": (
        "Стиль «Короткий и быстрый» (250–450 символов, максимум 3 предложения):\n"
        "- Сразу по делу без приветственных штампов.\n"
        "- Скажи, что сделаешь по этой задаче, назови ориентир (если есть) и задай 1 короткий вопрос."
    ),
    "demo_first": (
        "Стиль «С бесплатным мини-прототипом» (450–750 символов):\n"
        "- Покажи, что понял задачу из заявки.\n"
        "- Предложи сильный ход: до старта сделки можешь бесплатно набросать концепт/прототип первого экрана под их нишу, чтобы сразу было видно стиль и структуру.\n"
        "- В конце мягко спроси, актуально ли скинуть такой набросок и обсудить детали."
    ),
    "expert": (
        "Стиль «Экспертный разбор» (600–900 символов):\n"
        "- Коротко разбери задачу заказчика (структура/блоки/стек/адаптив/скорость — строго по тому, что в заявке).\n"
        "- Отметь 1 важный нюанс, о котором заказчики обычно забывают.\n"
        "- Задай 1–2 конкретных вопроса по материалам или функционалу."
    ),
}


def extract_order_summary(order_text: str) -> str:
    """Extracts a clean short title (<= 90 chars) from raw order text."""
    for raw_line in (order_text or "").splitlines():
        clean = " ".join(raw_line.split()).strip()
        if len(clean) >= 6:
            return clean[:87] + "..." if len(clean) > 90 else clean
    flat = " ".join((order_text or "").split()).strip()
    return (flat[:87] + "...") if len(flat) > 90 else (flat or "Заявка с Kwork")


async def build_kwork_proposal(
    order_text: str,
    style: str = "balanced",
    portfolio_url: str | None = None,
    price_hint: str | None = None,
    deadline_hint: str | None = None,
    include_portfolio: bool = True,
) -> str:
    """Generates a tailored Kwork bid/proposal from pasted order text."""
    norm_style = style if style in KWORK_STYLE_GUIDANCE else "balanced"
    portfolio = (
        portfolio_url
        or getattr(settings, "telegram_portfolio_url", None)
        or "https://murasaki-portfolio.vercel.app/"
    ).strip()

    extra_constraints = []
    if price_hint and price_hint.strip():
        extra_constraints.append(f"Ориентир по бюджету/стоимости (упомяни органично): {price_hint.strip()}")
    if deadline_hint and deadline_hint.strip():
        extra_constraints.append(f"Ориентир по срокам (упомяни органично): {deadline_hint.strip()}")
    if include_portfolio and portfolio:
        extra_constraints.append(
            f"Добавь ссылку на портфолио отдельной строкой в конце: «Портфолио: {portfolio}» (без точки после URL)."
        )
    else:
        extra_constraints.append("НЕ вставляй никаких ссылок в текст отклика.")

    system_prompt = (
        "Ты — веб-разработчик и дизайнер студии Murasaki, откликаешься на проект на бирже Kwork.\n"
        "Главное правило Kwork: заказчик читает первые 2 строчки среди 20 одинаковых шаблонов. "
        "ЗАПРЕЩЕНЫ клише: 'имею большой опыт', 'готов выполнить качественно и в срок', 'индивидуальный подход', 'буду рад сотрудничеству'.\n"
        "Пиши живым, грамотным человеческим языком на «вы», строго по фактам из текста заявки."
    )
    user_prompt = (
        f"{KWORK_STYLE_GUIDANCE[norm_style]}\n\n"
        "Дополнительные условия:\n"
        + "\n".join(f"- {c}" for c in extra_constraints)
        + f"\n\nТекст заявки заказчика:\n\"\"\"\n{order_text.strip()[:3500]}\n\"\"\"\n\n"
        "Верни ТОЛЬКО готовый текст отклика, который можно сразу скопировать и отправить на Kwork."
    )

    try:
        res = await ask_ai(
            user_prompt,
            system_prompt=system_prompt,
            task_type="smart",
            max_tokens=500,
            temperature=0.6,
        )
        if res and len(res.strip()) >= 40:
            cleaned = res.strip().strip('"').strip("«»")
            return cleaned
    except Exception as exc:
        logger.warning("Kwork proposal LLM generation failed: %s, using fallback", exc)

    summary = extract_order_summary(order_text)
    price_part = f" По бюджету ориентируюсь на {price_hint.strip()}." if price_hint and price_hint.strip() else ""
    deadline_part = f" По срокам — {deadline_hint.strip()}." if deadline_hint and deadline_hint.strip() else ""
    port_part = f"\n\nПортфолио: {portfolio}" if include_portfolio and portfolio else ""

    if norm_style == "short":
        return (
            f"Здравствуйте! Посмотрел вашу задачу («{summary}») — сделаю аккуратно под ключ с адаптивом.{price_part}{deadline_part} "
            "Подскажите, есть ли уже референсы или готовый контент?"
            f"{port_part}"
        )
    if norm_style == "demo_first":
        return (
            f"Здравствуйте! Изучил задачу по проекту «{summary}».\n\n"
            "Можем начать без риска: до оформления заказа соберу быстрый демо-прототип первого экрана под вашу тематику, "
            f"чтобы вы сразу увидели подачу и структуру.{price_part}{deadline_part}\n\n"
            "Если формат подойдёт — обсудим детали, материалы и запустим в работу. Скинуть набросок?"
            f"{port_part}"
        )
    if norm_style == "expert":
        return (
            f"Здравствуйте! Разобрал вашу заявку («{summary}»).\n\n"
            "По реализации предложу чистую структуру: адаптивная вёрстка под мобильные, быстрая загрузка, "
            "продуманные акценты на целевых действиях и настроенные формы обратной связи."
            f"{price_part}{deadline_part}\n\n"
            "Пара вопросов для точной оценки:\n"
            "1. Есть ли уже тексты/фото или нужно помочь со структурой?\n"
            "2. На каком домене или платформе планируете запуск?"
            f"{port_part}"
        )
    return (
        f"Здравствуйте! Посмотрел заявку по проекту «{summary}» — задача понятна, могу взять в работу.\n\n"
        "Соберу современную адаптивную версию с акцентом на удобство с телефона и понятную подачу ваших услуг/преимуществ, "
        f"подключу заявки и проверю скорость работы.{price_part}{deadline_part}\n\n"
        "Подскажите, есть ли у вас примеры сайтов, которые нравятся по стилю, или подготовить пару вариантов от себя?"
        f"{port_part}"
    )


async def generate_ai_promo(portfolio_url: str | None = None) -> str:
    """Generate a unique variation of the freelance pitch for promo broadcasting."""
    url = portfolio_url or getattr(settings, "telegram_portfolio_url", "https://murasaki-portfolio.vercel.app/")
    system_prompt = (
        "Ты фрилансер веб-разработчик (Murasaki). Напиши привлекательный, живой пост-визитку для телеграм-канала "
        "или чата фриланса в ветку 'Услуги/Резюме'. Напиши от первого лица.\n"
        "Укажи, что делаешь современные продающие сайты, лендинги и Telegram Mini Apps под ключ, берешь 1-2 проекта.\n"
        f"Обязательно включи ссылку на портфолио: {url}.\n"
        "Укажи контакт для связи: @loves_kyni.\n"
        "ВАЖНО: Текст прикрепляется к фото (скриншоту первой страницы портфолио), поэтому длина текста строго ДО 800 символов.\n"
        "Структурируй лаконично, с понятными буллетами. Без клише и официоза, доброжелательный профессиональный тон."
    )
    user_prompt = f"Ссылка на портфолио: {url}. Напиши уникальный текст визитки (до 800 символов):"

    try:
        res = await ask_ai(user_prompt, system_prompt=system_prompt, task_type="fast", max_tokens=350)
        if res and len(res.strip()) > 40:
            return res.strip()
    except Exception as exc:
        logger.warning("LLM promo generation failed: %s, using fallback", exc)

    template = random.choice(FALLBACK_PROMOS)
    return template.format(portfolio=url)


class BroadcastResult:
    """Result object that behaves as a boolean and unpacks into (success, error)."""
    def __init__(self, success: bool, error: str | None = None) -> None:
        self.success = success
        self.error = error

    def __bool__(self) -> bool:
        return self.success

    def __iter__(self):
        return iter((self.success, self.error))

    def __repr__(self) -> str:
        return f"BroadcastResult(success={self.success}, error={self.error})"


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

    async def get_active_client(self) -> Any:
        """Returns an active, authorized Telethon client from telegram_manager or account_pool."""
        if self.client and self.is_connected:
            try:
                if self.client.is_connected() and await self.client.is_user_authorized():
                    return self.client
            except Exception:
                pass

        # 1. Check account_pool for connected active clients
        try:
            from app.services.account_pool import account_pool
            for acc_id, client in list(account_pool._active_clients.items()):
                if client and client.is_connected():
                    try:
                        if await client.is_user_authorized():
                            self.client = client
                            self.is_connected = True
                            return client
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("Could not inspect account_pool: %s", exc)

        # 2. Query Supabase tg_accounts for active session
        try:
            from app.db import SessionLocal
            from app.models import TgAccount
            from app.services.account_pool import account_pool

            async with SessionLocal() as db_session:
                stmt = select(TgAccount).where(
                    TgAccount.session_string.isnot(None),
                    TgAccount.status.in_(["active", "warming"]),
                ).order_by(TgAccount.updated_at.desc())
                acc = (await db_session.execute(stmt)).scalars().first()
                if acc and acc.session_string:
                    client = await account_pool.get_client_for_account(acc)
                    await client.connect()
                    if await client.is_user_authorized():
                        account_pool._attach_message_handler(client, acc)
                        self.client = client
                        self.is_connected = True
                        logger.info("Attached active Telethon client for UserBot from account %s (@%s)", acc.phone, acc.username)
                        return client
        except Exception as exc:
            logger.warning("Could not instantiate client from tg_accounts: %s", exc)

        return None

    async def initialize(self) -> None:
        if not self.has_credentials:
            logger.info("Telegram: no API_ID/API_HASH configured yet. Operating in simulation mode.")
            self._ensure_background_worker()
            return

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            from app.models import TgAccount

            session_str = getattr(settings, "telegram_session_string", None)

            # 1. Try loading StringSession from Supabase tg_accounts
            if not session_str:
                try:
                    async with SessionLocal() as db_session:
                        stmt = select(TgAccount).where(
                            TgAccount.session_string.isnot(None),
                            TgAccount.status.in_(["active", "warming"]),
                        )
                        if settings.telegram_phone:
                            stmt = select(TgAccount).where(
                                TgAccount.phone == settings.telegram_phone,
                                TgAccount.session_string.isnot(None),
                            )
                        acc = (await db_session.execute(stmt)).scalars().first()
                        if acc and acc.session_string:
                            session_str = acc.session_string
                            logger.info("Loaded Telethon session from Supabase tg_accounts (phone=%s)", acc.phone)
                except Exception as db_err:
                    logger.warning("Could not query tg_accounts for session_string: %s", db_err)

            # 2. Seamless fallback: migrate legacy local session file if present
            if not session_str:
                local_session_file = DATA_DIR / "leadradar_user.session"
                if local_session_file.exists():
                    try:
                        temp_client = TelegramClient(
                            (DATA_DIR / "leadradar_user").as_posix(),
                            settings.telegram_api_id,
                            settings.telegram_api_hash,
                        )
                        session_str = StringSession.save(temp_client.session)
                        if session_str:
                            logger.info("Migrated legacy leadradar_user.session to StringSession (%d chars)", len(session_str))
                    except Exception as exc:
                        logger.warning("Could not convert local leadradar_user.session: %s", exc)

            session_arg = StringSession(session_str) if session_str else StringSession("")
            self.client = TelegramClient(
                session_arg,
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

                # Persist active StringSession into Supabase tg_accounts
                saved_str = self.client.session.save()
                if saved_str:
                    try:
                        async with SessionLocal() as db_session:
                            phone = settings.telegram_phone or getattr(me, "phone", "") or "+14642193549"
                            stmt = select(TgAccount).where(TgAccount.phone == phone)
                            acc = (await db_session.execute(stmt)).scalars().first()
                            if acc:
                                acc.session_string = saved_str
                                acc.status = "active"
                            else:
                                acc = TgAccount(
                                    phone=phone,
                                    username=getattr(me, "username", None),
                                    session_string=saved_str,
                                    status="active",
                                )
                                db_session.add(acc)
                            await db_session.commit()
                            logger.info("Persisted active StringSession in Supabase tg_accounts for %s", phone)
                    except Exception as save_err:
                        logger.warning("Could not persist session_string to Supabase: %s", save_err)
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
        from app.models import AppSetting
        from app.db import SessionLocal

        now = utcnow()
        cfg: dict[str, Any] = {}
        try:
            async with SessionLocal() as db_session:
                st = await db_session.get(AppSetting, "channel_blog_settings")
                if st and st.value:
                    cfg = dict(st.value)
        except Exception as db_err:
            logger.debug("Failed reading channel_blog_settings from DB: %s", db_err)

        enabled = cfg.get("enabled", getattr(settings, "channel_blog_enabled", True))
        if not enabled:
            return

        interval_hours = int(cfg.get("interval_hours", getattr(settings, "channel_blog_interval_hours", 24)) or 24)
        next_str = cfg.get("next_post_at") or getattr(settings, "channel_blog_next_post_at", None)

        if next_str:
            try:
                next_dt = datetime.fromisoformat(next_str)
                if next_dt > now:
                    return
            except Exception:
                pass

        channel_id = cfg.get("channel_id") or getattr(settings, "channel_blog_chat_id", "@Murasaki_website") or "@Murasaki_website"
        try:
            from app.services.telegram_growth import publish_blog_post
            logger.info("Auto-blogger: publishing scheduled blog post to %s (interval=%dh)", channel_id, interval_hours)
            await publish_blog_post(channel_id=channel_id, interval_hours=interval_hours)
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
                # Do NOT auto-post short promo pitches to user's personal blog channel
                blog_channel = (getattr(settings, "channel_blog_chat_id", "@Murasaki_website") or "@Murasaki_website").lower().strip()
                if target.chat_id.lower().strip() == blog_channel:
                    continue

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

    async def send_direct_message(self, recipient: str, text: str) -> BroadcastResult:
        """Send a message to a user or chat using active Telethon client."""
        client = await self.get_active_client()
        if not client:
            err = "Telegram UserBot не авторизован: подключите Telegram-аккаунт во вкладке Прогрев"
            logger.warning(err)
            return BroadcastResult(False, err)

        try:
            clean = recipient.lstrip("@").strip()
            try:
                entity = await client.get_entity(recipient)
            except Exception:
                entity = await client.get_entity(clean)

            await client.send_message(entity, text, parse_mode="md", link_preview=False)
            logger.info("Successfully sent direct message to %s", recipient)
            return BroadcastResult(True, None)
        except Exception as exc:
            err_msg = str(exc)
            logger.error("Failed to send direct message to %s: %s", recipient, exc)
            return BroadcastResult(False, err_msg)

    async def broadcast_promo(self, chat_id: str, text: str, image_path: str | None = None) -> BroadcastResult:
        """Post a promo message to a chat using active Telethon client with portfolio screenshot."""
        client = await self.get_active_client()
        if not client:
            err = "Telegram UserBot не авторизован: подключите Telegram-аккаунт во вкладке Прогрев"
            logger.warning(err)
            return BroadcastResult(False, err)

        try:
            clean = chat_id.lstrip("@").strip()
            try:
                entity = await client.get_entity(chat_id)
            except Exception:
                entity = await client.get_entity(clean)

            # Resolve portfolio screenshot image (first page of portfolio)
            from pathlib import Path
            img_file = None
            if image_path and Path(image_path).is_file():
                img_file = Path(image_path)
            else:
                static_dir = Path(__file__).resolve().parent.parent / "static"
                default_candidates = [
                    static_dir / "portfolio_hero.png",
                    DATA_DIR / "portfolio_hero.png",
                    DATA_DIR / "portfolio_screen.jpg",
                ]
                for cand in default_candidates:
                    if cand.is_file():
                        img_file = cand
                        break

            # Send as photo with caption if image is available, else send text without link preview
            if img_file:
                logger.info("Sending promo with portfolio screenshot (%s) to %s", img_file.name, chat_id)
                if len(text) <= 1020:
                    try:
                        await client.send_file(
                            entity,
                            file=img_file.as_posix(),
                            caption=text,
                            parse_mode="md",
                        )
                    except Exception as caption_err:
                        logger.warning("Caption send failed on %s (%s), sending photo and message separately", chat_id, caption_err)
                        await client.send_file(entity, file=img_file.as_posix())
                        await client.send_message(entity, text, parse_mode="md", link_preview=False)
                else:
                    logger.info("Text length (%d) > 1020, sending photo then text separately with link_preview=False", len(text))
                    await client.send_file(entity, file=img_file.as_posix())
                    await client.send_message(entity, text, parse_mode="md", link_preview=False)
            else:
                await client.send_message(entity, text, parse_mode="md", link_preview=False)

            logger.info("Successfully published promo post to %s", chat_id)
            return BroadcastResult(True, None)
        except Exception as exc:
            err_msg = str(exc)
            logger.error("Failed to broadcast promo to %s: %s", chat_id, exc)
            return BroadcastResult(False, err_msg)

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
                try:
                    from app.models import AppSetting
                    async with SessionLocal() as db_session:
                        st = await db_session.get(AppSetting, "telegram_bot_token")
                        if st:
                            st.value = {"token": token, "bot_username": bot_username}
                        else:
                            db_session.add(AppSetting(key="telegram_bot_token", value={"token": token, "bot_username": bot_username}))
                        await db_session.commit()
                except Exception as db_err:
                    logger.debug("Could not persist bot token to AppSetting: %s", db_err)

                env_path = DATA_DIR.parent / ".env"
                if env_path.exists():
                    try:
                        content = env_path.read_text(encoding="utf-8")
                        if "TELEGRAM_BOT_TOKEN=" in content:
                            content = re.sub(r"TELEGRAM_BOT_TOKEN=.*", f"TELEGRAM_BOT_TOKEN={token}", content)
                        else:
                            content += f"\nTELEGRAM_BOT_TOKEN={token}\n"
                        env_path.write_text(content, encoding="utf-8")
                    except Exception:
                        pass

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
