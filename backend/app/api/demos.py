from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import DemoSite, Lead, utcnow
from app.schemas import DemoOut, DemoRefineRequest, DemoUpdate
from app.services.demos import _capture_and_save_screenshot, demo_out, resolve_demo_by_identifier

router = APIRouter(prefix="/demos", tags=["demos"])
single_demo_router = APIRouter(prefix="/demo", tags=["demos"])


@router.get("/styles")
async def list_demo_styles():
    """Returns available design systems and styles inspired by VoltAgent/awesome-design-md."""
    from app.services.design_systems import get_all_styles
    return {"styles": get_all_styles()}


@router.get("/{demo_id}", response_model=DemoOut)
async def get_demo(demo_id: str, session: AsyncSession = Depends(get_session)) -> DemoOut:
    demo = await resolve_demo_by_identifier(session, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return demo_out(demo)


@router.patch("/{demo_id}", response_model=DemoOut)
async def update_demo(
    demo_id: str,
    payload: DemoUpdate,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    demo = await resolve_demo_by_identifier(session, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")

    if payload.html is not None:
        demo.html = payload.html
    if payload.message is not None:
        demo.message = payload.message
    if payload.published is not None:
        demo.published = payload.published

    session.add(demo)
    await session.commit()
    await session.refresh(demo)
    return demo_out(demo)


@router.get("/{demo_id}/raw", response_class=HTMLResponse)
async def get_demo_raw(demo_id: str, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    demo = await resolve_demo_by_identifier(session, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return HTMLResponse(
        content=demo.html,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
    )


@router.post("/{demo_id}/screenshot")
async def generate_demo_screenshot(demo_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    demo = await resolve_demo_by_identifier(session, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    url = await _capture_and_save_screenshot(demo.id, demo.html)
    return {"demo_id": demo.id, "preview_image_url": url}


async def _refine_demo_impl(
    demo_id: str,
    payload: DemoRefineRequest,
    session: AsyncSession,
) -> DemoOut:
    demo = await resolve_demo_by_identifier(session, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")

    lead = await session.get(Lead, demo.lead_id) if demo.lead_id else None
    from app.services.ai_router import refine_demo_html

    try:
        updated_html = await refine_demo_html(
            current_html=demo.html,
            user_instruction=payload.prompt,
            style_id=demo.style,
            category=lead.category if lead else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка AI-докрутки: {exc}") from exc

    demo.html = updated_html
    demo.updated_at = utcnow()
    session.add(demo)
    await session.commit()
    await session.refresh(demo)

    asyncio.create_task(_capture_and_save_screenshot(demo.id, demo.html))
    return demo_out(demo)


@router.post("/{demo_id}/refine", response_model=DemoOut)
async def refine_demo(
    demo_id: str,
    payload: DemoRefineRequest,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    return await _refine_demo_impl(demo_id, payload, session)


@single_demo_router.post("/{demo_id}/refine", response_model=DemoOut)
async def refine_demo_singular(
    demo_id: str,
    payload: DemoRefineRequest,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    return await _refine_demo_impl(demo_id, payload, session)


async def _rebuild_demo_impl(demo_id: str, session: AsyncSession) -> DemoOut:
    """Re-collect media, re-run sub-niche Vision photo sorting, and rebuild demo HTML."""
    from app.services.ai_router import sort_business_photos
    from app.services.demos import lead_to_dict, public_demo_url
    from app.services.design_systems import resolve_style_id
    from app.services.landing import generate_landing_html
    from app.services.media_collector import collect_media

    demo = await resolve_demo_by_identifier(session, demo_id, allow_lead_fallback=True)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")

    lead = await session.get(Lead, demo.lead_id) if demo.lead_id else None
    if lead is None:
        raise HTTPException(status_code=404, detail="Связанный лид не найден")

    data = lead_to_dict(lead)
    media_res = await collect_media(data, max_items=12)
    real_photos = media_res.get("real_photos") or []
    collected_photos = media_res.get("photos") or []

    hp: list[str] = []
    work_captions: dict[str, str] = {}
    interior: list[str] = []
    rejected: list[str] = []
    if real_photos:
        try:
            sorted_photos = await asyncio.wait_for(
                sort_business_photos(
                    real_photos,
                    business_category=lead.category or "",
                    business_name=lead.name or "",
                ),
                timeout=25.0,
            )
            hp = sorted_photos.get("hero_product") or []
            work_captions = dict(sorted_photos.get("work_captions") or {})
            interior = sorted_photos.get("interior") or []
            rejected = sorted_photos.get("rejected") or sorted_photos.get("trash") or []
        except Exception:
            pass

    lead.photos = collected_photos
    data["photos"] = collected_photos
    data["hero_product"] = hp
    data["work_captions"] = work_captions
    data["interior_photos"] = interior
    data["rejected_photos"] = rejected

    from app.services.brand_color import resolve_lead_brand_color
    tg_avatar_url = None
    tg_link = (data.get("social_links") or {}).get("telegram") if isinstance(data.get("social_links"), dict) else None
    if tg_link:
        try:
            from app.services.telegram_channel_scraper import scrape_telegram_channel
            tg_info = await scrape_telegram_channel(str(tg_link), limit_photos=0)
            tg_avatar_url = tg_info.get("avatar_url")
        except Exception:
            tg_avatar_url = None

    _, brand_color = await resolve_lead_brand_color(
        avatar_url=tg_avatar_url or data.get("logo_url"),
        category=lead.category,
        business_name=lead.name,
    )
    data["brand_color"] = brand_color

    effective_style = resolve_style_id(demo.style, lead.category)
    target_public_url = public_demo_url(demo.slug or demo.id)
    html_code, _engine = await generate_landing_html(
        data,
        style_id=effective_style,
        public_url=target_public_url,
    )

    demo.html = html_code
    demo.brand_color = brand_color
    demo.updated_at = utcnow()
    session.add(demo)
    session.add(lead)
    await session.commit()
    await session.refresh(demo)

    asyncio.create_task(_capture_and_save_screenshot(demo.id, demo.html))
    return demo_out(demo)


@router.post("/{demo_id}/rebuild", response_model=DemoOut)
async def rebuild_demo(demo_id: str, session: AsyncSession = Depends(get_session)) -> DemoOut:
    return await _rebuild_demo_impl(demo_id, session)


@single_demo_router.post("/{demo_id}/rebuild", response_model=DemoOut)
async def rebuild_demo_singular(demo_id: str, session: AsyncSession = Depends(get_session)) -> DemoOut:
    return await _rebuild_demo_impl(demo_id, session)
