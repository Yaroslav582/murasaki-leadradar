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
from app.services.media_collector import collect_media

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
    if hasattr(demo, "style"):
        data.style = getattr(demo, "style", None)
    return data


async def create_demo(session: AsyncSession, lead: Lead, style: str | None = None) -> DemoSite:
    lead_dict = lead_to_dict(lead)

    # 1. Cascading media collection (Yandex Maps + TG Channel + TG Profile + Persistence + Niche fallback)
    try:
        media_res = await collect_media(lead_dict, max_items=12)
        collected_photos = media_res.get("photos") or []
        if media_res.get("logo_url") and not lead.logo_url:
            lead.logo_url = media_res["logo_url"]
    except Exception as exc:
        logger.warning("Media collection notice for %s: %s", lead.name, exc)
        collected_photos = list(getattr(lead, "photos", []) or [])

    # 2. Vision AI sorting (distributes into hero_product, interior, trash)
    if len(collected_photos) > 1:
        try:
            from app.services.ai_router import sort_business_photos
            sorted_photos = await asyncio.wait_for(
                sort_business_photos(
                    collected_photos,
                    business_category=lead.category or "",
                    business_name=lead.name or "",
                ),
                timeout=7.0,
            )
            hp = sorted_photos.get("hero_product") or []
            interior = sorted_photos.get("interior") or []
            ordered_photos = hp + [p for p in interior if p not in hp]
            lead.photos = ordered_photos if ordered_photos else collected_photos
            if sorted_photos.get("logo") and not lead.logo_url:
                lead.logo_url = sorted_photos["logo"]
        except Exception as exc:
            logger.debug("Vision AI photo sort notice in create_demo: %s", exc)
            lead.photos = collected_photos
    else:
        lead.photos = collected_photos

    data = lead_to_dict(lead)
    demo_id = new_id()

    from app.services.design_systems import resolve_style_id
    effective_style = resolve_style_id(style, lead.category)

    # 3. Generate HTML via structured AI JSON + Jinja2 niche templates
    html, _engine = await generate_landing_html(data, style_id=effective_style)
    message = await generate_outreach_message(data, public_demo_url(demo_id))

    # 4. Save to database in a fresh, isolated transaction (protects against idle connection drops)
    async with SessionLocal() as db:
        demo = DemoSite(
            id=demo_id,
            lead_id=lead.id,
            title=f"Демо для {lead.name}",
            html=html,
            message=message,
            published=True,
            style=effective_style,
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
