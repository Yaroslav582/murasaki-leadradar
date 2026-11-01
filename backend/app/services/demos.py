from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DemoSite, Lead
from app.schemas import DemoOut
from app.services.landing import build_outreach, generate_landing_html, generate_outreach_message


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
    }


def public_demo_url(demo_id: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/demo/{demo_id}"


def demo_out(demo: DemoSite) -> DemoOut:
    data = DemoOut.model_validate(demo)
    data.public_url = public_demo_url(demo.id)
    return data


async def create_demo(session: AsyncSession, lead: Lead) -> DemoSite:
    data = lead_to_dict(lead)
    html, _engine = await generate_landing_html(data)
    demo = DemoSite(
        lead_id=lead.id,
        title=f"Демо для {lead.name}",
        html=html,
        published=True,
    )
    session.add(demo)
    await session.flush()
    demo.message = await generate_outreach_message(data, public_demo_url(demo.id))
    lead.demo_id = demo.id
    session.add(lead)
    await session.commit()
    await session.refresh(demo)
    return demo


async def get_lead_demo(session: AsyncSession, lead: Lead) -> DemoSite | None:
    if not lead.demo_id:
        return None
    return await session.get(DemoSite, lead.demo_id)
