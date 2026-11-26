from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import ParseJob
from app.providers import ProviderError, get_provider
from app.schemas import (
    LeadOut,
    ParseDirectUrlOut,
    ParseDirectUrlRequest,
    ParseJobOut,
    ParseRequest,
)
from app.services.billing import check_and_spend, get_or_create_user
from app.services.jobs import dispatch_parse_job, save_places

router = APIRouter(tags=["parsing"])


@router.post("/parse", response_model=ParseJobOut, status_code=status.HTTP_202_ACCEPTED)
async def start_parse(
    payload: ParseRequest,
    session: AsyncSession = Depends(get_session),
) -> ParseJobOut:
    try:
        get_provider(payload.source)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    params = payload.model_dump()
    params["limit"] = min(payload.limit, settings.max_parse_limit)

    # Calculate parsing cost (demo is free)
    if payload.source != "demo":
        user = await get_or_create_user(session)
        credits_cost = max(2, int((params["limit"] / 50.0) * settings.credits_per_parse_50))
        if payload.enrich:
            credits_cost += 1
        await check_and_spend(
            session=session,
            user_id=user.id,
            amount=credits_cost,
            module_name="parse_leads",
            description=f"Парсинг {params['limit']} лидов ({payload.city})",
        )

    job = ParseJob(source=payload.source, status="queued", params=params)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    dispatch_parse_job(job.id)
    return ParseJobOut.model_validate(job)


@router.post("/parse/url", response_model=ParseDirectUrlOut)
async def parse_direct_url(
    payload: ParseDirectUrlRequest,
    session: AsyncSession = Depends(get_session),
) -> ParseDirectUrlOut:
    """Parse a single organization from a direct Yandex Maps or 2GIS URL and optionally create a demo."""
    from app.providers.direct_url import parse_direct_org_url
    from app.services.demos import create_demo, demo_out, public_demo_url

    try:
        place = await parse_direct_org_url(payload.url, fallback_city=(payload.city or "").strip())
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга ссылки: {exc}") from exc

    created_count, _updated_count, saved_leads = await save_places(
        session, [place], place.city or payload.city or "Россия"
    )
    if not saved_leads:
        raise HTTPException(status_code=500, detail="Не удалось сохранить организацию в базу")

    lead = saved_leads[0]
    await session.refresh(lead)

    demo_result = None
    if payload.create_demo:
        demo = await create_demo(session, lead)
        demo_result = demo_out(demo)
        await session.refresh(lead)

    lead_out = LeadOut.model_validate(lead)
    if demo_result is not None:
        lead_out.demo_url = demo_result.public_url or public_demo_url(demo_result.slug or demo_result.id)

    return ParseDirectUrlOut(
        lead=lead_out,
        created=created_count > 0,
        demo=demo_result,
    )


@router.get("/jobs/{job_id}", response_model=ParseJobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> ParseJobOut:
    job = await session.get(ParseJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return ParseJobOut.model_validate(job)


@router.get("/jobs", response_model=list[ParseJobOut])
async def list_jobs(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[ParseJobOut]:
    jobs = await session.scalars(
        select(ParseJob).order_by(ParseJob.created_at.desc()).limit(limit)
    )
    return [ParseJobOut.model_validate(job) for job in jobs]
