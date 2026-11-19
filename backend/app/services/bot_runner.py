from __future__ import annotations

import asyncio
import html
import logging
import random
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Lead, TelegramOrder, utcnow
from app.services.lead_notifier import WEB_APP_URL, lead_notifier

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 <b>Добро пожаловать в Murasaki LeadRadar!</b>\n\n"
    "🚀 <b>Ваш личный радар заказов и AI-ассистент:</b>\n"
    "• Мониторинг заказов с бирж <b>Kwork</b> и <b>FL.ru</b> в реальном времени\n"
    "• Радар Telegram-каналов и чатов фриланса\n"
    "• Мгновенные уведомления о новых заказах прямо в этот чат\n"
    "• Генерация офферов в 1 клик и <b>автоотклик с вашего Telegram-аккаунта</b>\n"
    "• Автопостинг промо с портфолио по расписанию\n\n"
    "🔔 <i>Этот чат подключен к уведомлениям о новых заказах!</i>\n"
    "👇 Откройте Mini App или нажмите /test_lead для проверки:"
)


class TelegramBotRunner:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not settings.telegram_bot_token:
            logger.info("Bot runner: no TELEGRAM_BOT_TOKEN set.")
            return
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _handle_callback_query(
        self, client: httpx.AsyncClient, base_url: str, callback_query: dict[str, Any]
    ) -> None:
        cb_id = callback_query.get("id")
        cb_data = callback_query.get("data") or ""
        msg = callback_query.get("message") or {}
        chat_id = msg.get("chat", {}).get("id")
        message_id = msg.get("message_id")

        if not chat_id or not message_id:
            try:
                await client.post(f"{base_url}/answerCallbackQuery", json={"callback_query_id": cb_id})
            except Exception:
                pass
            return

        # 0. Action: Trigger test lead from button
        if cb_data == "cmd:test_lead":
            try:
                await client.post(
                    f"{base_url}/answerCallbackQuery",
                    json={"callback_query_id": cb_id, "text": "⚡️ Создаю тестовую карточку заказа..."},
                )
            except Exception:
                pass
            await self._handle_test_lead_command(client, base_url, chat_id)
            return

        # 1. Action: Generate AI Offer (gen_offer:<order_id>)
        if cb_data.startswith("gen_offer:"):
            order_id = cb_data.split(":", 1)[1]
            try:
                await client.post(
                    f"{base_url}/answerCallbackQuery",
                    json={"callback_query_id": cb_id, "text": "✨ Нейросеть генерирует персональный оффер..."},
                )
            except Exception:
                pass

            async with SessionLocal() as session:
                order = await session.get(TelegramOrder, order_id)
                if not order:
                    return

                from app.services.telegram_service import generate_ai_response

                new_response = await generate_ai_response(
                    order.raw_text, category=order.category
                )
                order.response_text = new_response
                await session.commit()
                await session.refresh(order)

                text, markup = lead_notifier.format_order_card(order)
                await client.post(
                    f"{base_url}/editMessageText",
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": markup,
                        "disable_web_page_preview": True,
                    },
                )
            return

        # 2. Action: Auto-reply from User's Account (auto_reply:<order_id>)
        if cb_data.startswith("auto_reply:"):
            order_id = cb_data.split(":", 1)[1]
            try:
                await client.post(
                    f"{base_url}/answerCallbackQuery",
                    json={"callback_query_id": cb_id, "text": "🚀 Отправляю отклик с вашего аккаунта..."},
                )
            except Exception:
                pass

            async with SessionLocal() as session:
                order = await session.get(TelegramOrder, order_id)
                if not order:
                    return

                if order.status == "sent":
                    try:
                        await client.post(
                            f"{base_url}/answerCallbackQuery",
                            json={"callback_query_id": cb_id, "text": "Отклик уже был отправлен ранее!"},
                        )
                    except Exception:
                        pass
                    return

                from app.services.telegram_service import generate_ai_response, telegram_manager

                pitch_text = order.response_text
                if not pitch_text:
                    pitch_text = await generate_ai_response(order.raw_text, category=order.category)
                    order.response_text = pitch_text
                    await session.commit()

                recipient = order.author_username or order.chat_id
                logger.info("Bot runner: Auto-reply triggered for order %s to %s", order.id, recipient)
                result = await telegram_manager.send_direct_message(recipient, pitch_text)

                if result.success:
                    order.status = "sent"
                    order.responded_at = utcnow()
                    await session.commit()

                    now_msk = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                    clean_recip = (order.author_username or order.chat_id or "").lstrip("@")
                    success_html = (
                        "✅ <b>АВТООТКЛИК УСПЕШНО ОТПРАВЛЕН С ВАШЕГО АККАУНТА!</b>\n\n"
                        f"📤 <b>Получатель:</b> <code>@{clean_recip}</code>\n"
                        f"⏱ <b>Время:</b> {now_msk}\n"
                        f"📌 <b>Заказ:</b> {html.escape(order.summary or order.raw_text[:120])}\n\n"
                        "💬 <b>Отправленный текст:</b>\n"
                        f"<blockquote>{html.escape(pitch_text)}</blockquote>"
                    )

                    keyboard: list[list[dict[str, Any]]] = []
                    if clean_recip:
                        keyboard.append([
                            {
                                "text": "💬 Открыть диалог в ЛС",
                                "url": f"https://t.me/{clean_recip}",
                            }
                        ])
                    keyboard.append([
                        {
                            "text": "📱 Открыть в Mini App",
                            "web_app": {"url": WEB_APP_URL},
                        }
                    ])

                    await client.post(
                        f"{base_url}/editMessageText",
                        json={
                            "chat_id": chat_id,
                            "message_id": message_id,
                            "text": success_html,
                            "parse_mode": "HTML",
                            "reply_markup": {"inline_keyboard": keyboard},
                            "disable_web_page_preview": True,
                        },
                    )
                else:
                    err_msg = html.escape(result.error or "Неизвестная ошибка")
                    clean_recip = (order.author_username or order.chat_id or "").lstrip("@")
                    fail_html = (
                        "⚠️ <b>НЕ УДАЛОСЬ ОТПРАВИТЬ АВТООТКЛИК С АККАУНТА</b>\n\n"
                        f"<b>Причина:</b> <i>{err_msg}</i>\n\n"
                        "💡 <b>Решение:</b>\n"
                        "• Убедитесь, что Telegram-аккаунт подключен во вкладке <b>«Прогрев»</b>\n"
                        "• Или перейдите напрямую в ЛС к клиенту по кнопке ниже и отправьте скопированный текст:\n\n"
                        f"<blockquote>{html.escape(pitch_text)}</blockquote>"
                    )

                    keyboard = [
                        [
                            {
                                "text": "💬 Перейти в ЛС и отправить вручную",
                                "url": f"https://t.me/{clean_recip}" if clean_recip else (order.source_url or "https://t.me"),
                            }
                        ],
                        [
                            {
                                "text": "📱 Открыть Mini App",
                                "web_app": {"url": WEB_APP_URL},
                            }
                        ],
                    ]

                    await client.post(
                        f"{base_url}/editMessageText",
                        json={
                            "chat_id": chat_id,
                            "message_id": message_id,
                            "text": fail_html,
                            "parse_mode": "HTML",
                            "reply_markup": {"inline_keyboard": keyboard},
                            "disable_web_page_preview": True,
                        },
                    )
            return

        # 3. Action: Skip Order (skip_order:<order_id>)
        if cb_data.startswith("skip_order:"):
            order_id = cb_data.split(":", 1)[1]
            try:
                await client.post(
                    f"{base_url}/answerCallbackQuery",
                    json={"callback_query_id": cb_id, "text": "Заказ пропущен"},
                )
            except Exception:
                pass

            async with SessionLocal() as session:
                order = await session.get(TelegramOrder, order_id)
                if order:
                    order.status = "skipped"
                    await session.commit()
                    text, markup = lead_notifier.format_order_card(order)
                    await client.post(
                        f"{base_url}/editMessageText",
                        json={
                            "chat_id": chat_id,
                            "message_id": message_id,
                            "text": text,
                            "parse_mode": "HTML",
                            "reply_markup": markup,
                            "disable_web_page_preview": True,
                        },
                    )
            return

        # Fallback default callback answer
        try:
            await client.post(f"{base_url}/answerCallbackQuery", json={"callback_query_id": cb_id})
        except Exception:
            pass

    async def _handle_test_lead_command(
        self, client: httpx.AsyncClient, base_url: str, chat_id: int
    ) -> None:
        """Create a realistic demo order and send interactive notification."""
        from datetime import timedelta
        from app.models import TelegramOrder
        from app.services.telegram_service import generate_ai_response

        sample_orders = [
            (
                "Нужен лендинг под ключ для студии автодетейлинга и оклейки авто пленкой. "
                "Дизайн, адаптивная верстка, калькулятор стоимости услуг, форма заявки в TG. "
                "Бюджет 45 000 руб. Писать в ЛС @detailing_pro_msk",
                "Лендинг для студии детейлинга",
                "45 000 ₽",
                "detailing_pro_msk",
                "Алексей Детейлинг",
                "@freelancetavern",
                "Freelance Tavern (Заказы)",
            ),
            (
                "Требуется разработка Telegram Mini App магазина доставки суши и роллов. "
                "Корзина, выбор адреса, онлайн-оплата и уведомления курьеру. Бюджет 80 000 руб. Отклики в лс @tokyo_sushi_owner",
                "Telegram Mini App доставки суши",
                "80 000 ₽",
                "tokyo_sushi_owner",
                "Tokyo Sushi Owner",
                "@it_freelance_chat",
                "IT Freelance Чат & Биржа",
            ),
        ]

        text, summary, budget, username, name, channel_id, channel_title = random.choice(sample_orders)
        ai_resp = await generate_ai_response(text)

        async with SessionLocal() as session:
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
                response_text=ai_resp,
                scheduled_for=utcnow() + timedelta(minutes=10),
                status="pending",
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            card_text, markup = lead_notifier.format_order_card(order)
            await client.post(
                f"{base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": card_text,
                    "parse_mode": "HTML",
                    "reply_markup": markup,
                    "disable_web_page_preview": True,
                },
            )

    async def _poll_loop(self) -> None:
        token = settings.telegram_bot_token
        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0
        logger.info(
            "Starting Telegram Bot long-polling loop for @%s",
            getattr(settings, "telegram_bot_username", "bot"),
        )

        async with httpx.AsyncClient(timeout=35) as client:
            while self._running:
                try:
                    resp = await client.get(
                        f"{base_url}/getUpdates",
                        params={"offset": offset, "timeout": 20},
                    )
                    if resp.status_code != 200:
                        await asyncio.sleep(3)
                        continue

                    data = resp.json()
                    updates = data.get("result", [])
                    for update in updates:
                        update_id = update.get("update_id", 0)
                        offset = max(offset, update_id + 1)

                        # Handle Callback Queries (Button clicks)
                        callback_query = update.get("callback_query")
                        if callback_query:
                            await self._handle_callback_query(client, base_url, callback_query)
                            continue

                        # Handle Incoming Messages
                        msg = update.get("message")
                        if not msg:
                            continue

                        chat_id = msg.get("chat", {}).get("id")
                        if not chat_id:
                            continue

                        # Automatically register this chat as a lead alert subscriber
                        await lead_notifier.add_subscriber(chat_id)
                        settings.telegram_owner_id = chat_id

                        text = (msg.get("text") or "").strip()

                        if text.startswith("/test_lead") or text.startswith("/demo_lead"):
                            await self._handle_test_lead_command(client, base_url, chat_id)

                        elif text.startswith("/settings") or text.startswith("/radar") or text.startswith("/autopost"):
                            await client.post(
                                f"{base_url}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": (
                                        "⚙️ <b>Настройки модулей LeadRadar:</b>\n\n"
                                        "• <b>ТГ Радар заказов:</b> автоотклик, рабочие часы (МСК), ключевые и стоп-слова\n"
                                        "• <b>Автопосев визиток:</b> автопостинг промо, интервалы ротации, портфолио и фото-скриншоты\n"
                                        "• <b>Уведомления:</b> данный чат подписан на моментальные алерты о заказах\n\n"
                                        "👇 Откройте панель настроек в приложении:"
                                    ),
                                    "parse_mode": "HTML",
                                    "reply_markup": {
                                        "inline_keyboard": [
                                            [
                                                {
                                                    "text": "⚙️ Открыть настройки в Mini App",
                                                    "web_app": {"url": WEB_APP_URL},
                                                }
                                            ],
                                            [
                                                {
                                                    "text": "🧪 Протестировать карточку лида",
                                                    "callback_data": "cmd:test_lead",
                                                }
                                            ],
                                        ]
                                    },
                                },
                            )
                        elif text.startswith("/start"):
                            await client.post(
                                f"{base_url}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": WELCOME_TEXT,
                                    "parse_mode": "HTML",
                                    "reply_markup": {
                                        "inline_keyboard": [
                                            [
                                                {
                                                    "text": "🚀 Открыть LeadRadar Mini App",
                                                    "web_app": {"url": WEB_APP_URL},
                                                }
                                            ],
                                            [
                                                {
                                                    "text": "🧪 Тестовый заказ с кнопками",
                                                    "callback_data": "cmd:test_lead",
                                                }
                                            ],
                                            [
                                                {
                                                    "text": "💼 Портфолио Murasaki",
                                                    "url": "https://murasaki-portfolio.vercel.app/",
                                                }
                                            ],
                                        ]
                                    },
                                },
                            )
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("Bot poll error (retrying): %s", exc)
                    await asyncio.sleep(2)


bot_runner = TelegramBotRunner()
