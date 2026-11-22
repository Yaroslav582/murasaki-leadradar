"""
Unified AI routing and multi-provider fallback engine for Murasaki LeadRadar.
Uses AsyncOpenAI with OpenAI-compatible endpoints across:
1. Groq (https://api.groq.com/openai/v1)
2. OpenRouter (https://openrouter.ai/api/v1)
3. Google AI Studio / Gemini (https://generativelanguage.googleapis.com/v1beta/openai/)
4. MXR / OpenAI-compatible paid provider (Last-resort reserve)

Chains configured via environment variables:
- TEXT_MODELS_CHAIN: Ordered list of provider:model_id for text, copy, code and landing JSON generation.
- VISION_MODELS_CHAIN: Ordered list of provider:model_id for multimodal image analysis & photo sorting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.config import (
    DEFAULT_TEXT_MODELS_CHAIN,
    DEFAULT_VISION_MODELS_CHAIN,
    settings,
)
from app.services.logger_service import log_event_bg

logger = logging.getLogger(__name__)


class AIQuotaExceededError(RuntimeError):
    """Raised when the maximum daily allowed LLM calls is reached."""
    pass


class AllProvidersFailedError(RuntimeError):
    """Raised when every provider in the fallback chain fails."""
    pass


# ── Daily Rate Limiter (Max 400 calls per day) ────────────────────────────────
class AIRateLimiter:
    """In-memory rate limiter with daily UTC reset and database persistence."""

    def __init__(self, max_calls: int = 400) -> None:
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

            # Asynchronously persist to DB every 5 calls or on first call
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


rate_limiter = AIRateLimiter(max_calls=400)


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


# ── Provider Resolution & Chain Parsers ───────────────────────────────────────
def _read_secret(key: str) -> str:
    """Reads secret from environment, or from Render Secret Files (/etc/secrets/<key>)."""
    val = os.getenv(key)
    if val and str(val).strip():
        return str(val).strip()
    from pathlib import Path
    for folder in [Path("/etc/secrets"), Path.cwd(), Path(__file__).resolve().parent.parent.parent]:
        candidate = folder / key
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except Exception:
                pass
    return ""


def _get_provider_config(provider_id: str) -> dict[str, Any] | None:
    """Resolves credentials and base URL for a provider ID. Returns None if unconfigured."""
    p = provider_id.strip().lower()

    if p == "groq":
        key = (settings.groq_api_key or _read_secret("GROQ_API_KEY")).strip()
        if not key:
            return None
        return {
            "name": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": key,
            "extra_headers": None,
        }

    if p in ("gemini", "google"):
        key = (settings.gemini_api_key or _read_secret("GEMINI_API_KEY")).strip()
        if not key:
            return None
        return {
            "name": "Google AI Studio",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key": key,
            "extra_headers": None,
        }

    if p == "openrouter":
        key = (settings.openrouter_api_key or _read_secret("OPENROUTER_API_KEY")).strip()
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

    if p in ("mxr", "openai"):
        key = (
            settings.mxr_api_key
            or _read_secret("MXR_API_KEY")
            or settings.openai_api_key
            or _read_secret("OPENAI_API_KEY")
            or ""
        ).strip()
        if not key:
            return None
        base_url = (
            settings.mxr_base_url
            or _read_secret("MXR_BASE_URL")
            or settings.openai_base_url
            or "https://mxr.one/v1"
        ).strip()
        return {
            "name": "MXR Reserve (Paid)",
            "base_url": base_url,
            "api_key": key,
            "extra_headers": None,
        }

    return None


def parse_model_chain(raw_chain: str | None) -> list[tuple[str, str]]:
    """
    Parses comma-separated 'provider:model_id' strings into a structured list of (provider, model_id).
    Splits strictly on the first colon to preserve model tags like ':free'.
    """
    if not raw_chain or not raw_chain.strip():
        return []

    results: list[tuple[str, str]] = []
    tokens = [t.strip() for t in raw_chain.split(",") if t.strip()]
    for token in tokens:
        if ":" in token:
            prov, model_id = token.split(":", 1)
            prov = prov.strip().lower()
            model_id = model_id.strip()
            if prov and model_id:
                results.append((prov, model_id))
    return results


def get_text_models_chain() -> list[tuple[str, str]]:
    """Returns the parsed ordered list of text models from TEXT_MODELS_CHAIN in .env."""
    raw = (
        getattr(settings, "text_models_chain", None)
        or os.getenv("TEXT_MODELS_CHAIN")
        or DEFAULT_TEXT_MODELS_CHAIN
    )
    chain = parse_model_chain(raw)
    return chain if chain else parse_model_chain(DEFAULT_TEXT_MODELS_CHAIN)


def get_vision_models_chain() -> list[tuple[str, str]]:
    """Returns the parsed ordered list of multimodal vision models from VISION_MODELS_CHAIN in .env."""
    raw = (
        getattr(settings, "vision_models_chain", None)
        or os.getenv("VISION_MODELS_CHAIN")
        or DEFAULT_VISION_MODELS_CHAIN
    )
    chain = parse_model_chain(raw)
    return chain if chain else parse_model_chain(DEFAULT_VISION_MODELS_CHAIN)


def get_task_chain(task_type: str = "text") -> list[tuple[str, str]]:
    """Unified helper returning the ordered model chain for a task."""
    if task_type == "vision":
        return get_vision_models_chain()
    return get_text_models_chain()


# ── JSON Extraction Helper ────────────────────────────────────────────────────
def extract_json_payload(text: str) -> dict[str, Any] | list[Any] | None:
    """Extracts and parses JSON object or array from LLM response text."""
    if not text or not text.strip():
        return None
    cleaned = text.strip()

    # 1. Direct JSON parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Markdown fenced code block ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # 3. Outer braces {...}
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace : last_brace + 1])
        except Exception:
            pass

    # 4. Outer brackets [...]
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(cleaned[first_bracket : last_bracket + 1])
        except Exception:
            pass

    return None


# ── Core Text & JSON AI Router Function ───────────────────────────────────────
async def ask_ai(
    prompt: str,
    system_prompt: str = "",
    task_type: str = "text",
    max_tokens: int | None = None,
    temperature: float = 0.7,
    expect_json: bool = False,
) -> str:
    """
    Unified entry point for text, copy, code and JSON generation across Murasaki LeadRadar.
    Reads TEXT_MODELS_CHAIN from .env and tries models strictly in order.
    Automatically handles rate limiting, timeouts, and transparent fallbacks on:
    - HTTP 429 RateLimit
    - Timeout (12s / 18s)
    - 5xx Server Errors & 400/404 decommission notices
    - Invalid JSON when expect_json=True
    """
    # 1. Check daily rate limiter (max 400 calls per day)
    await rate_limiter.check_and_increment()

    # 2. Determine default tokens & timeouts
    is_code_or_json = task_type in ("code", "json") or expect_json
    if max_tokens is None:
        if is_code_or_json:
            max_tokens = 2200
        elif task_type == "smart":
            max_tokens = 800
        else:
            max_tokens = 400

    timeout = 18.0 if is_code_or_json else 12.0

    # 3. Construct messages payload
    messages = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})

    chain = get_text_models_chain()
    errors_encountered: list[str] = []

    for provider_id, model_id in chain:
        prov_cfg = _get_provider_config(provider_id)
        if not prov_cfg:
            logger.debug("AI Router: Skipping %s [%s] (provider not configured with API key)", provider_id, model_id)
            continue

        client = get_openai_client(
            provider_name=provider_id,
            base_url=prov_cfg["base_url"],
            api_key=prov_cfg["api_key"],
            timeout=timeout,
            extra_headers=prov_cfg["extra_headers"],
        )

        try:
            logger.info(
                "AI Router: Trying %s [model=%s, task=%s, timeout=%ss]...",
                prov_cfg["name"], model_id, task_type, timeout
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout,
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""
                trimmed = content.strip()
                if not trimmed:
                    err_msg = f"{prov_cfg['name']} ({model_id}) returned empty response"
                    logger.warning("AI Router fallback: %s -> switching to next model in chain", err_msg)
                    errors_encountered.append(err_msg)
                    continue

                if expect_json or task_type == "json":
                    parsed = extract_json_payload(trimmed)
                    if parsed is None:
                        err_msg = f"{prov_cfg['name']} ({model_id}) returned invalid JSON payload"
                        logger.warning("AI Router fallback: %s -> switching to next model in chain", err_msg)
                        errors_encountered.append(err_msg)
                        log_event_bg("ai_router", err_msg, level="WARNING", details={"model": model_id, "reason": "invalid_json"})
                        continue

                logger.info(
                    "AI Router: %s [%s] successfully answered task '%s' (%d chars)",
                    prov_cfg["name"], model_id, task_type, len(trimmed)
                )
                return trimmed

        except asyncio.TimeoutError:
            err_msg = f"{prov_cfg['name']} ({model_id}) timed out after {timeout}s"
            logger.warning("AI Router fallback: %s -> switching to next model in chain", err_msg)
            errors_encountered.append(err_msg)
            log_event_bg("ai_router", err_msg, level="WARNING", details={"task_type": task_type, "model": model_id, "reason": "timeout"})
            continue

        except Exception as exc:
            err_msg = f"{prov_cfg['name']} ({model_id}) error: {type(exc).__name__}: {exc}"
            logger.warning("AI Router fallback: %s -> switching to next model in chain", err_msg)
            errors_encountered.append(err_msg)
            log_event_bg("ai_router", err_msg, level="WARNING", details={"task_type": task_type, "model": model_id, "error": str(exc)})
            continue

    # Last resort fallback: MXR reserve model if configured and not already exhausted
    mxr_cfg = _get_provider_config("mxr")
    if mxr_cfg and not any(p == "mxr" for p, _ in chain):
        reserve_model = settings.openai_model or "gpt-6-astra"
        try:
            logger.info("AI Router: Attempting last-resort reserve %s [%s]...", mxr_cfg["name"], reserve_model)
            client = get_openai_client(
                provider_name="mxr",
                base_url=mxr_cfg["base_url"],
                api_key=mxr_cfg["api_key"],
                timeout=timeout,
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=reserve_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout,
            )
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""
                if content.strip():
                    logger.info("AI Router: Last-resort %s [%s] succeeded (%d chars)", mxr_cfg["name"], reserve_model, len(content))
                    return content.strip()
        except Exception as exc:
            err_msg = f"Last-resort {mxr_cfg['name']} ({reserve_model}) error: {exc}"
            logger.warning("AI Router: %s", err_msg)
            errors_encountered.append(err_msg)

    all_errs = "; ".join(errors_encountered) if errors_encountered else "Все провайдеры в цепочке отключены или не настроены"
    logger.error("AI Router: All providers failed for task '%s'. Errors: %s", task_type, all_errs)
    log_event_bg("ai_router", f"All providers failed for task {task_type}", level="ERROR", details={"errors": errors_encountered})
    raise AllProvidersFailedError(f"Нейросети временно недоступны: {all_errs}")


async def ask_ai_json(
    prompt: str,
    system_prompt: str = "",
    task_type: str = "json",
    max_tokens: int | None = None,
    temperature: float = 0.2,
) -> dict[str, Any] | list[Any]:
    """Convenience helper executing ask_ai with expect_json=True and returning the parsed dict/list."""
    raw = await ask_ai(
        prompt=prompt,
        system_prompt=system_prompt,
        task_type=task_type,
        max_tokens=max_tokens,
        temperature=temperature,
        expect_json=True,
    )
    parsed = extract_json_payload(raw)
    if parsed is None:
        raise ValueError(f"Failed to parse JSON payload from response: {raw[:200]}")
    return parsed


# ── Vision & Photo Sorting Engine ─────────────────────────────────────────────
async def ask_ai_vision(
    prompt: str,
    image_urls: list[str],
    system_prompt: str = "",
    max_tokens: int = 1500,
    temperature: float = 0.2,
    expect_json: bool = False,
) -> str:
    """
    Unified entry point for multimodal Vision calls across Murasaki LeadRadar.
    Reads VISION_MODELS_CHAIN from .env and tries models strictly in order.
    Automatically handles rate limiting, timeouts, and transparent fallbacks.
    """
    await rate_limiter.check_and_increment()

    timeout = 20.0
    valid_images = [u.strip() for u in image_urls if u and isinstance(u, str) and u.strip().startswith("http")]

    # Build multimodal OpenAI messages payload
    user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt.strip()}]
    for u in valid_images:
        user_content.append({"type": "image_url", "image_url": {"url": u}})

    messages: list[dict[str, Any]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": user_content})

    chain = get_vision_models_chain()
    errors_encountered: list[str] = []

    for provider_id, model_id in chain:
        prov_cfg = _get_provider_config(provider_id)
        if not prov_cfg:
            logger.debug("AI Router Vision: Skipping %s [%s] (provider not configured with API key)", provider_id, model_id)
            continue

        client = get_openai_client(
            provider_name=provider_id,
            base_url=prov_cfg["base_url"],
            api_key=prov_cfg["api_key"],
            timeout=timeout,
            extra_headers=prov_cfg["extra_headers"],
        )

        try:
            logger.info(
                "AI Router Vision: Trying %s [model=%s, images=%d, timeout=%ss]...",
                prov_cfg["name"], model_id, len(valid_images), timeout
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout,
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""
                trimmed = content.strip()
                if not trimmed:
                    err_msg = f"{prov_cfg['name']} ({model_id}) returned empty vision response"
                    logger.warning("AI Router Vision fallback: %s -> switching to next model in chain", err_msg)
                    errors_encountered.append(err_msg)
                    continue

                if expect_json:
                    parsed = extract_json_payload(trimmed)
                    if parsed is None:
                        err_msg = f"{prov_cfg['name']} ({model_id}) returned invalid JSON payload for vision task"
                        logger.warning("AI Router Vision fallback: %s -> switching to next model in chain", err_msg)
                        errors_encountered.append(err_msg)
                        log_event_bg("ai_router", err_msg, level="WARNING", details={"model": model_id, "reason": "invalid_json"})
                        continue

                logger.info(
                    "AI Router Vision: %s [%s] successfully processed %d images (%d chars)",
                    prov_cfg["name"], model_id, len(valid_images), len(trimmed)
                )
                return trimmed

        except asyncio.TimeoutError:
            err_msg = f"{prov_cfg['name']} ({model_id}) timed out after {timeout}s"
            logger.warning("AI Router Vision fallback: %s -> switching to next model in chain", err_msg)
            errors_encountered.append(err_msg)
            log_event_bg("ai_router", err_msg, level="WARNING", details={"task_type": "vision", "model": model_id, "reason": "timeout"})
            continue

        except Exception as exc:
            err_msg = f"{prov_cfg['name']} ({model_id}) error: {type(exc).__name__}: {exc}"
            logger.warning("AI Router Vision fallback: %s -> switching to next model in chain", err_msg)
            errors_encountered.append(err_msg)
            log_event_bg("ai_router", err_msg, level="WARNING", details={"task_type": "vision", "model": model_id, "error": str(exc)})
            continue

    all_errs = "; ".join(errors_encountered) if errors_encountered else "Все Vision-провайдеры отключены или не настроены"
    logger.error("AI Router Vision: All vision providers failed. Errors: %s", all_errs)
    log_event_bg("ai_router", "All vision providers failed", level="ERROR", details={"errors": errors_encountered})
    raise AllProvidersFailedError(f"Vision-нейросети временно недоступны: {all_errs}")


async def sort_business_photos(
    photo_urls: list[str],
    business_category: str = "",
    business_name: str = "",
) -> dict[str, Any]:
    """
    Intelligently sorts and categorizes lead photos for landing pages using Vision AI models from VISION_MODELS_CHAIN.
    Returns: {"hero": str | None, "gallery": list[str], "logo": str | None, "rejected": list[str]}
    Gracefully falls back to heuristic curation if Vision models fail or are unconfigured.
    """
    valid_photos = [p for p in photo_urls if isinstance(p, str) and p.startswith("http")]
    if not valid_photos:
        return {"hero": None, "gallery": [], "logo": None, "rejected": []}

    if len(valid_photos) == 1:
        return {"hero": valid_photos[0], "gallery": [valid_photos[0]], "logo": None, "rejected": []}

    prompt = (
        f"Ты — профессиональный арт-директор и UI/UX дизайнер современных конверсионных сайтов.\n"
        f"Проанализируй предоставленные фотографии компании «{business_name or 'Бизнес'}» (сфера: {business_category or 'Сфера услуг'}).\n\n"
        "Твоя задача — рассортировать их по категориям для посадочной страницы:\n"
        "1. 'hero': 1 самый качественный, эффектный и привлекательный кадр для первого экрана "
        "(красивый фасад, стильный интерьер, флагманский продукт или рабочий процесс специалиста).\n"
        "2. 'gallery': список до 6 качественных фотографий для блока галереи/портфолио "
        "(разные ракурсы, детали интерьера, примеры работ, оборудование).\n"
        "3. 'logo': URL фотографии, если на ней изображен чистый логотип компании или брендовая вывеска (иначе null).\n"
        "4. 'rejected': список URL размытых, слишком темных, нерелевантных фото или скриншотов чеков/документов.\n\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "- Используй ТОЛЬКО переданные ссылки. Не придумывай чужие URL.\n"
        "- Верни СТРОГО валидный JSON без лишних пояснений:\n"
        '{"hero": "url", "gallery": ["url1", "url2"], "logo": null, "rejected": []}'
    )

    try:
        raw_json = await ask_ai_vision(
            prompt=prompt,
            image_urls=valid_photos[:10],
            system_prompt="Отвечай строго в формате JSON без markdown разметки и пояснений.",
            max_tokens=1000,
            temperature=0.2,
            expect_json=True,
        )
        parsed = extract_json_payload(raw_json)
        if isinstance(parsed, dict) and "hero" in parsed and "gallery" in parsed:
            hero = parsed.get("hero") if parsed.get("hero") in valid_photos else valid_photos[0]
            raw_gallery = parsed.get("gallery") or []
            gallery = [p for p in raw_gallery if p in valid_photos and p != hero][:6]
            if not gallery:
                gallery = [p for p in valid_photos if p != hero][:4] or [hero]

            logo = parsed.get("logo") if parsed.get("logo") in valid_photos else None
            rejected = [p for p in (parsed.get("rejected") or []) if p in valid_photos]

            logger.info("Vision photo sorting succeeded: hero=%s, gallery_count=%d", hero, len(gallery))
            return {
                "hero": hero,
                "gallery": gallery,
                "logo": logo,
                "rejected": rejected,
            }
    except Exception as exc:
        logger.warning("Vision photo sorting unavailable or failed (%s). Using deterministic heuristic fallback.", exc)

    # Deterministic heuristic fallback
    hero = valid_photos[0]
    remaining = [p for p in valid_photos[1:7] if p != hero]
    return {
        "hero": hero,
        "gallery": remaining if remaining else [hero],
        "logo": None,
        "rejected": [],
    }


# ── Diagnostics & Provider Status ─────────────────────────────────────────────
def get_ai_router_stats() -> dict[str, Any]:
    """Returns active rate limiter usage and configured provider statuses."""
    stats = rate_limiter.get_stats()
    stats["providers"] = {
        "groq": bool(settings.groq_api_key or os.getenv("GROQ_API_KEY")),
        "openrouter": bool(settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")),
        "gemini": bool(settings.gemini_api_key or os.getenv("GEMINI_API_KEY")),
        "mxr": bool(
            settings.mxr_api_key
            or os.getenv("MXR_API_KEY")
            or settings.openai_api_key
            or os.getenv("OPENAI_API_KEY")
        ),
    }
    stats["text_models_chain"] = [f"{p}:{m}" for p, m in get_text_models_chain()]
    stats["vision_models_chain"] = [f"{p}:{m}" for p, m in get_vision_models_chain()]
    stats["proxy_configured"] = bool(_get_proxy_url())
    return stats
