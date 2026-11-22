from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import DemoSite, Lead, new_id
from app.schemas import DemoOut
from app.services.landing import build_outreach, generate_landing_html, generate_outreach_message

logger = logging.getLogger(__name__)


def lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "name": lead.name,
        "category": lead.category,
        "city": lead.city,
        "address": lead.address,
        "phone": lead.phone,
        "website_url": lead.website_url,
        "has_website": lead.has_website,
        "rating": lead.rating,
        "reviews_count": lead.reviews_count,
        "social_links": lead.social_links or {},
        "opening_hours": lead.opening_hours or [],
        "latitude": lead.latitude,
        "longitude": lead.longitude,
        "photos": list(getattr(lead, "photos", []) or []),
        "logo_url": getattr(lead, "logo_url", None),
    }


def public_demo_url(demo_id: str) -> str:
    base = settings.public_base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/demo/{demo_id}"


def demo_out(demo: DemoSite) -> DemoOut:
    data = DemoOut.model_validate(demo)
    data.public_url = public_demo_url(demo.id)
    return data


async def create_demo(session: AsyncSession, lead: Lead) -> DemoSite:
    # Auto-fetch TG photos if missing and TG channel exists
    cur_photos = list(getattr(lead, "photos", []) or [])
    logo = getattr(lead, "logo_url", None)
    socials = getattr(lead, "social_links", {}) or {}
    if (not cur_photos or not logo) and isinstance(socials, dict):
        tg_url = socials.get("telegram")
        if tg_url:
            try:
                from app.services.telegram_channel_scraper import scrape_telegram_channel
                tg_data = await scrape_telegram_channel(tg_url)
                if tg_data.get("avatar_url") and not logo:
                    lead.logo_url = tg_data["avatar_url"]
                if tg_data.get("photos"):
                    for p in tg_data["photos"]:
                        if p not in cur_photos:
                            cur_photos.append(p)
                    lead.photos = cur_photos[:10]
            except Exception:
                pass

    # Vision AI sorting for real lead photos if multiple photos exist
    if len(cur_photos) > 1:
        try:
            from app.services.ai_router import sort_business_photos
            sorted_photos = await asyncio.wait_for(
                sort_business_photos(
                    cur_photos,
                    business_category=lead.category or "",
                    business_name=lead.name or "",
                ),
                timeout=6.0,
            )
            if sorted_photos.get("hero"):
                lead.photos = [sorted_photos["hero"]] + [
                    p for p in sorted_photos.get("gallery", []) if p != sorted_photos["hero"]
                ]
            if sorted_photos.get("logo") and not lead.logo_url:
                lead.logo_url = sorted_photos["logo"]
        except Exception as exc:
            logger.debug("Vision AI photo sort notice in create_demo: %s", exc)

    data = lead_to_dict(lead)
    demo_id = new_id()

    # Generate HTML and outreach message BEFORE holding any DB locks
    html, _engine = await generate_landing_html(data)
    message = await generate_outreach_message(data, public_demo_url(demo_id))

    # Save to database in a fresh, isolated transaction (protects against idle connection drops)
    async with SessionLocal() as db:
        demo = DemoSite(
            id=demo_id,
            lead_id=lead.id,
            title=f"Демо для {lead.name}",
            html=html,
            message=message,
            published=True,
        )
        db.add(demo)
        target_lead = await db.get(Lead, lead.id)
        if target_lead:
            target_lead.demo_id = demo.id
            if getattr(lead, "photos", None):
                target_lead.photos = lead.photos
            if getattr(lead, "logo_url", None):
                target_lead.logo_url = lead.logo_url
            db.add(target_lead)
        await db.commit()
        await db.refresh(demo)
        return demo


async def get_lead_demo(session: AsyncSession, lead: Lead) -> DemoSite | None:
    if not lead.demo_id:
        return None
    return await session.get(DemoSite, lead.demo_id)
