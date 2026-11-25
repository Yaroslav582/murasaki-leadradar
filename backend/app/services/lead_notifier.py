"""
Lead & Order Notification Service (lead_notifier.py)
----------------------------------------------------
Sends real-time alerts about newly discovered leads & freelance orders directly
to the user's Telegram chat via @murasaki_radar_1438_bot with interactive inline buttons:
  • ⚡️ Сгенерировать AI-отклик (генерирует персональный оффер и обновляет сообщение)
  • 💬 Перейти в ЛС (прямой переход к переписке с клиентом в Telegram)
  • 🚀 Автоотклик с аккаунта (отправка сообщения клиенту от лица юзербота владельца)
  • ❌ Пропустить (пометка заказа как пропущенного)
  • 📱 Открыть в Mini App (бесшовный запуск приложения)
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting, Lead, TelegramOrder, utcnow

logger = logging.getLogger(__name__)

WEB_APP_URL = getattr(settings, "web_app_url", "https://frontend-mocha-three-gfa8fzsldf.vercel.app")


def clean_handle(raw: str | None) -> str:
    if not raw:
        return ""
    val = raw.strip()
    if val.startswith("https://t.me/"):
        val = val[13:]
    elif val.startswith("t.me/"):
        val = val[5:]
    return val.lstrip("@").strip()


class LeadNotifier:
    """Dispatches interactive lead & order notifications via Telegram Bot."""

    def __init__(self) -> None:
        self.bot_token = getattr(settings, "telegram_bot_token", None)

    def _get_api_url(self, method: str) -> str:
        token = self.bot_token or settings.telegram_bot_token
        return f"https://api.telegram.org/bot{token}/{method}"

    async def get_recipients(self) -> list[int]:
        """Fetch all subscribed chat IDs (owner ID + any chats that clicked /start)."""
        chat_ids: set[int] = set()

        # 1. Configured owner ID
        if settings.telegram_owner_id:
            try:
                chat_ids.add(int(settings.telegram_owner_id))
            except (ValueError, TypeError):
                pass

        # 2. Database subscribers list from app_settings
        try:
            async with SessionLocal() as db_session:
                st = await db_session.get(AppSetting, "telegram_bot_subscribers")
                if st and st.value:
                    subs = st.value.get("chat_ids", [])
                    for s in subs:
                        try:
                            chat_ids.add(int(s))
                        except (ValueError, TypeError):
                            pass
        except Exception as exc:
            logger.debug("Could not query telegram_bot_subscribers from DB: %s", exc)

        return list(chat_ids)

    async def add_subscriber(self, chat_id: int) -> None:
        """Register a chat ID to receive new lead notifications."""
        try:
            async with SessionLocal() as db_session:
                st = await db_session.get(AppSetting, "telegram_bot_subscribers")
                current_ids: list[int] = []
                if st and st.value:
                    current_ids = [int(x) for x in st.value.get("chat_ids", [])]

                if chat_id not in current_ids:
                    current_ids.append(chat_id)
                    val = {"chat_ids": current_ids, "updated_at": utcnow().isoformat()}
                    if st:
                        st.value = val
                    else:
                        st = AppSetting(key="telegram_bot_subscribers", value=val)
                        db_session.add(st)
                    await db_session.commit()
                    logger.info("Added %d to telegram_bot_subscribers", chat_id)
        except Exception as exc:
            logger.warning("Failed saving telegram_bot_subscribers: %s", exc)

    def format_order_card(
        self, order: TelegramOrder, is_sent: bool = False
    ) -> tuple[str, dict[str, Any]]:
        """Formats the HTML alert message and inline action buttons for a freelance order."""
        source_name = order.source.upper() if order.source else "TELEGRAM"
        chat_title = html.escape(order.chat_title or order.chat_id or "Фриланс чат")
        category = html.escape(order.category or "Веб-сайт")
        budget = html.escape(order.budget or "По договорённости")
        author_name = html.escape(order.author_name or "Заказчик")
        username = clean_handle(order.author_username)
        raw_text = html.escape(order.raw_text.strip() if order.raw_text else "")
        response_text = html.escape(order.response_text.strip() if order.response_text else "")

        author_display = author_name
        if username:
            author_display += f" (<code>@{username}</code>)"

        if is_sent or order.status == "sent":
            status_badge = "✅ <b>ОТКЛИК ОТПРАВЛЕН В ЛС</b>"
        elif order.status == "skipped":
            status_badge = "❌ <b>ЗАКАЗ ПРОПУЩЕН</b>"
        else:
            status_badge = "🔥 <b>НОВЫЙ ЗАКАЗ НА РАДАРЕ</b>"

        card_lines = [
            f"{status_badge}",
            "",
            f"📌 <b>Категория:</b> {category}",
            f"💰 <b>Бюджет:</b> <code>{budget}</code>",
            f"🌐 <b>Источник:</b> {source_name} ({chat_title})",
            f"👤 <b>Заказчик:</b> {author_display}",
            "",
            "📝 <b>Задача заказчика:</b>",
            f"<blockquote>{raw_text[:750]}</blockquote>",
        ]

        if response_text:
            card_lines.extend([
                "",
                "💡 <b>Подготовленный AI-отклик:</b>",
                f"<blockquote>{response_text[:750]}</blockquote>",
            ])
        else:
            card_lines.extend([
                "",
                "💡 <i>AI-отклик ещё не сгенерирован. Нажмите кнопку ниже для генерации.</i>",
            ])

        message_html = "\n".join(card_lines)

        # Build inline keyboard
        keyboard: list[list[dict[str, Any]]] = []

        if order.status not in ("sent", "skipped") and not is_sent:
            # Row 1: Generation & Direct PM link
            row1: list[dict[str, Any]] = []
            gen_label = "🔄 Перегенерировать" if response_text else "⚡️ Сгенерировать AI-отклик"
            row1.append({
                "text": gen_label,
                "callback_data": f"gen_offer:{order.id}",
            })

            if username:
                row1.append({
                    "text": "💬 Перейти в ЛС",
                    "url": f"https://t.me/{username}",
                })
            elif order.source_url:
                row1.append({
                    "text": "🔗 Открыть заказ",
                    "url": order.source_url,
                })
            elif order.chat_id and str(order.chat_id).startswith("@"):
                row1.append({
                    "text": "💬 Перейти в чат",
                    "url": f"https://t.me/{order.chat_id.lstrip('@')}",
                })
            keyboard.append(row1)

            # Row 2: One-click Auto-reply from User's Account OR Skip
            row2: list[dict[str, Any]] = []
            if username or (order.chat_id and str(order.chat_id).startswith("@")) or order.source == "telegram":
                row2.append({
                    "text": "🚀 Автоотклик с аккаунта",
                    "callback_data": f"auto_reply:{order.id}",
                })
            row2.append({
                "text": "❌ Пропустить",
                "callback_data": f"skip_order:{order.id}",
            })
            keyboard.append(row2)

        else:
            # Order is already processed (sent or skipped)
            row_done: list[dict[str, Any]] = []
            if username:
                row_done.append({
                    "text": "💬 Открыть диалог в ЛС",
                    "url": f"https://t.me/{username}",
                })
            elif order.source_url:
                row_done.append({
                    "text": "🔗 Ссылка на биржу",
                    "url": order.source_url,
                })
            if row_done:
                keyboard.append(row_done)

        # Bottom row: Mini App link
        keyboard.append([
            {
                "text": "📱 Открыть заказ в Mini App",
                "web_app": {"url": WEB_APP_URL},
            }
        ])

        reply_markup = {"inline_keyboard": keyboard}
        return message_html, reply_markup

    def format_lead_card(self, lead: Lead) -> tuple[str, dict[str, Any]]:
        """Formats the HTML alert for a parsed business lead."""
        name = html.escape(lead.name or "Новая компания")
        category = html.escape(lead.category or "Услуги")
        city = html.escape(lead.city or "РФ")
        phone = html.escape(lead.phone or "Не указан")
        site = html.escape(lead.website_url or "Без сайта (потенциальный клиент на сайт!)")
        rating = f"{lead.rating} ⭐" if lead.rating else "Нет отзывов"

        lines = [
            "🏢 <b>НОВЫЙ ЛИД КОМПАНИИ В БАЗЕ</b>",
            "",
            f"📌 <b>Организация:</b> {name}",
            f"📍 <b>Сфера и город:</b> {category} ({city})",
            f"📞 <b>Телефон:</b> <code>{phone}</code>",
            f"🌐 <b>Сайт:</b> {site}",
            f"📊 <b>Рейтинг:</b> {rating}",
        ]

        if lead.address:
            lines.append(f"🏠 <b>Адрес:</b> {html.escape(lead.address)}")

        message_html = "\n".join(lines)

        keyboard: list[list[dict[str, Any]]] = []
        row1: list[dict[str, Any]] = [
            {
                "text": "⚡️ Сгенерировать оффер",
                "callback_data": f"gen_lead:{lead.id}",
            }
        ]
        if lead.phone:
            clean_digits = "".join(ch for ch in lead.phone if ch.isdigit())
            row1.append({
                "text": "💬 Написать в Telegram",
                "url": f"https://t.me/+{clean_digits}",
            })
        keyboard.append(row1)

        keyboard.append([
            {
                "text": "📱 Открыть лид в Mini App",
                "web_app": {"url": f"{WEB_APP_URL}?lead_id={lead.id}"},
            }
        ])

        return message_html, {"inline_keyboard": keyboard}

    async def notify_new_order(self, order: TelegramOrder) -> int:
        """Broadcasts a new order alert to all configured Telegram recipients."""
        recipients = await self.get_recipients()
        if not recipients:
            logger.info("No Telegram notification recipients configured. Skipping alert.")
            return 0

        text, markup = self.format_order_card(order)
        url = self._get_api_url("sendMessage")
        sent_count = 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            for chat_id in recipients:
                try:
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": markup,
                        "disable_web_page_preview": True,
                    }
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        sent_count += 1
                        logger.info("Delivered lead alert for order %s to chat %d", order.id, chat_id)
                    else:
                        logger.warning(
                            "Failed sending lead alert to %d (HTTP %d): %s",
                            chat_id,
                            resp.status_code,
                            resp.text[:150],
                        )
                except Exception as exc:
                    logger.warning("Error dispatching alert to chat %d: %s", chat_id, exc)

        return sent_count

    async def notify_new_lead(self, lead: Lead) -> int:
        """Broadcasts a new business lead alert to all configured Telegram recipients."""
        recipients = await self.get_recipients()
        if not recipients:
            return 0

        text, markup = self.format_lead_card(lead)
        url = self._get_api_url("sendMessage")
        sent_count = 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            for chat_id in recipients:
                try:
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": markup,
                        "disable_web_page_preview": True,
                    }
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        sent_count += 1
                except Exception as exc:
                    logger.warning("Error dispatching lead alert to %d: %s", chat_id, exc)

        return sent_count

    async def notify_demo_viewed(
        self,
        lead_name: str,
        demo_id: str,
        views_count: int,
        demo_url: str = "",
        lead_id: str | None = None,
    ) -> int:
        """Alerts the owner in Telegram when a prospect opens their generated demo site."""
        recipients = await self.get_recipients()
        if not recipients:
            return 0

        safe_name = html.escape(lead_name or "Клиент")
        lines = [
            "🔥 <b>Клиент открыл демо-сайт!</b>",
            f"🏢 <b>Компания:</b> {safe_name}",
            f"👀 <b>Просмотров:</b> {views_count}",
        ]
        if demo_url:
            lines.append(f"🔗 <a href=\"{html.escape(demo_url)}\">Открыть демо</a>")
        lines.append("\n<i>Самое время написать ему в диалоге, пока он изучает сайт!</i>")
        text = "\n".join(lines)

        url = self._get_api_url("sendMessage")
        sent_count = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for chat_id in recipients:
                try:
                    resp = await client.post(
                        url,
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True,
                        },
                    )
                    if resp.status_code == 200:
                        sent_count += 1
                except Exception as exc:
                    logger.warning("Error dispatching demo view alert to %d: %s", chat_id, exc)
        return sent_count


lead_notifier = LeadNotifier()
