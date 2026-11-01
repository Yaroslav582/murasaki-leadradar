from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm import get_current_llm_info, update_llm_info

router = APIRouter(prefix="/llm", tags=["llm"])


class LLMUpdateIn(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None


@router.get("/config")
def get_llm_config():
    return get_current_llm_info()


@router.post("/config")
def update_llm_config(payload: LLMUpdateIn):
    return update_llm_info(
        provider=payload.provider,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
    )
