from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Dialog, Lead, Message, TgAccount, utcnow
from app.services.account_pool import account_pool
from app.services.billing import check_and_spend
from app.services.ai_router import ask_ai

logger = logging.getLogger(__name__)


class OutreachWorker:
    """Orchestrates soft lead outreach via warm Telegram account pool with AI personalization."""

    def __init__(self) -> None:
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._stats: dict[str, Any] = {
            "total_sent": 0,
            "total_failed": 0,
            "is_running": False,
            "current_lead": None,
        }

    @property
    def stats(self) -> dict[str, Any]:
        return self._stats

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

        # Fallback substitution
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

                # Target identifier: telegram link or phone
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

                # 1. Check and spend 1 credit for outreach message
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

                # 2. Get available account from pool
                account = await account_pool.get_available_account(session, user_id)
                if not account:
                    logger.warning("No available TG accounts in pool for outreach")
                    failed += 1
                    break

                # 3. Personalize message via LLM
                message_text = await self.personalize_message(lead, template)

                # 4. Send via Telethon
                success = False
                try:
                    client = await account_pool.get_client_for_account(account)
                    await client.connect()

                    if await client.is_user_authorized():
                        peer_entity = await client.get_entity(target_peer)
                        sent_msg = await client.send_message(peer_entity, message_text, parse_mode="md", link_preview=False)

                        # Create or update Dialog + Message in Unified Inbox
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

                        # Update lead status
                        lead.status = "sent"
                        await account_pool.record_action(session, account.id)
                        await session.commit()

                        sent += 1
                        self._stats["total_sent"] += 1
                        success = True
                        logger.info("Sent outreach to %s via account %s", lead.name, account.phone)
                    else:
                        account.status = "banned"
                        await session.commit()
                except Exception as err:
                    logger.warning("Outreach send failed for %s: %s", lead.name, err)
                    await account_pool.rotate_on_error(session, account.id, err)
                    failed += 1
                    self._stats["total_failed"] += 1

                # Random pause between 180 and 600 seconds
                delay = random.uniform(float(delay_min), float(delay_max))
                logger.info("Waiting %.1f seconds before next outreach...", delay)
                await asyncio.sleep(delay)

        self._stats["is_running"] = False
        self._stats["current_lead"] = None
        self._active_tasks.pop(campaign_id, None)
        logger.info("Campaign %s finished. Sent: %d, Failed: %d", campaign_id, sent, failed)


outreach_worker = OutreachWorker()
