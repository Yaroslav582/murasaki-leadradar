from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import DemoSite
from app.schemas import DemoOut, DemoUpdate
from app.services.demos import demo_out

router = APIRouter(prefix="/demos", tags=["demos"])


@router.get("/{demo_id}", response_model=DemoOut)
async def get_demo(demo_id: str, session: AsyncSession = Depends(get_session)) -> DemoOut:
    demo = await session.get(DemoSite, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return demo_out(demo)


@router.patch("/{demo_id}", response_model=DemoOut)
async def update_demo(
    demo_id: str,
    payload: DemoUpdate,
    session: AsyncSession = Depends(get_session),
) -> DemoOut:
    demo = await session.get(DemoSite, demo_id)
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
    demo = await session.get(DemoSite, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Демо не найдено")
    return HTMLResponse(
        content=demo.html,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
    )
