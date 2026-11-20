from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import DATA_DIR, settings

logger = logging.getLogger(__name__)

CONFIG_FILE = DATA_DIR / "llm_config.json"

DEFAULT_PRESETS = [
    {
        "id": "gpt-6-sol",
        "name": "MXR GPT-6 Sol (Флагман)",
        "provider": "openai",
        "base_url": "https://mxr.one/v1",
        "description": "Основная мощная модель MXR. Идеальна для лендингов, копирайтинга и откликов.",
        "badge": "Рекомендовано",
    },
    {
        "id": "gpt-6.1-sol",
        "name": "MXR GPT-6.1 Sol (Новое поколение)",
        "provider": "openai",
        "base_url": "https://mxr.one/v1",
        "description": "Продвинутая модель с глубоким анализом и улучшенной стилистикой текстов.",
        "badge": "Smart",
    },
    {
        "id": "gpt-6-astra",
        "name": "MXR GPT-6 Astra (Турбо-скорость)",
        "provider": "openai",
        "base_url": "https://mxr.one/v1",
        "description": "Сверхбыстрая генерация откликов и промо-постов за 1-2 секунды.",
        "badge": "Быстрая",
    },
    {
        "id": "gpt-5.6-sol",
        "name": "MXR GPT-5.6 Sol",
        "provider": "openai",
        "base_url": "https://mxr.one/v1",
        "description": "Стабильная классическая модель MXR.",
        "badge": "Стабильная",
    },
    {
        "id": "gpt-4o-mini",
        "name": "OpenAI GPT-4o Mini",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "description": "Легкая быстрая модель OpenAI для коротких задач.",
        "badge": "OpenAI",
    },
    {
        "id": "gpt-4o",
        "name": "OpenAI GPT-4o",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "description": "Флагман OpenAI для комплексных веб-задач.",
        "badge": "OpenAI",
    },
    {
        "id": "claude-3-5-sonnet-latest",
        "name": "Anthropic Claude 3.5 Sonnet",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "description": "Лидер в написании красивого адаптивного HTML/CSS кода лендингов.",
        "badge": "Anthropic",
    },
]


_in_memory_llm_cfg: dict[str, Any] | None = None


async def load_llm_config_from_db() -> dict[str, Any] | None:
    """Preloads LLM config from Supabase app_settings table into memory cache."""
    global _in_memory_llm_cfg
    try:
        from app.db import SessionLocal
        from app.models import AppSetting

        async with SessionLocal() as session:
            setting = await session.get(AppSetting, "llm_config")
            if setting and setting.value:
                _in_memory_llm_cfg = setting.value
                return setting.value
    except Exception as exc:
        logger.debug("Could not load llm_config from Supabase app_settings: %s", exc)
    return None


async def save_llm_config_to_db(cfg: dict[str, Any]) -> None:
    """Persists LLM configuration into Supabase app_settings table."""
    try:
        from app.db import SessionLocal
        from app.models import AppSetting

        async with SessionLocal() as session:
            setting = await session.get(AppSetting, "llm_config")
            if setting:
                setting.value = cfg
            else:
                session.add(AppSetting(key="llm_config", value=cfg))
            await session.commit()
    except Exception as exc:
        logger.error("Could not persist llm_config to Supabase: %s", exc)


def load_llm_config() -> dict[str, Any]:
    global _in_memory_llm_cfg
    if _in_memory_llm_cfg is not None:
        return dict(_in_memory_llm_cfg)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                _in_memory_llm_cfg = json.load(f)
                return dict(_in_memory_llm_cfg)
        except Exception as exc:
            logger.warning("Failed to load llm_config.json: %s", exc)

    _in_memory_llm_cfg = {
        "provider": settings.llm_provider or "openai",
        "model": settings.openai_model or "gpt-6-sol",
        "base_url": settings.openai_base_url or "https://mxr.one/v1",
        "api_key": settings.openai_api_key or "",
        "anthropic_key": settings.anthropic_api_key or "",
        "anthropic_model": settings.anthropic_model or "claude-3-5-sonnet-latest",
    }
    return dict(_in_memory_llm_cfg)


def save_llm_config(cfg: dict[str, Any]) -> None:
    global _in_memory_llm_cfg
    _in_memory_llm_cfg = cfg
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(save_llm_config_to_db(cfg))
    except RuntimeError:
        pass

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass



def get_current_llm_info() -> dict[str, Any]:
    cfg = load_llm_config()
    provider = cfg.get("provider", "openai").lower()
    model = cfg.get("model", "gpt-6-sol")
    base_url = cfg.get("base_url", "https://mxr.one/v1")
    has_api_key = bool(cfg.get("api_key") or (provider == "anthropic" and cfg.get("anthropic_key")))

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "has_api_key": has_api_key,
        "presets": DEFAULT_PRESETS,
    }


def update_llm_info(
    provider: str,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    cfg = load_llm_config()
    cfg["provider"] = provider.lower()
    cfg["model"] = model.strip()
    if base_url is not None:
        cfg["base_url"] = base_url.strip()
    if api_key is not None and api_key.strip():
        cfg["api_key"] = api_key.strip()
        if provider.lower() == "anthropic":
            cfg["anthropic_key"] = api_key.strip()

    save_llm_config(cfg)

    # Sync into runtime settings object
    settings.llm_provider = cfg["provider"]
    if cfg["provider"] == "openai":
        settings.openai_model = cfg["model"]
        settings.openai_base_url = cfg.get("base_url")
        if cfg.get("api_key"):
            settings.openai_api_key = cfg["api_key"]
    elif cfg["provider"] == "anthropic":
        settings.anthropic_model = cfg["model"]
        if cfg.get("anthropic_key") or cfg.get("api_key"):
            settings.anthropic_api_key = cfg.get("anthropic_key") or cfg.get("api_key")

    return get_current_llm_info()


class LLMUnavailable(RuntimeError):
    pass


async def chat_completion(
    system: str,
    user: str,
    *,
    max_tokens: int = 6000,
    temperature: float = 0.8,
    task_type: str | None = None,
) -> str:
    """Delegates chat completions to the unified ai_router with automatic task-type inference."""
    from app.services.ai_router import ask_ai

    if task_type is None:
        if max_tokens > 2000 or "html" in system.lower() or "лендинг" in system.lower():
            task_type = "code"
        elif max_tokens > 300 or "менеджер" in system.lower() or "отклик" in system.lower():
            task_type = "smart"
        else:
            task_type = "fast"

    try:
        return await ask_ai(
            prompt=user,
            system_prompt=system,
            task_type=task_type,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as exc:
        raise LLMUnavailable(str(exc)) from exc

