from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.billing import get_or_create_user
from app.services.outreach_worker import outreach_worker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Outreach"])


class OutreachStartRequest(BaseModel):
    lead_ids: list[str]
    template: str = (
        "Здравствуйте! Обратили внимание на компанию {company_name} в {city}. "
        "Мы специализируемся на разработке конверсионных сайтов и лендингов для вашей сферы. "
        "Подготовили интерактивное демо решения — показать вам?"
    )
    delay_min: int = 180
    delay_max: int = 600


@router.post("/outreach/start")
async def start_outreach(
    payload: OutreachStartRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if not payload.lead_ids:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одного лида для рассылки")

    user = await get_or_create_user(session)
    campaign_id = await outreach_worker.start_outreach_campaign(
        user_id=user.id,
        lead_ids=payload.lead_ids,
        template=payload.template,
        delay_min=payload.delay_min,
        delay_max=payload.delay_max,
    )
    return {
        "status": "started",
        "campaign_id": campaign_id,
        "leads_count": len(payload.lead_ids),
    }


@router.get("/outreach/status")
async def get_outreach_status() -> dict[str, Any]:
    auto_status = await outreach_worker.get_autonomous_status()
    return {**outreach_worker.stats, "autonomous": auto_status}


class OutreachToggleRequest(BaseModel):
    enabled: bool


@router.post("/outreach/toggle")
async def toggle_autonomous_outreach(payload: OutreachToggleRequest) -> dict[str, Any]:
    return await outreach_worker.set_autonomous_enabled(payload.enabled)


@router.post("/outreach/step")
async def trigger_autonomous_step() -> dict[str, Any]:
    outcome = await outreach_worker.run_autonomous_step()
    status_info = await outreach_worker.get_autonomous_status()
    return {"outcome": outcome, **status_info}
