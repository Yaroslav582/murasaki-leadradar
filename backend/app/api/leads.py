from __future__ import annotations

import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.filters import LeadFilters, apply_lead_filters, lead_filters
from app.config import settings
from app.db import get_session
from app.models import DemoSite, Lead, utcnow
from app.schemas import (
    BulkStatusUpdate,
    CustomDemoCreate,
    DemoGenerateRequest,
    DemoOut,
    LeadOut,
    LeadsPage,
    LeadUpdate,
    OutreachOut,
)
from app.services.billing import check_and_spend, get_or_create_user
from app.services.demos import create_demo, demo_out, lead_to_dict, public_demo_url
from app.services.enrichment import enrich_leads
from app.services.landing import build_outreach, generate_outreach_message

logger = logging.getLogger(__name__)

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
    items: list[LeadOut] = []
    for row in rows:
        try:
            items.append(LeadOut.model_validate(row))
        except Exception as exc:
            logger.warning("Error validating lead %s: %s", getattr(row, "id", None), exc)
            try:
                items.append(
                    LeadOut(
                        id=str(getattr(row, "id", "")),
                        name=str(getattr(row, "name", "") or "Без названия"),
                        category=str(getattr(row, "category", "") or ""),
                        city=str(getattr(row, "city", "") or ""),
                        address=str(getattr(row, "address", "") or ""),
                        phone=getattr(row, "phone", None),
                        website_url=getattr(row, "website_url", None),
                        has_website=bool(getattr(row, "has_website", False)),
                        rating=getattr(row, "rating", None),
                        reviews_count=getattr(row, "reviews_count", 0) or 0,
                        social_links=getattr(row, "social_links", {}) or {},
                        emails=getattr(row, "emails", []) or [],
                        opening_hours=getattr(row, "opening_hours", []) or [],
                        photos=getattr(row, "photos", []) or [],
                        logo_url=getattr(row, "logo_url", None),
                        demo_id=getattr(row, "demo_id", None),
                        status=getattr(row, "status", "new") or "new",
                        source=getattr(row, "source", "demo") or "demo",
                    )
                )
            except Exception as inner_exc:
                logger.error("Failed creating fallback LeadOut for %s: %s", getattr(row, "id", None), inner_exc)
    pages = (total + page_size - 1) // page_size if page_size else 1
    return LeadsPage(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: str, session: AsyncSession = Depends(get_session)) -> LeadOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")
    try:
        return LeadOut.model_validate(lead)
    except Exception as exc:
        logger.warning("Error validating lead %s: %s", lead_id, exc)
        return LeadOut(
            id=str(lead.id),
            name=str(lead.name or "Без названия"),
            category=str(lead.category or ""),
            city=str(lead.city or ""),
            address=str(lead.address or ""),
            phone=lead.phone,
            website_url=lead.website_url,
            has_website=bool(lead.has_website),
            rating=lead.rating,
            reviews_count=lead.reviews_count or 0,
            social_links=lead.social_links or {},
            emails=lead.emails or [],
            opening_hours=lead.opening_hours or [],
            photos=getattr(lead, "photos", []) or [],
            logo_url=getattr(lead, "logo_url", None),
            demo_id=lead.demo_id,
            status=lead.status or "new",
            source=lead.source or "demo",
        )


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
    payload: DemoGenerateRequest | None = None,
    style: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")

    chosen_style = (payload.style if payload and payload.style else None) or style

    # 1. Pre-check credits balance before running generation
    user = await get_or_create_user(session)
    if user.credits_balance < settings.credits_per_demo:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Недостаточно кредитов ({user.credits_balance} cr). Требуется {settings.credits_per_demo} cr.",
        )

    # 2. Transactional safety: generate demo first
    try:
        demo = await create_demo(session, lead, style=chosen_style)
    except Exception as exc:
        logger.error("Failed to generate demo for lead %s: %s", lead_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации демо-сайта: {exc}. Кредиты не списаны.",
        )

    # 3. Spend credits strictly AFTER successful creation and persistence
    try:
        await check_and_spend(
            session=session,
            user_id=user.id,
            amount=settings.credits_per_demo,
            module_name="ai_demo",
            description=f"Генерация AI-демо сайта для {lead.name}",
        )
        await session.commit()
    except Exception as spend_err:
        logger.warning("Credit deduction notice for user %s: %s", user.id, spend_err)

    return demo_out(demo)


@router.post("/{lead_id}/custom-demo", response_model=DemoOut)
async def save_custom_demo(
    lead_id: str,
    payload: CustomDemoCreate,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    """Saves manually generated or prompt-pasted HTML demo for a lead for 0 credits."""
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Лид не найден")

    # Clean incoming custom HTML from markdown fences and surrounding chat preambles
    clean_html = (payload.html or "").strip()
    clean_html = re.sub(r"^```(?:html)?\s*", "", clean_html, flags=re.I)
    clean_html = re.sub(r"\s*```$", "", clean_html)
    start_tag = clean_html.lower().find("<!doctype html")
    if start_tag == -1:
        start_tag = clean_html.lower().find("<html")
    if start_tag != -1:
        end_tag = clean_html.lower().rfind("</html>")
        if end_tag != -1:
            clean_html = clean_html[start_tag : end_tag + len("</html>")]
        else:
            clean_html = clean_html[start_tag:] + "\n</html>"

    # Enforce Murasaki LeadRadar floating badge before </body>
    from app.services.landing import inject_murasaki_badge
    final_html = inject_murasaki_badge(clean_html, lead.name or "бизнеса")

    demo = None
    if lead.demo_id:
        demo = await session.get(DemoSite, lead.demo_id)

    if demo:
        demo.html = final_html
        if payload.message:
            demo.message = payload.message
        if payload.title:
            demo.title = payload.title
        demo.published = True
        demo.updated_at = utcnow()
    else:
        demo = DemoSite(
            lead_id=lead.id,
            title=payload.title or f"Демо для {lead.name}",
            html=final_html,
            message=payload.message or "",
            published=True,
        )
        session.add(demo)
        await session.flush()
        lead.demo_id = demo.id
        session.add(lead)

    await session.commit()
    await session.refresh(demo)
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
