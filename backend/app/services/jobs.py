from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Lead, ParseJob
from app.providers import PlaceResult, ProviderError, get_provider
from app.schemas import ParseRequest
from app.services.enrichment import enrich_leads

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


async def save_places(
    session: AsyncSession,
    places: list[PlaceResult],
    city: str,
) -> tuple[int, int, list[Lead]]:
    created = 0
    updated = 0
    leads: list[Lead] = []

    for place in places:
        existing: Lead | None = None
        if place.source_id:
            existing = await session.scalar(
                select(Lead).where(
                    Lead.source == place.source,
                    Lead.source_id == place.source_id,
                )
            )
        if existing is None and place.phone:
            existing = await session.scalar(
                select(Lead).where(
                    Lead.source == place.source,
                    Lead.phone == place.phone,
                    Lead.name == place.name,
                )
            )

        if existing is not None:
            existing.name = place.name or existing.name
            existing.rating = place.rating or existing.rating
            existing.reviews_count = max(existing.reviews_count or 0, place.reviews_count)
            existing.website_url = place.website_url or existing.website_url
            existing.has_website = bool(existing.website_url)
            existing.phone = place.phone or existing.phone
            existing.address = place.address or existing.address
            existing.opening_hours = place.opening_hours or existing.opening_hours
            socials = dict(existing.social_links or {})
            socials.update(place.social_links)
            existing.social_links = socials
            session.add(existing)
            leads.append(existing)
            updated += 1
            continue

        lead = Lead(
            name=place.name,
            category=place.category or "Бизнес",
            city=place.city or city,
            address=place.address or "",
            phone=place.phone,
            website_url=place.website_url,
            has_website=bool(place.website_url),
            rating=place.rating,
            reviews_count=place.reviews_count or 0,
            latitude=place.latitude,
            longitude=place.longitude,
            social_links=place.social_links or {},
            emails=place.emails or [],
            opening_hours=place.opening_hours or [],
            price_level=place.price_level,
            source=place.source,
            source_id=place.source_id,
            status="new",
        )
        session.add(lead)
        leads.append(lead)
        created += 1

    await session.commit()
    return created, updated, leads


async def run_parse_job(job_id: str) -> None:
    async with SessionLocal() as session:
        job = await session.get(ParseJob, job_id)
        if job is None:
            return
        job.status = "running"
        await session.commit()

        try:
            params = ParseRequest.model_validate(job.params or {})
            provider = get_provider(job.source)
            places = await provider.search(
                city=params.city,
                categories=params.categories,
                query=params.query,
                limit=min(params.limit, settings.max_parse_limit),
                latitude=params.latitude,
                longitude=params.longitude,
                radius=params.radius,
            )

            if params.only_no_website:
                places = [place for place in places if not place.website_url]

            job.total_found = len(places)
            created, updated, leads = await save_places(session, places, params.city)
            job.total_saved = created + updated

            if params.enrich:
                enriched = await enrich_leads(
                    session, [lead for lead in leads if lead.website_url]
                )
                job.log = f"Обогащено контактов: {enriched}"

            job.status = "done"
        except ProviderError as exc:
            job.status = "failed"
            job.error = str(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Parse job %s failed", job_id)
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
        finally:
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            await session.commit()


async def fail_stale_jobs() -> int:
    """Mark in-process jobs interrupted by a server restart as failed."""
    async with SessionLocal() as session:
        result = await session.execute(
            update(ParseJob)
            .where(ParseJob.status.in_(("queued", "running")))
            .values(
                status="failed",
                error="Задача прервана перезапуском сервера. Запустите сбор повторно.",
                finished_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        return result.rowcount or 0


def dispatch_parse_job(job_id: str) -> None:
    if settings.use_celery:
        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.parse_job", args=[job_id])
        return

    task = asyncio.create_task(run_parse_job(job_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
