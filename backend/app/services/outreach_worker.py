from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import or_, select
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

                # 0. Anti-duplicate check: don't message the same lead or username twice
                dup_stmt = select(Dialog.id).where(Dialog.lead_id == lead.id)
                if (await session.execute(dup_stmt)).first():
                    logger.info("Skipping duplicate outreach for lead %s (dialog exists)", lead.name)
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

                        # Check if we have a generated mobile screenshot for this lead's demo
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

                account = await account_pool.get_account_by_id(session, dialog.account_id) if hasattr(account_pool, "get_account_by_id") else None
                if account is None:
                    from app.models import TgAccount
                    account = await session.get(TgAccount, dialog.account_id)
                if not account or account.status != "active":
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
