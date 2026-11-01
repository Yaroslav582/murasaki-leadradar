from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.filters import LeadFilters, apply_lead_filters, lead_filters
from app.db import get_session
from app.models import DemoSite, Lead
from app.schemas import (
    BulkStatusUpdate,
    DemoOut,
    LeadOut,
    LeadsPage,
    LeadUpdate,
    OutreachOut,
)
from app.services.demos import create_demo, demo_out, lead_to_dict, public_demo_url
from app.services.enrichment import enrich_leads
from app.services.landing import build_outreach, generate_outreach_message

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadsPage)
async def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    filters: LeadFilters = Depends(lead_filters),
    session: AsyncSession = Depends(get_session),
) -> LeadsPage:
    stmt = apply_lead_filters(select(Lead), filters)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
    items = [LeadOut.model_validate(row) for row in rows]
    pages = (total + page_size - 1) // page_size
    return LeadsPage(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: str, session: AsyncSession = Depends(get_session)) -> LeadOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")
    return LeadOut.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")

    if payload.status is not None:
        lead.status = payload.status
    if payload.notes is not None:
        lead.notes = payload.notes
    if payload.phone is not None:
        lead.phone = payload.phone.strip() or None
    if payload.website_url is not None:
        lead.website_url = payload.website_url.strip() or None
        lead.has_website = bool(lead.website_url)

    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return LeadOut.model_validate(lead)


@router.post("/bulk-status")
async def bulk_status(
    payload: BulkStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not payload.ids:
        return {"updated": 0}
    result = await session.execute(
        select(Lead).where(Lead.id.in_(payload.ids))
    )
    leads = result.scalars().all()
    for lead in leads:
        lead.status = payload.status
        session.add(lead)
    await session.commit()
    return {"updated": len(leads)}


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")
    await session.execute(delete(DemoSite).where(DemoSite.lead_id == lead_id))
    await session.delete(lead)
    await session.commit()
    return {"deleted": True}


@router.post("/{lead_id}/enrich", response_model=LeadOut)
async def enrich_single(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")
    if not lead.website_url:
        raise HTTPException(status_code=400, detail="У лида нет сайта для обогащения")

    await enrich_leads(session, [lead])
    await session.refresh(lead)
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/demo", response_model=DemoOut)
async def generate_demo(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")
    demo = await create_demo(session, lead)
    return demo_out(demo)


@router.get("/{lead_id}/demo", response_model=DemoOut)
async def get_demo(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")
    if not lead.demo_id:
        raise HTTPException(status_code=404, detail="Демо ещё не сгенерировано")
    demo = await session.get(DemoSite, lead.demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return demo_out(demo)


@router.post("/{lead_id}/message", response_model=OutreachOut)
async def generate_message(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> OutreachOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")

    message: str
    demo_url: str | None = None
    if lead.demo_id:
        demo = await session.get(DemoSite, lead.demo_id)
        if demo is not None:
            demo_url = public_demo_url(demo.id)
            message = demo.message or await generate_outreach_message(lead_to_dict(lead), demo_url)
            if not demo.message:
                demo.message = message
                session.add(demo)
                await session.commit()
            return OutreachOut(message=message, demo_url=demo_url)

    demo = await create_demo(session, lead)
    return OutreachOut(message=demo.message, demo_url=public_demo_url(demo.id))
