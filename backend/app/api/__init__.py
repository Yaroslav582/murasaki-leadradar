from __future__ import annotations

from fastapi import APIRouter

from app.api import accounts, billing, demos, dialogs, export, growth, leads, llm, meta, outreach, parse, telegram

api_router = APIRouter()
api_router.include_router(leads.router)
api_router.include_router(parse.router)
api_router.include_router(meta.router)
api_router.include_router(demos.router)
api_router.include_router(demos.single_demo_router)
api_router.include_router(export.router)
api_router.include_router(telegram.router)
api_router.include_router(llm.router)
api_router.include_router(growth.router)
api_router.include_router(accounts.router)
api_router.include_router(billing.router)
api_router.include_router(dialogs.router)
api_router.include_router(outreach.router)
