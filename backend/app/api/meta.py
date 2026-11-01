from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import DemoSite, Lead, ParseJob
from app.schemas import STATUS_LABELS, FacetValue, MetaOut, ParseJobOut, StatsOut

router = APIRouter(tags=["meta"])


async def _facets(session: AsyncSession, column) -> list[FacetValue]:
    rows = await session.execute(
        select(column, func.count(Lead.id))
        .where(column.isnot(None), column != "")
        .group_by(column)
        .order_by(func.count(Lead.id).desc())
    )
    return [FacetValue(value=str(value), count=count) for value, count in rows.all()]


@router.get("/meta", response_model=MetaOut)
async def get_meta(session: AsyncSession = Depends(get_session)) -> MetaOut:
    cities = await _facets(session, Lead.city)
    categories = await _facets(session, Lead.category)
    sources = await _facets(session, Lead.source)

    status_rows = await session.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    counts = {value: count for value, count in status_rows.all()}
    statuses = [
        FacetValue(value=key, count=counts.get(key, 0)) for key in STATUS_LABELS
    ]

    total = await session.scalar(select(func.count(Lead.id))) or 0
    no_website = await session.scalar(
        select(func.count(Lead.id)).where(Lead.has_website.is_(False))
    ) or 0
    with_social = await session.scalar(
        select(func.count(Lead.id)).where(func.length(cast(Lead.social_links, String)) > 2)
    ) or 0
    with_phone = await session.scalar(
        select(func.count(Lead.id)).where(Lead.phone.isnot(None), Lead.phone != "")
    ) or 0

    return MetaOut(
        cities=cities,
        categories=categories,
        statuses=statuses,
        sources=sources,
        total=total,
        no_website=no_website,
        with_social=with_social,
        with_phone=with_phone,
    )


@router.get("/stats", response_model=StatsOut)
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsOut:
    total = await session.scalar(select(func.count(Lead.id))) or 0
    no_website = await session.scalar(
        select(func.count(Lead.id)).where(Lead.has_website.is_(False))
    ) or 0
    with_social = await session.scalar(
        select(func.count(Lead.id)).where(func.length(cast(Lead.social_links, String)) > 2)
    ) or 0
    with_phone = await session.scalar(
        select(func.count(Lead.id)).where(Lead.phone.isnot(None), Lead.phone != "")
    ) or 0
    demos = await session.scalar(select(func.count(DemoSite.id))) or 0

    status_rows = await session.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    by_status = {key: 0 for key in STATUS_LABELS}
    for value, count in status_rows.all():
        by_status[value] = count

    latest_job = await session.scalar(
        select(ParseJob).order_by(ParseJob.created_at.desc()).limit(1)
    )

    return StatsOut(
        total=total,
        no_website=no_website,
        with_social=with_social,
        with_phone=with_phone,
        demos=demos,
        by_status=by_status,
        latest_job=ParseJobOut.model_validate(latest_job) if latest_job else None,
    )
