from __future__ import annotations

from fastapi import APIRouter

from app.api import demos, export, growth, leads, llm, meta, parse, telegram

api_router = APIRouter()
api_router.include_router(leads.router)
api_router.include_router(parse.router)
api_router.include_router(meta.router)
api_router.include_router(demos.router)
api_router.include_router(export.router)
api_router.include_router(telegram.router)
api_router.include_router(llm.router)
api_router.include_router(growth.router)
