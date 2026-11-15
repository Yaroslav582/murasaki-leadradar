"""
Unified AI routing and multi-provider fallback engine for Murasaki LeadRadar.
Uses AsyncOpenAI with OpenAI-compatible endpoints across:
1. Groq (Ultra-fast, Llama 3)
2. Google AI Studio / Gemini (/v1beta/openai/)
3. OpenRouter (Free tier / community models)
4. MXR / OpenAI-compatible paid provider (Last-resort reserve)

Features:
- Task-type adaptive routing: "fast", "smart", "code"
- Automatic provider health check & instant fallback on 429 / 5xx / timeout / 403
- Hard daily rate limiter (MAX_DAILY_LLM_CALLS = 300) with UTC day rollover and DB sync
- Optional HTTP/SOCKS5 proxy support via AI_PROXY_URL
- Structured logging into Supabase system_logs
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.services.logger_service import log_event_bg

logger = logging.getLogger(__name__)


class AIQuotaExceededError(RuntimeError):
    """Raised when the maximum daily allowed LLM calls is reached."""
    pass


class AllProvidersFailedError(RuntimeError):
    """Raised when every provider in the fallback chain fails."""
    pass


# ── Daily Rate Limiter ────────────────────────────────────────────────────────
class AIRateLimiter:
    """In-memory rate limiter with daily UTC reset and database persistence."""

    def __init__(self, max_calls: int = 300) -> None:
        self.max_calls = max_calls
        self.today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.calls_count = 0
        self._lock = asyncio.Lock()
        self._synced_with_db = False

    async def _ensure_db_sync(self) -> None:
        if self._synced_with_db:
            return
        try:
            from app.db import SessionLocal
            from app.models import AppSetting

            async with SessionLocal() as session:
                st = await session.get(AppSetting, "ai_daily_calls")
                if st and st.value:
                    val = st.value
                    if val.get("date") == self.today:
                        self.calls_count = max(self.calls_count, int(val.get("count", 0)))
            self._synced_with_db = True
        except Exception as exc:
            logger.debug("Failed syncing AI rate limiter with DB: %s", exc)

    async def _persist_to_db(self) -> None:
        try:
            from app.db import SessionLocal
            from app.models import AppSetting

            async with SessionLocal() as session:
                st = await session.get(AppSetting, "ai_daily_calls")
                val = {"date": self.today, "count": self.calls_count}
                if st:
                    st.value = val
                else:
                    session.add(AppSetting(key="ai_daily_calls", value=val))
                await session.commit()
        except Exception as exc:
            logger.debug("Failed saving AI daily calls to DB: %s", exc)

    async def check_and_increment(self) -> int:
        async with self._lock:
            await self._ensure_db_sync()
            now_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if now_day != self.today:
                self.today = now_day
                self.calls_count = 0

            limit = settings.max_daily_llm_calls or self.max_calls
            if self.calls_count >= limit:
                msg = f"Превышен суточный лимит запросов к AI ({self.calls_count}/{limit}). Сброс в 00:00 UTC."
                logger.error("AI Router: %s", msg)
                log_event_bg("ai_router", msg, level="ERROR", details={"count": self.calls_count, "limit": limit})
                raise AIQuotaExceededError(msg)

            self.calls_count += 1
            current = self.calls_count

            # Asynchronously persist to DB every 5 calls or first call
            if current == 1 or current % 5 == 0:
                asyncio.create_task(self._persist_to_db())

            return current

    def get_stats(self) -> dict[str, Any]:
        limit = settings.max_daily_llm_calls or self.max_calls
        return {
            "calls_today": self.calls_count,
            "max_daily_calls": limit,
            "date_utc": self.today,
            "remaining_calls": max(0, limit - self.calls_count),
        }


rate_limiter = AIRateLimiter()


# ── Client Pool with Optional Proxy ───────────────────────────────────────────
_client_cache: dict[str, AsyncOpenAI] = {}


def _get_proxy_url() -> str | None:
    return settings.ai_proxy_url or os.getenv("AI_PROXY_URL") or settings.proxy_url or os.getenv("PROXY_URL")


def get_openai_client(
    provider_name: str,
    base_url: str,
    api_key: str,
    timeout: float,
    extra_headers: dict[str, str] | None = None,
) -> AsyncOpenAI:
    """Returns or creates a cached AsyncOpenAI client configured for the specific provider."""
    cache_key = f"{provider_name}:{base_url}:{api_key[:6] if len(api_key) > 6 else api_key}"
    if cache_key in _client_cache:
        return _client_cache[cache_key]

    proxy = _get_proxy_url()
    http_client = httpx.AsyncClient(proxy=proxy, timeout=timeout) if proxy else None

    default_headers = {}
    if extra_headers:
        default_headers.update(extra_headers)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        http_client=http_client,
        default_headers=default_headers if default_headers else None,
    )
    _client_cache[cache_key] = client
    return client


# ── Provider Chain Definitions ────────────────────────────────────────────────
def _get_provider_config(provider_id: str) -> dict[str, Any] | None:
    """Resolves credentials and base URL for a provider ID. Returns None if unconfigured."""
    if provider_id == "groq":
        key = (settings.groq_api_key or os.getenv("GROQ_API_KEY") or "").strip()
        if not key:
            return None
        return {
            "name": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": key,
            "extra_headers": None,
        }

    if provider_id == "gemini":
        key = (settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if not key:
            return None
        return {
            "name": "Google Gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key": key,
            "extra_headers": None,
        }

    if provider_id == "openrouter":
        key = (settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not key:
            return None
        return {
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": key,
            "extra_headers": {
                "HTTP-Referer": "https://leadradar.murasaki.app",
                "X-Title": "Murasaki LeadRadar",
            },
        }

    if provider_id == "mxr":
        key = (
            settings.mxr_api_key
            or os.getenv("MXR_API_KEY")
            or settings.openai_api_key
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()
        if not key:
            return None
        base_url = (
            settings.mxr_base_url
            or os.getenv("MXR_BASE_URL")
            or settings.openai_base_url
            or "https://mxr.one/v1"
        ).strip()
        return {
            "name": "MXR Reserve",
            "base_url": base_url,
            "api_key": key,
            "extra_headers": None,
        }

    return None


def get_task_chain(task_type: str) -> list[tuple[str, list[str]]]:
    """
    Returns priority list of (provider_id, [model_candidates]) for a given task type:
    1. fast: Groq -> Gemini -> OpenRouter -> MXR
    2. smart: Gemini -> Groq -> OpenRouter -> MXR
    3. code: Gemini -> OpenRouter -> MXR
    """
    reserve_model = settings.openai_model or "gpt-6-sol"

    if task_type == "fast":
        return [
            ("groq", ["llama-3.1-8b-instant"]),
            ("gemini", ["gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-1.5-flash"]),
            ("openrouter", ["openrouter/free", "meta-llama/llama-3.1-8b-instruct:free"]),
            ("mxr", [reserve_model]),
        ]

    if task_type == "smart":
        return [
            ("gemini", ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]),
            ("groq", ["llama-3.3-70b-versatile"]),
            ("openrouter", ["openrouter/free", "meta-llama/llama-3.3-70b-instruct:free"]),
            ("mxr", [reserve_model]),
        ]

    if task_type == "code":
        return [
            ("gemini", ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]),
            ("openrouter", ["openrouter/free", "meta-llama/llama-3.3-70b-instruct:free"]),
            ("mxr", [reserve_model]),
        ]

    # Default fallback chain
    return [
        ("groq", ["llama-3.1-8b-instant"]),
        ("gemini", ["gemini-2.5-flash", "gemini-1.5-flash"]),
        ("openrouter", ["openrouter/free"]),
        ("mxr", [reserve_model]),
    ]


# ── Core AI Router Function ───────────────────────────────────────────────────
async def ask_ai(
    prompt: str,
    system_prompt: str = "",
    task_type: str = "fast",
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> str:
    """
    Unified entry point for all AI calls across Murasaki LeadRadar.
    Automatically handles rate limiting, model selection, timeouts, and fallbacks.

    :param prompt: User prompt or main task description
    :param system_prompt: System role instructions
    :param task_type: "fast" | "smart" | "code"
    :param max_tokens: Max tokens to generate (defaults: fast=200, smart=500, code=4000)
    :param temperature: Generation temperature
    :return: Generated text response
    """
    # 1. Check daily rate limiter
    await rate_limiter.check_and_increment()

    # 2. Determine default tokens & timeouts
    if max_tokens is None:
        if task_type == "code":
            max_tokens = 4000
        elif task_type == "smart":
            max_tokens = 500
        else:
            max_tokens = 200

    timeout = 45.0 if task_type == "code" else 15.0

    # 3. Construct messages payload
    messages = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})

    chain = get_task_chain(task_type)
    errors_encountered: list[str] = []

    for provider_id, model_candidates in chain:
        prov_cfg = _get_provider_config(provider_id)
        if not prov_cfg:
            # Skip unconfigured provider without delay
            continue

        client = get_openai_client(
            provider_name=provider_id,
            base_url=prov_cfg["base_url"],
            api_key=prov_cfg["api_key"],
            timeout=timeout,
            extra_headers=prov_cfg["extra_headers"],
        )

        for model in model_candidates:
            try:
                logger.debug(
                    "AI Router: Calling %s (model=%s, task=%s, max_tokens=%d)...",
                    prov_cfg["name"], model, task_type, max_tokens
                )
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    timeout=timeout,
                )

                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content or ""
                    if content.strip():
                        logger.info(
                            "AI Router: %s [%s] successfully answered task '%s' (%d chars)",
                            prov_cfg["name"], model, task_type, len(content)
                        )
                        return content.strip()

            except asyncio.TimeoutError:
                err_msg = f"{prov_cfg['name']} ({model}) timed out after {timeout}s"
                logger.warning("AI Router timeout: %s", err_msg)
                errors_encountered.append(err_msg)
                log_event_bg("ai_router", err_msg, level="WARNING", details={"task_type": task_type, "model": model})
                break  # try next provider

            except Exception as exc:
                err_msg = f"{prov_cfg['name']} ({model}) error: {type(exc).__name__}: {exc}"
                logger.warning("AI Router error: %s", err_msg)
                errors_encountered.append(err_msg)
                log_event_bg("ai_router", err_msg, level="WARNING", details={"task_type": task_type, "model": model})
                # If error is a 404 model not found (e.g. Gemini preview versions), continue to candidate model;
                # otherwise jump to next provider on rate limit or auth issues
                err_str = str(exc).lower()
                if "404" in err_str or "not_found" in err_str or "does not exist" in err_str:
                    continue
                break

    all_errs = "; ".join(errors_encountered) if errors_encountered else "Все провайдеры в цепочке отключены или не настроены"
    logger.error("AI Router: All providers failed for task '%s'. Errors: %s", task_type, all_errs)
    log_event_bg("ai_router", f"All providers failed for task {task_type}", level="ERROR", details={"errors": errors_encountered})
    raise AllProvidersFailedError(f"Нейросети временно недоступны: {all_errs}")


# ── Diagnostics & Provider Status ─────────────────────────────────────────────
def get_ai_router_stats() -> dict[str, Any]:
    """Returns active rate limiter usage and configured provider statuses."""
    stats = rate_limiter.get_stats()
    stats["providers"] = {
        "groq": bool(settings.groq_api_key or os.getenv("GROQ_API_KEY")),
        "gemini": bool(settings.gemini_api_key or os.getenv("GEMINI_API_KEY")),
        "openrouter": bool(settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")),
        "mxr": bool(
            settings.mxr_api_key
            or os.getenv("MXR_API_KEY")
            or settings.openai_api_key
            or os.getenv("OPENAI_API_KEY")
        ),
    }
    stats["proxy_configured"] = bool(_get_proxy_url())
    return stats
