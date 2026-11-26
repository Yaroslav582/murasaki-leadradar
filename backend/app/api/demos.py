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
