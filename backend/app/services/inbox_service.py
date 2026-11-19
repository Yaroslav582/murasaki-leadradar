from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.models import Dialog, Lead, Message, TgAccount, User, utcnow
from app.services.account_pool import account_pool
from app.services.billing import check_and_spend
from app.services.ai_router import ask_ai

logger = logging.getLogger(__name__)

DEAL_TRIGGERS = [
    "цена", "стоимост", "сколько стоит", "прайс", "бюджет",
    "созвон", "созвониться", "встреч", "обсудить", "позвонить",
    "договор", "заказ", "купить", "готов работать", "бриф", "тз",
]


class InboxService:
    """Unified Inbox service coordinating cross-account dialogues and AI closing assistant."""

    def check_deal_signals(self, text: str) -> bool:
        """Analyzes text for commercial buying intent and deal closing signals."""
        lower = text.lower()
        return any(trigger in lower for trigger in DEAL_TRIGGERS)

    async def notify_owner_deal(
        self, dialog: Dialog, lead_name: str, client_message: str
    ) -> None:
        """Sends immediate Telegram push notification to bot owner when deal status is reached."""
        token = settings.telegram_bot_token
        owner_id = settings.telegram_owner_id
        if not token or not owner_id:
            logger.info("Bot notification skipped: no owner_id or bot_token configured")
            return

        text = (
            "🔥 **ГОРЯЧИЙ ЛИД / СДЕЛКА В MURASAKI LEADRADAR!**\n\n"
            f"👤 **Клиент:** {dialog.peer_name or dialog.peer_username or 'Неизвестно'}\n"
            f"🏢 **Компания:** {lead_name}\n"
            f"💬 **Сообщение клиента:**\n«{client_message}»\n\n"
            "👉 Откройте Mini App -> вкладка 'Диалоги' для продолжения общения."
        )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": owner_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
            logger.info("Sent deal push-notification to owner %s", owner_id)
        except Exception as e:
            logger.warning("Failed to send bot deal notification: %s", e)

    async def generate_ai_reply(
        self, session: AsyncSession, dialog_id: str
    ) -> dict[str, Any]:
        """Generates AI assistant reply to qualify lead and send portfolio."""
        dialog = await session.get(Dialog, dialog_id)
        if not dialog:
            raise ValueError("Диалог не найден")

        # Guard: Abort if auto-reply is disabled or dialog is in manual/deal mode
        if not dialog.ai_auto_reply_enabled or dialog.status in ("deal", "manual"):
            logger.info("generate_ai_reply aborted for dialog %s: disabled or manual/deal", dialog_id)
            return {"message_id": None, "text": "", "status": dialog.status, "is_deal": False}

        # Guard: Never reply to bots
        peer_u = (dialog.peer_username or "").lower()
        peer_n = (dialog.peer_name or "").lower()
        if peer_u.endswith("bot") or "bot" in peer_n or peer_u in ("spambot", "telegram"):
            logger.info("generate_ai_reply aborted for dialog %s: peer is a bot", dialog_id)
            dialog.ai_auto_reply_enabled = False
            await session.commit()
            return {"message_id": None, "text": "", "status": dialog.status, "is_deal": False}

        # Fetch lead details if available
        lead_name = "бизнес"
        lead_site_status = "нет сайта"
        if dialog.lead_id:
            lead = await session.get(Lead, dialog.lead_id)
            if lead:
                lead_name = lead.name or lead_name
                lead_site_status = "есть сайт" if lead.has_website else "нет сайта"

        # Fetch last 8 messages
        msg_stmt = (
            select(Message)
            .where(Message.dialog_id == dialog_id)
            .order_by(Message.created_at.desc())
            .limit(8)
        )
        res = await session.execute(msg_stmt)
        messages = list(reversed(res.scalars().all()))

        # Circuit breaker: count consecutive outbound AI messages
        consecutive_ai = 0
        for m in reversed(messages):
            if m.direction == "out" and m.is_ai_generated:
                consecutive_ai += 1
            else:
                break

        if consecutive_ai >= 2:
            logger.warning(
                "Circuit breaker: dialog %s already sent %d consecutive AI messages without manual reply. Switching to manual.",
                dialog_id,
                consecutive_ai,
            )
            dialog.ai_auto_reply_enabled = False
            dialog.status = "manual"
            await session.commit()
            return {
                "message_id": None,
                "text": "",
                "status": "manual",
                "is_deal": False,
            }

        history_lines = []
        for m in messages:
            prefix = "Менеджер" if m.direction == "out" else "Клиент"
            history_lines.append(f"{prefix}: {m.text}")

        history_text = "\n".join(history_lines) if history_lines else "Диалог только начат."

        portfolio_url = settings.telegram_portfolio_url or ""
        portfolio_ref = f"Портфолио: {portfolio_url}. " if portfolio_url else ""

        system_prompt = (
            "Ты — профессиональный менеджер по продажам веб-студии. "
            "Твоя задача — вежливо, уверенно и кратко квалифицировать клиента, "
            f"{portfolio_ref}"
            "и договориться о созвоне или демонстрации. "
            "Отвечай естественным языком, без канцеляризмов, максимум 2-3 коротких предложения."
        )

        user_prompt = (
            f"Контекст лида: компания '{lead_name}', статус: {lead_site_status}.\n"
            f"История диалога:\n{history_text}\n\n"
            "Напиши ответное сообщение от лица менеджера:"
        )

        try:
            ai_text = await ask_ai(user_prompt, system_prompt=system_prompt, task_type="smart", max_tokens=500, temperature=0.7)
            if not ai_text or len(ai_text.strip()) < 5:
                ai_text = "Здравствуйте! Ознакомились с вашей задачей. Подскажите, когда вам удобно обсудить детали проекта?"
        except Exception as e:
            logger.info("AI reply fallback to template: %s", e)
            ai_text = "Здравствуйте! С удовольствием поможем вам с реализацией проекта. Подскажите, когда вам удобно обсудить детали?"

        ai_text = ai_text.strip()

        # Check last client message for deal triggers
        last_client_msg = next((m.text for m in reversed(messages) if m.direction == "in"), "")
        is_deal = self.check_deal_signals(last_client_msg)
        if is_deal:
            dialog.status = "deal"
            if dialog.lead_id:
                lead = await session.get(Lead, dialog.lead_id)
                if lead:
                    lead.status = "deal"
            await self.notify_owner_deal(dialog, lead_name, last_client_msg)
        else:
            dialog.status = "ai_handling"

        # Save AI message
        new_msg = Message(
            dialog_id=dialog.id,
            account_id=dialog.account_id,
            direction="out",
            text=ai_text,
            is_ai_generated=True,
            created_at=utcnow(),
        )
        session.add(new_msg)
        dialog.last_message_at = utcnow()
        await session.commit()
        await session.refresh(new_msg)

        # Attempt sending to Telegram
        try:
            acc = await session.get(TgAccount, dialog.account_id)
            if acc:
                client = await account_pool.get_client_for_account(acc)
                await client.connect()
                if await client.is_user_authorized():
                    peer_val = dialog.peer_username or int(dialog.peer_id) if dialog.peer_id.isdigit() else dialog.peer_id
                    entity = await client.get_entity(peer_val)
                    sent = await client.send_message(entity, ai_text, parse_mode="md", link_preview=False)
                    new_msg.tg_message_id = getattr(sent, "id", None)
                    await session.commit()
        except Exception as send_err:
            logger.warning("Telegram direct send failed for dialog %s: %s", dialog.id, send_err)

        return {
            "message_id": new_msg.id,
            "text": ai_text,
            "status": dialog.status,
            "is_deal": is_deal,
        }

    async def handle_incoming_auto_reply(self, dialog_id: str, client_text: str) -> None:
        """Processes incoming client message and triggers AI reply if enabled for this chat."""
        async with SessionLocal() as session:
            dialog = await session.get(Dialog, dialog_id)
            if not dialog:
                return
            if not dialog.ai_auto_reply_enabled:
                logger.info("Auto-reply skipped for dialog %s: disabled", dialog_id)
                return
            if dialog.status in ("deal", "manual"):
                logger.info("Auto-reply skipped for dialog %s: status is %s", dialog_id, dialog.status)
                return
            if not dialog.lead_id:
                logger.info("Auto-reply skipped for dialog %s: not a registered outreach lead", dialog_id)
                dialog.ai_auto_reply_enabled = False
                await session.commit()
                return

            peer_u = (dialog.peer_username or "").lower()
            peer_n = (dialog.peer_name or "").lower()
            if peer_u.endswith("bot") or "bot" in peer_n or peer_u in ("spambot", "telegram"):
                logger.info("Auto-reply skipped for dialog %s: peer is a bot", dialog_id)
                dialog.ai_auto_reply_enabled = False
                await session.commit()
                return

            # Human delay before responding (2.0 - 4.0s)
            await asyncio.sleep(2.5)

            try:
                await self.generate_ai_reply(session, dialog_id)
                logger.info("Sent automated AI reply to dialog %s", dialog_id)
            except Exception as e:
                logger.error("Failed auto AI reply for dialog %s: %s", dialog_id, e)


inbox_service = InboxService()
