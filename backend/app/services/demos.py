from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import DemoSite, Lead, new_id
from app.schemas import DemoOut
from app.services.landing import build_outreach, generate_landing_html, generate_outreach_message
from app.services.media_collector import collect_media

logger = logging.getLogger(__name__)

_CYRILLIC_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def transliterate_slug(name: str, city: str = "") -> str:
    """Build a clean ASCII kebab-case slug from business name and city."""
    raw = f"{name or ''} {city or ''}".strip().lower()
    out: list[str] = []
    for ch in raw:
        if ch in _CYRILLIC_MAP:
            out.append(_CYRILLIC_MAP[ch])
        elif "a" <= ch <= "z" or "0" <= ch <= "9":
            out.append(ch)
        else:
            out.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    if not slug:
        slug = f"demo-{new_id()[:8]}"
    return slug[:80].strip("-")


async def generate_unique_slug(session: AsyncSession, name: str, city: str = "") -> str:
    """Return a unique slug, appending -2, -3, ... if already taken."""
    base = transliterate_slug(name, city)
    candidate = base
    suffix = 2
    while True:
        exists = await session.scalar(select(DemoSite.id).where(DemoSite.slug == candidate))
        if not exists:
            return candidate
        candidate = f"{base[:72]}-{suffix}"
        suffix += 1


async def resolve_demo_by_identifier(
    session: AsyncSession, identifier: str, allow_lead_fallback: bool = False
) -> DemoSite | None:
    """Find DemoSite by UUID id, human slug, or optionally lead_id."""
    target = (identifier or "").strip()
    if not target:
        return None
    demo = await session.get(DemoSite, target)
    if demo is not None:
        return demo
    res = await session.execute(select(DemoSite).where(DemoSite.slug == target))
    demo = res.scalars().first()
    if demo is not None:
        return demo
    if allow_lead_fallback:
        res = await session.execute(
            select(DemoSite).where(DemoSite.lead_id == target).order_by(DemoSite.created_at.desc())
        )
        return res.scalars().first()
    return None


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


def public_demo_url(demo_id_or_slug: str) -> str:
    base = settings.public_base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/demo/{demo_id_or_slug}"


def demo_out(demo: DemoSite) -> DemoOut:
    data = DemoOut.model_validate(demo)
    identifier = getattr(demo, "slug", None) or demo.id
    data.public_url = public_demo_url(identifier)
    if hasattr(demo, "style"):
        data.style = getattr(demo, "style", None)
    return data


async def create_demo(session: AsyncSession, lead: Lead, style: str | None = None) -> DemoSite:
    lead_dict = lead_to_dict(lead)

    # 1. Cascading media collection (Yandex Maps + TG Channel + TG Profile + Persistence + Niche fallback)
    try:
        media_res = await collect_media(lead_dict, max_items=12)
        collected_photos = media_res.get("photos") or []
        real_photos = media_res.get("real_photos") if "real_photos" in media_res else collected_photos
        if media_res.get("logo_url") and not lead.logo_url:
            lead.logo_url = media_res["logo_url"]
    except Exception as exc:
        logger.warning("Media collection notice for %s: %s", lead.name, exc)
        collected_photos = list(getattr(lead, "photos", []) or [])
        real_photos = [
            p for p in collected_photos
            if "images.unsplash.com" not in p and "/static/stock/" not in p
        ]

    # 2. Vision AI sorting ONLY on real business photos (distributes into hero_product, interior, rejected)
    hp: list[str] = []
    interior: list[str] = []
    rejected: list[str] = []
    if real_photos:
        try:
            from app.services.ai_router import sort_business_photos
            sorted_photos = await asyncio.wait_for(
                sort_business_photos(
                    real_photos,
                    business_category=lead.category or "",
                    business_name=lead.name or "",
                ),
                timeout=25.0,
            )
            hp = sorted_photos.get("hero_product") or []
            interior = sorted_photos.get("interior") or []
            rejected = sorted_photos.get("rejected") or sorted_photos.get("trash") or []
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
    data["hero_product"] = hp
    data["interior_photos"] = interior
    data["rejected_photos"] = rejected
    demo_id = new_id()

    from app.services.design_systems import resolve_style_id
    effective_style = resolve_style_id(style, lead.category)

    async with SessionLocal() as slug_db:
        demo_slug = await generate_unique_slug(slug_db, lead.name, lead.city)
    target_public_url = public_demo_url(demo_slug)

    # 3. Generate HTML via structured AI JSON + Jinja2 niche templates
    html, _engine = await generate_landing_html(
        data,
        style_id=effective_style,
        public_url=target_public_url,
    )
    message = await generate_outreach_message(data, target_public_url)

    # 4. Save to database in a fresh, isolated transaction (protects against idle connection drops)
    async with SessionLocal() as db:
        demo_slug = await generate_unique_slug(db, lead.name, lead.city)
        demo = DemoSite(
            id=demo_id,
            lead_id=lead.id,
            slug=demo_slug,
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

        # Capture mobile preview screenshot in background (best-effort)
        asyncio.create_task(_capture_and_save_screenshot(demo.id, demo.html))
        return demo


async def capture_demo_screenshot(demo_id: str, html_content: str) -> Path | None:
    """Render demo HTML into a mobile-sized PNG preview using Playwright if available."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None

    out_dir = Path(__file__).resolve().parent.parent / "static" / "uploads" / "demos"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{demo_id}.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 412, "height": 840}, device_scale_factor=2)
            await page.set_content(html_content, wait_until="networkidle", timeout=15000)
            await page.screenshot(path=str(out_path), full_page=False)
            await browser.close()
        return out_path
    except Exception as exc:
        logger.debug("Demo screenshot skipped for %s: %s", demo_id, exc)
        return None


async def _capture_and_save_screenshot(demo_id: str, html_content: str) -> str | None:
    path = await capture_demo_screenshot(demo_id, html_content)
    if not path:
        return None
    rel_url = f"/static/uploads/demos/{demo_id}.png"
    try:
        async with SessionLocal() as db:
            demo = await db.get(DemoSite, demo_id)
            if demo:
                demo.preview_image_url = rel_url
                db.add(demo)
                await db.commit()
    except Exception as exc:
        logger.debug("Could not persist preview_image_url for %s: %s", demo_id, exc)
    return rel_url


async def get_lead_demo(session: AsyncSession, lead: Lead) -> DemoSite | None:
    if not lead.demo_id:
        return None
    return await session.get(DemoSite, lead.demo_id)
