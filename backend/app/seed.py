from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from app.db import SessionLocal, init_db
from app.models import Dialog, Lead, Message, Proxy, TgAccount, Transaction, User, utcnow
from app.providers.demo import CATEGORIES, CITIES, DemoProvider
from app.services.demos import create_demo
from app.services.jobs import save_places

logger = logging.getLogger(__name__)

SEED_CITIES = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Сочи", "Краснодар"]


async def seed_demo_data() -> int:
    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count(Lead.id))) or 0
        if existing:
            return 0

        provider = DemoProvider()
        created_leads: list[Lead] = []
        for city in SEED_CITIES:
            places = await provider.search(
                city=city,
                categories=CATEGORIES,
                query=None,
                limit=9,
            )
            _created, _updated, leads = await save_places(session, places, city)
            created_leads.extend(leads)

        for index, lead in enumerate(created_leads):
            if index % 23 == 7:
                lead.status = "deal"
            elif index % 17 == 5:
                lead.status = "sent"
            elif index % 11 == 3:
                lead.status = "database"
            elif index % 29 == 19:
                lead.status = "rejected"
            if lead.status == "deal":
                lead.notes = "Созвонились, ждём подтверждение. Демо понравилось."
            session.add(lead)

        await session.commit()

        demo_targets = [lead for lead in created_leads if not lead.has_website][:2]
        for lead in demo_targets:
            await create_demo(session, lead)

        logger.info("Seeded %s demo leads", len(created_leads))
        return len(created_leads)


async def seed_telegram_data() -> dict[str, int]:
    """Ensure Telegram freelance channels and initial orders are seeded on startup."""
    from datetime import timedelta
    import random
    from app.models import TelegramChatTarget, TelegramOrder, utcnow
    from app.services.telegram_service import DEFAULT_TARGETS

    seeded_counts = {"chats": 0, "orders": 0}

    async with SessionLocal() as session:
        # 1. Seed chat targets if empty or missing
        existing_chats = (await session.scalars(select(TelegramChatTarget.chat_id))).all()
        existing_chat_ids = set(existing_chats)

        for target in DEFAULT_TARGETS:
            if target["chat_id"] not in existing_chat_ids:
                session.add(TelegramChatTarget(**target))
                existing_chat_ids.add(target["chat_id"])
                seeded_counts["chats"] += 1

        # 2. Seed initial freelance orders if none exist
        orders_count = await session.scalar(select(func.count(TelegramOrder.id))) or 0
        if orders_count == 0:
            now = utcnow()
            sample_orders = [
                {
                    "source": "telegram",
                    "chat_id": "@freelancetavern",
                    "chat_title": "Фриланс Таверна (Заказы)",
                    "message_id": 84120,
                    "author_username": "ekaterina_pro",
                    "author_name": "Екатерина (Салон Beauty)",
                    "raw_text": "Ищем веб-дизайнера / разработчика для создания лендинга под ключ для премиального салона красоты. Нужен чистый современный дизайн, адаптив под смартфоны, подключение формы заявки в Telegram. Бюджет 35 000 - 50 000 руб. Сроки до 1 недели. Ждем отклики с примерами работ в ЛС @ekaterina_pro.",
                    "summary": "Лендинг для салона красоты",
                    "category": "Лендинг",
                    "budget": "35 000 - 50 000 ₽",
                    "response_text": "Здравствуйте! Увидел ваш заказ на лендинг для салона красоты. Могу взять в работу — делаю адаптивные сайты под ключ с чистым кодом и быстрым запуском за 3-5 дней. Если предложение актуально, напишите в ответ — скину пару примеров похожих работ.",
                    "scheduled_for": now + timedelta(minutes=8),
                    "status": "pending",
                },
                {
                    "source": "telegram",
                    "chat_id": "@tg_bots_orders",
                    "chat_title": "Заказы Telegram ботов и WebApps",
                    "message_id": 84121,
                    "author_username": "pizzaman_chef",
                    "author_name": "Шеф Пицца",
                    "raw_text": "Нужен Telegram Mini App (TMA) для доставки пиццы и суши: меню с корзиной, выбор адреса и оплата. Кто уже делал WebApp ботов в TG, скиньте портфолио в лс @pizzaman_chef.",
                    "summary": "Telegram Mini App доставки еды",
                    "category": "Веб-сайт",
                    "budget": "60 000 ₽",
                    "response_text": "Здравствуйте! Понял задачу: нужен Telegram Mini App для доставки с каталогом, корзиной и оплатой. Уже реализовал несколько TMA под ключ. Буду рад обсудить проект и показать похожие кейсы.",
                    "scheduled_for": now + timedelta(minutes=11),
                    "status": "pending",
                },
                {
                    "source": "kwork",
                    "source_url": "https://kwork.ru/projects/3272066",
                    "chat_id": "kwork.ru",
                    "chat_title": "Kwork — Биржа проектов",
                    "message_id": 3272066,
                    "author_username": "Заказчик Kwork",
                    "author_name": "Заказчик Kwork (Kwork)",
                    "raw_text": "Нужно разработать интернет магазин с продающим дизайном на тильда с корзиной и панелью для менеджеров по продажам. Настроить Jivo чат, загрузить 200 позиций продукции.",
                    "summary": "Интернет-магазин на Тильде с корзиной и товарами",
                    "category": "Сайт под ключ",
                    "budget": "90 000 ₽",
                    "response_text": "Здравствуйте! Готов взять разработку интернет-магазина. Опыт с каталогами на Тильде и интеграцией онлайн-оплаты большой. Сделаем удобную структуру и стильный дизайн.",
                    "scheduled_for": now + timedelta(minutes=14),
                    "status": "pending",
                },
                {
                    "source": "fl",
                    "source_url": "https://www.fl.ru/projects/5528469",
                    "chat_id": "fl.ru",
                    "chat_title": "FL.ru — Биржа фриланса",
                    "message_id": 5528469,
                    "author_username": "fl_client",
                    "author_name": "Заказчик на FL.ru",
                    "raw_text": "Нужно разработать современный корпоративный сайт компании с каталогом услуг и калькулятором стоимости.",
                    "summary": "Корпоративный сайт с калькулятором",
                    "category": "Веб-сайт",
                    "budget": "75 000 ₽",
                    "response_text": "Добрый день! Задача понятна: разработка адаптивного корпоративного сайта с калькулятором. Делаю чистый код и быстрый запуск. Напишите — покажу примеры калькуляторов в работах.",
                    "scheduled_for": now + timedelta(minutes=16),
                    "status": "pending",
                },
                {
                    "source": "telegram",
                    "chat_id": "@zakazy_freelance",
                    "chat_title": "Биржа заказов Freelance",
                    "message_id": 84122,
                    "author_username": "mikhail_auto",
                    "author_name": "Михаил (Автосервис)",
                    "raw_text": "Нужен сайт для автосервиса и шиномонтажа в Краснодаре. 4 блока: услуги, прайс, отзывы, контакты и кнопка вызова эвакуатора/записи. Дизайн строгий, темная тема. @mikhail_auto.",
                    "summary": "Сайт автосервиса под ключ",
                    "category": "Веб-сайт",
                    "budget": "25 000 ₽",
                    "response_text": "Приветствую! Готов разработать стильный сайт для автосервиса с темной темой и удобной кнопкой вызова/записи. Сделаю за 3 дня. Напишите в ЛС, скину кейсы в смежных сферах.",
                    "scheduled_for": now - timedelta(minutes=25),
                    "responded_at": now - timedelta(minutes=24),
                    "status": "sent",
                },
            ]
            for order_data in sample_orders:
                session.add(TelegramOrder(**order_data))
                seeded_counts["orders"] += 1

        await session.commit()

    if seeded_counts["chats"] or seeded_counts["orders"]:
        logger.info("Seeded Telegram targets/orders: %s", seeded_counts)
    return seeded_counts


async def seed_accounts_and_dialogs_data() -> dict[str, int]:
    counts = {"accounts": 0, "proxies": 0, "dialogs": 0}
    async with SessionLocal() as session:
        # Check if accounts exist
        existing_acc = await session.scalar(select(func.count(TgAccount.id))) or 0
        if existing_acc:
            return counts

        # Seed Proxy
        proxy = Proxy(
            protocol="socks5",
            host="185.220.101.5",
            port=1080,
            username="murasaki_proxy",
            password="secret_password",
            is_alive=True,
            last_check=utcnow(),
        )
        session.add(proxy)
        await session.flush()
        counts["proxies"] += 1

        # Seed 2 Demo Accounts
        acc1 = TgAccount(
            phone="+79991234567",
            username="murasaki_radar_main",
            device_model="Samsung Galaxy S22 Ultra",
            system_version="Android 13, One UI 5.1",
            app_version="Telegram Android 9.6.5",
            proxy_id=proxy.id,
            status="active",
            warmup_level=85,
            warmup_preset="optimal",
            auto_warmup=True,
            daily_actions_count=4,
        )
        acc2 = TgAccount(
            phone="+79189876543",
            username="lead_hunter_pro",
            device_model="Google Pixel 7 Pro",
            system_version="Android 14, UpsideDownCake",
            app_version="Telegram Android 10.1.2",
            proxy_id=proxy.id,
            status="warming",
            warmup_level=45,
            warmup_preset="light",
            auto_warmup=True,
            daily_actions_count=2,
        )
        session.add_all([acc1, acc2])
        await session.flush()
        counts["accounts"] += 2

        # Seed Dialogs & Messages
        from datetime import timedelta
        now = utcnow()

        # Dialog 1: Deal
        d1 = Dialog(
            account_id=acc1.id,
            peer_id="594812301",
            peer_username="artem_barber",
            peer_name="Артём (Барбершоп 'OldBoy')",
            status="deal",
            unread_count=0,
            last_message_at=now - timedelta(minutes=14),
        )
        session.add(d1)
        await session.flush()

        m1 = Message(
            dialog_id=d1.id,
            account_id=acc1.id,
            direction="out",
            text="Здравствуйте, Артём! Обратили внимание на ваш барбершоп в Москве. Собрали для вас интерактивное демо нового сайта с онлайн-записью: https://murasaki-portfolio.vercel.app/",
            is_ai_generated=True,
            created_at=now - timedelta(hours=2),
        )
        m2 = Message(
            dialog_id=d1.id,
            account_id=acc1.id,
            direction="in",
            text="Добрый день! Посмотрел демо, выглядит очень круто. Сколько будет стоить внедрить такое под наш филиал и возможен ли созвон сегодня в 17:00?",
            is_ai_generated=False,
            created_at=now - timedelta(minutes=35),
        )
        m3 = Message(
            dialog_id=d1.id,
            account_id=acc1.id,
            direction="out",
            text="Отлично! Да, созвон в 17:00 идеально подойдёт. Стоимость базовой интеграции около 35 000 ₽. Ссылку на Google Meet пришлю за 15 минут до созвона.",
            is_ai_generated=True,
            created_at=now - timedelta(minutes=14),
        )
        session.add_all([m1, m2, m3])

        # Dialog 2: AI Handling
        d2 = Dialog(
            account_id=acc1.id,
            peer_id="481920311",
            peer_username="elena_yoga",
            peer_name="Елена Смирнова (Йога-студия)",
            status="ai_handling",
            unread_count=1,
            last_message_at=now - timedelta(minutes=4),
        )
        session.add(d2)
        await session.flush()

        m2_1 = Message(
            dialog_id=d2.id,
            account_id=acc1.id,
            direction="out",
            text="Елена, здравствуйте! Заметили, что у вашей студии йоги много отзывов на картах, но нет удобного сайта с расписанием тренировок. Мы сделали готовый концепт, показать?",
            is_ai_generated=True,
            created_at=now - timedelta(hours=3),
        )
        m2_2 = Message(
            dialog_id=d2.id,
            account_id=acc1.id,
            direction="in",
            text="Здравствуйте! Да, пришлите пожалуйста ссылку, как раз думаем об обновлении сайта.",
            is_ai_generated=False,
            created_at=now - timedelta(minutes=4),
        )
        session.add_all([m2_1, m2_2])
        counts["dialogs"] += 2

        await session.commit()
        logger.info("Seeded accounts, proxy, dialogs: %s", counts)

    return counts


async def _main() -> None:
    await init_db()
    count = await seed_demo_data()
    print(f"Seeded {count} leads")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
