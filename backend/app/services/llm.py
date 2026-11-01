from __future__ import annotations

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


def load_llm_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load llm_config.json: %s", exc)

    return {
        "provider": settings.llm_provider or "openai",
        "model": settings.openai_model or "gpt-6-sol",
        "base_url": settings.openai_base_url or "https://mxr.one/v1",
        "api_key": settings.openai_api_key or "",
        "anthropic_key": settings.anthropic_api_key or "",
        "anthropic_model": settings.anthropic_model or "claude-3-5-sonnet-latest",
    }


def save_llm_config(cfg: dict[str, Any]) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("Failed to save llm_config.json: %s", exc)


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
) -> str:
    cfg = load_llm_config()
    provider = (cfg.get("provider") or settings.llm_provider or "mock").lower()
    model = cfg.get("model") or settings.openai_model or "gpt-6-sol"
    api_key = cfg.get("api_key") or settings.openai_api_key

    if provider == "openai":
        if not api_key:
            raise LLMUnavailable("API-ключ для нейросети не задан")
        base_url = (cfg.get("base_url") or settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadRadar/1.0",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            if not content and msg.get("reasoning_content"):
                content = msg.get("reasoning_content") or ""
            return content

    if provider == "anthropic":
        anthropic_key = cfg.get("anthropic_key") or cfg.get("api_key") or settings.anthropic_api_key
        if not anthropic_key:
            raise LLMUnavailable("ANTHROPIC_API_KEY не задан")
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return "".join(
                block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
            )

    raise LLMUnavailable("LLM_PROVIDER=mock")
