from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import ParseJob
from app.providers import ProviderError, get_provider
from app.schemas import ParseJobOut, ParseRequest
from app.services.billing import check_and_spend, get_or_create_user
from app.services.jobs import dispatch_parse_job

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
