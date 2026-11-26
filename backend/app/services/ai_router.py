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
    Distributes photos into 3 key categories:
      - hero_product: close-up shots of works, products, food, procedures (used for hero screen and portfolio gallery)
      - interior: premises, facade, atmosphere, indoor design
      - trash: screenshots of chats, price lists with text, documents, blurry/unfitting photos (discarded)
    """
    valid_photos = [p for p in photo_urls if isinstance(p, str) and p.startswith("http")]
    if not valid_photos:
        return {
            "hero_product": [],
            "interior": [],
            "trash": [],
            "hero": None,
            "gallery": [],
            "logo": None,
            "rejected": [],
        }

    if len(valid_photos) == 1:
        single = valid_photos[0]
        return {
            "hero_product": [single],
            "interior": [],
            "trash": [],
            "hero": single,
            "gallery": [single],
            "logo": None,
            "rejected": [],
        }

    prompt = (
        f"Ты — профессиональный арт-директор и UI/UX дизайнер современных конверсионных сайтов.\n"
        f"Проанализируй предоставленные фотографии компании «{business_name or 'Бизнес'}» (сфера: {business_category or 'Сфера услуг'}).\n\n"
        "Твоя задача — рассортировать переданные фотографии строго по 3 категориям:\n"
        "1. 'hero_product': крупные планы работ, товаров, блюд, процедур, готовых результатов "
        "(идеально для главного экрана и галереи работ).\n"
        "2. 'interior': помещение, фасад, ресепшн, зона ожидания, общая атмосфера и оборудование.\n"
        "3. 'trash': скриншоты переписок, прайс-листы с текстом, чеки, размытые, некачественные или нерелевантные фото (не показываем на сайте).\n\n"
        "СТРОГИЕ ПРАВИЛА:\n"
        "- Используй ТОЛЬКО переданные URL, строго без выдумывания сторонних ссылок.\n"
        "- Верни СТРОГО валидный JSON без дополнительного текста:\n"
        '{\n'
        '  "hero_product": ["url1", "url2"],\n'
        '  "interior": ["url3", "url4"],\n'
        '  "trash": ["url_trash"]\n'
        '}'
    )

    try:
        raw_json = await ask_ai_vision(
            prompt=prompt,
            image_urls=valid_photos[:12],
            system_prompt="Отвечай строго в формате JSON без markdown разметки и пояснений.",
            max_tokens=1000,
            temperature=0.2,
            expect_json=True,
        )
        parsed = extract_json_payload(raw_json)
        if isinstance(parsed, dict) and ("hero_product" in parsed or "hero" in parsed or "interior" in parsed):
            raw_hp = parsed.get("hero_product") or []
            if not raw_hp and parsed.get("hero"):
                raw_hp = [parsed["hero"]] + (parsed.get("gallery") or [])

            raw_int = parsed.get("interior") or []
            raw_trash = parsed.get("trash") or parsed.get("rejected") or []

            hero_product = [p for p in raw_hp if p in valid_photos]
            interior = [p for p in raw_int if p in valid_photos and p not in hero_product]
            trash = [p for p in raw_trash if p in valid_photos]

            # If classification was empty, populate from remaining valid photos
            unassigned = [p for p in valid_photos if p not in hero_product and p not in interior and p not in trash]
            if not hero_product and unassigned:
                hero_product.append(unassigned.pop(0))
            if not interior and unassigned:
                interior.extend(unassigned)

            hero = hero_product[0] if hero_product else (interior[0] if interior else valid_photos[0])
            gallery = (hero_product[1:] + interior)[:6]
            if not gallery:
                gallery = [hero]

            logger.info("Vision photo sorting succeeded: hero_product=%d, interior=%d, trash=%d", len(hero_product), len(interior), len(trash))
            return {
                "hero_product": hero_product,
                "interior": interior,
                "trash": trash,
                "hero": hero,
                "gallery": gallery,
                "logo": parsed.get("logo") if parsed.get("logo") in valid_photos else None,
                "rejected": trash,
            }
    except Exception as exc:
        logger.warning("Vision photo sorting unavailable or failed (%s). Using deterministic heuristic fallback.", exc)

    # Deterministic heuristic fallback
    hero = valid_photos[0]
    gallery = [p for p in valid_photos[1:7] if p != hero]
    return {
        "hero_product": [hero] + gallery[:2],
        "interior": gallery[2:],
        "trash": [],
        "hero": hero,
        "gallery": gallery if gallery else [hero],
        "logo": None,
        "rejected": [],
    }


async def generate_demo_json(
    lead_dict: dict[str, Any],
    hero_photos: list[str],
    interior_photos: list[str],
    requested_style: str | None = None,
) -> dict[str, Any]:
    """
    Generates structured JSON content for a business landing page using TEXT_MODELS_CHAIN.
    Enforces DESIGN.md tokens and design language from VoltAgent/awesome-design-md.
    """
    from app.services.design_systems import STYLES_CATALOG, build_llm_design_context, resolve_style_id

    name = lead_dict.get("name") or "Компания"
    category = lead_dict.get("category") or "Сфера услуг"
    city = lead_dict.get("city") or "Россия"
    address = lead_dict.get("address") or ""
    raw_rating = lead_dict.get("rating") or 4.9
    try:
        rating = round(float(raw_rating), 1)
    except (TypeError, ValueError):
        rating = 4.9
    reviews_count = int(lead_dict.get("reviews_count") or 18)

    # Determine canonical style and template_id
    effective_style = resolve_style_id(requested_style, category)
    suggested_template = effective_style
    design_context = build_llm_design_context(effective_style, category)

    valid_templates = tuple(STYLES_CATALOG.keys())

    system_prompt = (
        "Ты — редактор сайтов для малого бизнеса (как в лучших студиях: пишешь просто, по делу и по-человечески).\n"
        "Твоя задача — составить живые, приземлённые тексты для полноценного 9-секционного сайта компании.\n\n"
        f"{design_context}\n\n"
        "СТРОГИЕ ПРАВИЛА (ЧТОБЫ НЕ БЫЛО ПОХОЖЕ НА НЕЙРОСЕТЬ):\n"
        "1. ЗАПРЕЩЕНЫ любые ИИ-штампы и вода: 'премиальный сервис', 'индивидуальный подход', 'широкий спектр', "
        "'команда профессионалов', 'высочайшее качество', 'современное оборудование', 'уютная атмосфера', "
        "'синергия', 'забота о каждом клиенте', 'оптимальное решение', 'под ключ'.\n"
        "2. Пиши как живой человек: коротко, конкретно, с фактами (что делаем, сколько стоит, где находимся, как записаться). "
        "Без восклицательных знаков и без эмодзи.\n"
        "3. В services укажи 6–8 РЕАЛЬНЫХ конкретных услуг этой ниши, разбитых на 2–3 понятные категории (поле 'category', например 'Популярное', 'Комплексы', 'Дополнительно'), с реалистичными ценами в рублях (например '1 800 ₽' или 'от 2 500 ₽').\n"
        "4. В reviews сгенерируй 3 реалистичных отзыва на основе ниши и рейтинга точки (разной длины, живым разговорным языком, с обычными именами).\n"
        "5. В faq дай 4–5 реальных вопросов (запись, оплата, гарантия, парковка/адрес).\n"
        f"6. Выбери template_id строго: '{suggested_template}'.\n"
        "7. Верни СТРОГО валидный JSON следующей структуры, без markdown-обёртки:\n"
        "{\n"
        f'  "template_id": "{suggested_template}",\n'
        '  "hero_title": "Короткий понятный заголовок: что это за место и чем занимается (до 7 слов)",\n'
        '  "hero_subtitle": "Одно спокойное предложение с адресом/районом и главным удобством для клиента",\n'
        '  "facts": [\n'
        f'    {{"value": "{rating} ★", "label": "Рейтинг на картах"}},\n'
        f'    {{"value": "{reviews_count}+", "label": "Отзывов клиентов"}},\n'
        '    {"value": "100%", "label": "Гарантия на работы"},\n'
        '    {"value": "10 мин", "label": "Среднее время ответа"}\n'
        '  ],\n'
        '  "usp_list": [\n'
        '    {"title": "Короткий факт 1", "desc": "Пояснение в 1 простое предложение"},\n'
        '    {"title": "Короткий факт 2", "desc": "Пояснение в 1 простое предложение"},\n'
        '    {"title": "Короткий факт 3", "desc": "Пояснение в 1 простое предложение"}\n'
        '  ],\n'
        '  "services": [\n'
        '    {"category": "Популярное", "name": "Услуга 1", "price": "1 500 ₽", "desc": "Что входит"},\n'
        '    {"category": "Популярное", "name": "Услуга 2", "price": "2 200 ₽", "desc": "Что входит"},\n'
        '    {"category": "Популярное", "name": "Услуга 3", "price": "2 800 ₽", "desc": "Что входит"},\n'
        '    {"category": "Комплексы", "name": "Услуга 4", "price": "4 200 ₽", "desc": "Что входит"},\n'
        '    {"category": "Комплексы", "name": "Услуга 5", "price": "5 500 ₽", "desc": "Что входит"},\n'
        '    {"category": "Дополнительно", "name": "Услуга 6", "price": "от 900 ₽", "desc": "Что входит"}\n'
        '  ],\n'
        '  "promo": {\n'
        '    "badge": "Спецпредложение",\n'
        '    "title": "Скидка 15% на первый визит",\n'
        '    "desc": "Действует при записи через сайт на любую основную услугу.",\n'
        '    "cta": "Забрать бонус"\n'
        '  },\n'
        '  "reviews": [\n'
        '    {"author": "Алексей М.", "date": "Недавно", "rating": 5, "text": "Конкретный короткий отзыв по делу."},\n'
        '    {"author": "Ирина К.", "date": "2 недели назад", "rating": 5, "text": "Живой отзыв без штампов."},\n'
        '    {"author": "Дмитрий В.", "date": "Месяц назад", "rating": 5, "text": "Отзыв с упоминанием результата."}\n'
        '  ],\n'
        '  "faq": [\n'
        '    {"question": "Как записаться?", "answer": "Короткий прямой ответ."},\n'
        '    {"question": "Как оплатить?", "answer": "Короткий прямой ответ."},\n'
        '    {"question": "Есть ли гарантия?", "answer": "Короткий прямой ответ."},\n'
        '    {"question": "Где вы находитесь и есть ли парковка?", "answer": "Короткий прямой ответ."}\n'
        '  ]\n'
        "}"
    )

    user_prompt = (
        f"Компания: «{name}»\n"
        f"Сфера бизнеса: {category}\n"
        f"Город: {city}\n"
        f"Адрес: {address or 'Центр города'}\n"
        f"Рейтинг: {rating}★ ({reviews_count} отзывов на картах)\n\n"
        f"Выбранный стиль сайта (DESIGN.md): {effective_style}\n\n"
        "Сгенерируй продающий JSON для лендинга:"
    )

    fallback = _build_niche_fallback(
        name=name,
        category=category,
        city=city,
        address=address,
        rating=rating,
        reviews_count=reviews_count,
        template_id=suggested_template,
    )

    try:
        raw_res = await ask_ai(
            user_prompt,
            system_prompt=system_prompt,
            task_type="smart",
            max_tokens=2200,
            temperature=0.6,
            expect_json=True,
        )
        parsed = extract_json_payload(raw_res)
        if isinstance(parsed, dict) and "hero_title" in parsed and "services" in parsed:
            t_id = parsed.get("template_id")
            if t_id not in valid_templates:
                parsed["template_id"] = suggested_template
            # Fill any missing 9-section fields from niche fallback
            for key in ("facts", "usp_list", "promo", "reviews", "faq"):
                if not parsed.get(key):
                    parsed[key] = fallback[key]
            if len(parsed.get("services") or []) < 4:
                parsed["services"] = fallback["services"]
            return parsed
    except Exception as exc:
        logger.warning("AI landing JSON generation notice: %s. Using deterministic niche profile.", exc)

    return fallback


def _build_niche_fallback(
    *,
    name: str,
    category: str,
    city: str,
    address: str,
    rating: float,
    reviews_count: int,
    template_id: str,
) -> dict[str, Any]:
    """Build realistic 9-section fallback content tailored by niche without AI cliches."""
    cat_l = category.lower()
    place_label = address or city
    common_facts = [
        {"value": f"{rating} ★", "label": "Рейтинг на картах"},
        {"value": f"{reviews_count}+", "label": "Отзывов клиентов"},
        {"value": "100%", "label": "Фиксированная смета"},
        {"value": "10 мин", "label": "Ответ в мессенджере"},
    ]

    if any(k in cat_l for k in ("барбер", "стриж", "парикмах")):
        return {
            "template_id": template_id,
            "hero_title": f"{name} — мужские стрижки и бритьё",
            "hero_subtitle": f"Работаем по адресу {place_label}. Запись на удобное время без звонков.",
            "facts": common_facts,
            "usp_list": [
                {"title": "Чётко по времени", "desc": "Начинаем строго по записи, без живой очереди."},
                {"title": "Фиксированный прайс", "desc": "Мытьё головы и укладка уже входят в стоимость стрижки."},
                {"title": "Удобное расположение", "desc": f"Находимся по адресу {place_label}, есть парковка рядом."},
            ],
            "services": [
                {"category": "Популярное", "name": "Мужская стрижка", "price": "1 600 ₽", "desc": "Мытьё головы, стрижка, укладка стайлингом."},
                {"category": "Популярное", "name": "Стрижка бороды и усов", "price": "1 100 ₽", "desc": "Моделирование формы, бритьё опасной бритвой."},
                {"category": "Популярное", "name": "Стрижка машинкой", "price": "1 000 ₽", "desc": "Под одну или несколько насадок, окантовка."},
                {"category": "Комплексы", "name": "Стрижка + борода", "price": "2 400 ₽", "desc": "Полный уход за один визит (~75 минут)."},
                {"category": "Комплексы", "name": "Отец + сын", "price": "2 500 ₽", "desc": "Две стрижки в одно время по выгодной цене."},
                {"category": "Дополнительно", "name": "Детская стрижка", "price": "1 200 ₽", "desc": "Для мальчиков до 12 лет."},
                {"category": "Дополнительно", "name": "Тонирование бороды", "price": "900 ₽", "desc": "Выравнивание цвета без эффекта окрашивания."},
            ],
            "promo": {
                "badge": "Первый визит",
                "title": "Скидка 20% на первое посещение",
                "desc": "Действует на мужскую стрижку или комплекс «стрижка + борода» при записи через сайт.",
                "cta": "Забрать бонус",
            },
            "reviews": [
                {"author": "Артём С.", "date": "3 дня назад", "rating": 5, "text": "Хожу сюда уже полгода. Мастера слушают, как надо, а не стригут под копирку. Удобно, что рядом с домом."},
                {"author": "Максим В.", "date": "2 недели назад", "rating": 5, "text": "Записался за 2 часа до приёма, приняли ровно вовремя. Стрижкой и бородой доволен, прайс адекватный."},
                {"author": "Егор П.", "date": "Месяц назад", "rating": 5, "text": "Чисто, хороший кофе, мастер работает аккуратно и быстро. Рекомендую."},
            ],
            "faq": [
                {"question": "Можно прийти без записи?", "answer": "Лучше записаться заранее в мессенджере, но если есть свободный мастер — примем сразу."},
                {"question": "Что входит в стоимость стрижки?", "answer": "Мытьё головы до и после, сама стрижка, окантовка и укладка профессиональным стайлингом."},
                {"question": "Как оплатить?", "answer": "Наличными, банковской картой или переводом по СБП после стрижки."},
                {"question": "Где вы находитесь и есть ли парковка?", "answer": f"Мы находимся по адресу {place_label}, у входа есть бесплатная парковка."},
            ],
        }
    if any(k in cat_l for k in ("бьюти", "салон", "маникюр", "косметол", "красот", "ресниц", "бров")):
        return {
            "template_id": template_id,
            "hero_title": f"{name} — студия красоты",
            "hero_subtitle": f"Маникюр, уход и запись онлайн. Ждём вас по адресу {place_label}.",
            "facts": common_facts,
            "usp_list": [
                {"title": "Стерильный инструмент", "desc": "Крафт-пакеты вскрываются при вас перед процедурой."},
                {"title": "Запись в 2 клика", "desc": "Подберём удобное окно в WhatsApp или Telegram."},
                {"title": "Гарантия на покрытие", "desc": "Бесплатно поправим скол в течение 5 дней после визита."},
            ],
            "services": [
                {"category": "Популярное", "name": "Маникюр + гель-лак", "price": "2 200 ₽", "desc": "Снятие, маникюр, выравнивание и покрытие в один тон."},
                {"category": "Популярное", "name": "Педикюр с покрытием", "price": "2 900 ₽", "desc": "Обработка стоп, пальчиков и стойкое покрытие."},
                {"category": "Популярное", "name": "Оформление и окрашивание бровей", "price": "1 400 ₽", "desc": "Коррекция воском/пинцетом и краска или хна."},
                {"category": "Комплексы", "name": "Маникюр + педикюр в 4 руки", "price": "4 600 ₽", "desc": "Экономия времени — оба мастера работают одновременно."},
                {"category": "Комплексы", "name": "Брови + ламинирование ресниц", "price": "3 200 ₽", "desc": "Выразительный взгляд до 6 недель без туши."},
                {"category": "Дополнительно", "name": "Укладка / уход за волосами", "price": "от 2 000 ₽", "desc": "Подбор состава и укладка на выход."},
                {"category": "Дополнительно", "name": "Снятие покрытия без последующего", "price": "600 ₽", "desc": "Аккуратное снятие, опил формы и уходовое масло."},
            ],
            "promo": {
                "badge": "Спецпредложение",
                "title": "Снятие покрытия в подарок на первый визит",
                "desc": "Забронируйте время на маникюр или комплекс через форму на сайте и получите снятие бесплатно.",
                "cta": "Забрать бонус",
            },
            "reviews": [
                {"author": "Анна К.", "date": "5 дней назад", "rating": 5, "text": "Покрытие держится 4 недели без единого скола. Инструменты открывают при мне, очень уютная студия."},
                {"author": "Марина Л.", "date": "2 недели назад", "rating": 5, "text": "Делала комплекс маникюр+педикюр в 4 руки — всё заняло меньше двух часов. Отдельное спасибо мастеру бровисту."},
                {"author": "Елена Д.", "date": "Месяц назад", "rating": 5, "text": "Удобно записываться через WhatsApp, всегда находят окно даже вечером после работы."},
            ],
            "faq": [
                {"question": "За сколько дней лучше записываться?", "answer": "На будни обычно есть окна за 1–2 дня, на выходные лучше писать за 3–4 дня."},
                {"question": "Как обрабатываются инструменты?", "answer": "Все инструменты проходят дезинфекцию и стерилизацию в сухожаре, крафт-пакет вскрывается при вас."},
                {"question": "Есть ли гарантия на маникюр?", "answer": "Да, даём гарантию 5 дней — при любом сколе переделаем ноготь бесплатно."},
                {"question": "Где вы находитесь?", "answer": f"Адрес: {place_label}. Подскажем точный вход и код домофона при записи."},
            ],
        }
    if any(k in cat_l for k in ("авто", "сто", "шиномонт", "детейл", "мойк")):
        return {
            "template_id": template_id,
            "hero_title": f"{name} — автосервис и диагностика",
            "hero_subtitle": f"Честная оценка стоимости до начала работ. Адрес: {place_label}.",
            "facts": common_facts,
            "usp_list": [
                {"title": "Согласуем цену заранее", "desc": "Не меняем смету в процессе без вашего подтверждения."},
                {"title": "Запчасти в наличии и под заказ", "desc": "Подберём оригинал или проверенный аналог под бюджет."},
                {"title": "Фотоотчёт в мессенджер", "desc": "Покажем изношенные узлы до замены, если нет времени ждать в боксе."},
            ],
            "services": [
                {"category": "Популярное", "name": "Компьютерная диагностика", "price": "от 1 200 ₽", "desc": "Чтение ошибок, проверка основных блоков и датчиков."},
                {"category": "Популярное", "name": "Замена масла и фильтров", "price": "от 1 500 ₽", "desc": "Работа + осмотр ходовой части на подъёмнике."},
                {"category": "Популярное", "name": "Сезонный шиномонтаж", "price": "от 2 400 ₽", "desc": "Снятие, переобувка и балансировка всех 4 колёс."},
                {"category": "Комплексы", "name": "Полное ТО автомобиля", "price": "от 4 500 ₽", "desc": "Масло, все фильтры, диагностика подвески и тормозов."},
                {"category": "Комплексы", "name": "Диагностика перед покупкой", "price": "3 500 ₽", "desc": "Проверка кузова толщиномером, двигателя и ходовой."},
                {"category": "Дополнительно", "name": "Ремонт подвески", "price": "от 2 000 ₽", "desc": "Замена рычагов, стоек, сайлентблоков и шаровых."},
                {"category": "Дополнительно", "name": "Заправка автокондиционера", "price": "2 500 ₽", "desc": "Вакуумирование системы и заправка фреоном."},
            ],
            "promo": {
                "badge": "Акция сервиса",
                "title": "Бесплатный осмотр ходовой при замене масла",
                "desc": "Запишитесь на удобный день через сайт — проверим подвеску и тормозную систему на подъёмнике за 0 ₽.",
                "cta": "Забрать бонус",
            },
            "reviews": [
                {"author": "Сергей Н.", "date": "4 дня назад", "rating": 5, "text": "Приехал на стук в подвеске, сразу подняли машину и показали люфт. Цену назвали до ремонта, ничего лишнего не навязали."},
                {"author": "Игорь Т.", "date": "2 недели назад", "rating": 5, "text": "Менял масло и колодки, скинули фото старых деталей в WhatsApp. Быстро и по делу."},
                {"author": "Виктор К.", "date": "Месяц назад", "rating": 5, "text": "Отличные ребята, помогли оперативно найти редкую запчасть и всё поставили в тот же день."},
            ],
            "faq": [
                {"question": "Можно ли со своими запчастями?", "answer": "Да, без проблем. Либо подберём нужные детали сами по VIN."},
                {"question": "Даёте ли гарантию на работы?", "answer": "Да, предоставляем гарантию на выполненные работы и заказ-наряд."},
                {"question": "Сколько длится ТО?", "answer": "Стандартное ТО занимает около 1–1,5 часов, можно подождать в клиентской зоне."},
                {"question": "Как к вам заехать?", "answer": f"Боксы находятся по адресу {place_label}, есть удобный заезд с улицы."},
            ],
        }
    if any(k in cat_l for k in ("кафе", "ресторан", "кофе", "пекар", "пицц", "суши", "бар")):
        return {
            "template_id": template_id,
            "hero_title": f"{name} — кухня и напитки",
            "hero_subtitle": f"Свежие блюда каждый день, бронь столов и самовывоз. {place_label}.",
            "facts": common_facts,
            "usp_list": [
                {"title": "Готовим из-под ножа", "desc": "Не используем заморозку для основных блюд."},
                {"title": "Быстрая бронь стола", "desc": "Забронируйте место на вечер в пару сообщений."},
                {"title": "Удобно зайти рядом", "desc": f"Находимся по адресу {place_label}."},
            ],
            "services": [
                {"category": "Популярное", "name": "Фирменный завтрак / сет", "price": "590 ₽", "desc": "Подаётся с горячим напитком до 13:00."},
                {"category": "Популярное", "name": "Горячее блюдо дня", "price": "790 ₽", "desc": "Полноценная порция из сезонного меню."},
                {"category": "Популярное", "name": "Спешелти кофе", "price": "260 ₽", "desc": "Эспрессо, капучино, флэт уайт или раф."},
                {"category": "Комплексы", "name": "Бизнес-ланч (3 блюда)", "price": "690 ₽", "desc": "Суп, горячее, салат и напиток по будням с 12:00 до 16:00."},
                {"category": "Комплексы", "name": "Сет на двоих к ужину", "price": "2 100 ₽", "desc": "Два горячих блюда, закуска и два напитка."},
                {"category": "Дополнительно", "name": "Десерт с витрины", "price": "380 ₽", "desc": "Свежая выпечка собственного приготовления."},
                {"category": "Дополнительно", "name": "Заказ навынос", "price": "по меню", "desc": "Соберём к вашему приходу без ожидания."},
            ],
            "promo": {
                "badge": "Комплимент гостю",
                "title": "Десерт или кофе в подарок к первому заказу",
                "desc": "Забронируйте стол через сайт и покажите сообщение администратору.",
                "cta": "Забрать бонус",
            },
            "reviews": [
                {"author": "Ольга Р.", "date": "Вчера", "rating": 5, "text": "Очень вкусные завтраки и нормальный кофе, не пережжённый. Обслуживание быстрое, столики чистые."},
                {"author": "Дмитрий М.", "date": "Неделю назад", "rating": 5, "text": "Бронировали стол на компанию в пятницу — всё подали вовремя, порции большие."},
                {"author": "Алина Г.", "date": "3 недели назад", "rating": 5, "text": "Любимое место в районе, заходим перед работой за кофе и круассанами."},
            ],
            "faq": [
                {"question": "Как забронировать столик?", "answer": "Напишите в мессенджер или позвоните — подтвердим бронь за 2 минуты."},
                {"question": "Есть ли блюда с собой?", "answer": "Да, любое блюдо и напиток аккуратно упакуем навынос."},
                {"question": "Можно ли провести небольшой банкет?", "answer": "Да, подберём сет-меню для компании от 6 человек."},
                {"question": "Где вы находитесь?", "answer": f"Адрес: {place_label}. Удобный вход прямо с первой линии."},
            ],
        }

    return {
        "template_id": template_id,
        "hero_title": f"{name} — услуги в г. {city}",
        "hero_subtitle": f"Консультация, расчёт стоимости и запись по адресу {place_label}.",
        "facts": common_facts,
        "usp_list": [
            {"title": "Понятная стоимость", "desc": "Называем цену до начала работы, без скрытых доплат."},
            {"title": "Быстрая связь", "desc": "Отвечаем в WhatsApp и Telegram в течение 10 минут."},
            {"title": "Удобный график", "desc": f"Принимаем по адресу {place_label} по предварительной записи."},
        ],
        "services": [
            {"category": "Популярное", "name": "Первичная консультация", "price": "Бесплатно", "desc": "Оценка задачи и точный расчёт стоимости."},
            {"category": "Популярное", "name": "Базовая услуга", "price": "от 2 500 ₽", "desc": "Выполнение работы под вашу задачу в оговорённый срок."},
            {"category": "Популярное", "name": "Экспресс-решение", "price": "от 1 800 ₽", "desc": "Быстрое выполнение типовой задачи в день обращения."},
            {"category": "Комплексы", "name": "Комплексное обслуживание", "price": "от 4 900 ₽", "desc": "Полный цикл работ с проверкой результата."},
            {"category": "Комплексы", "name": "Сопровождение под ключ", "price": "от 7 500 ₽", "desc": "Расширенный пакет с приоритетной поддержкой."},
            {"category": "Дополнительно", "name": "Срочный выезд / приём", "price": "по запросу", "desc": "Оперативная помощь в день обращения."},
        ],
        "promo": {
            "badge": "Выгодный старт",
            "title": "Бесплатный расчёт и скидка 10% на первый заказ",
            "desc": "Оставьте заявку через форму на сайте, чтобы зафиксировать цену.",
            "cta": "Забрать бонус",
        },
        "reviews": [
            {"author": "Александр Б.", "date": "4 дня назад", "rating": 5, "text": "Всё сделали чётко в срок, цена не выросла ни на рубль от изначальной договорённости."},
            {"author": "Екатерина С.", "date": "2 недели назад", "rating": 5, "text": "Ответили в мессенджере за 5 минут, подробно объяснили, что нужно сделать и сколько это стоит."},
            {"author": "Павел Д.", "date": "Месяц назад", "rating": 5, "text": "Обращаюсь уже не первый раз — всегда стабильный результат без лишней суеты."},
        ],
        "faq": [
            {"question": "Как узнать точную стоимость?", "answer": "Напишите нам в мессенджер — сориентируем по цене за 5 минут."},
            {"question": "Как проходит запись и оплата?", "answer": "Выбираете удобный день в форме на сайте, оплата после согласования или по факту."},
            {"question": "Есть ли гарантия на услуги?", "answer": "Да, фиксируем условия и гарантируем результат по договору или чеку."},
            {"question": "Где вы находитесь?", "answer": f"Мы работаем по адресу: {place_label}."},
        ],
    }


async def refine_demo_html(
    current_html: str,
    user_instruction: str,
    style_id: str | None = None,
    category: str | None = None,
) -> str:
    """Apply targeted user prompt edits to existing demo HTML using fast Groq/TEXT_MODELS_CHAIN."""
    from app.services.design_systems import build_llm_design_context

    design_context = build_llm_design_context(style_id, category)
    system_prompt = (
        "Ты — Senior Frontend-разработчик и UX-редактор. "
        "Тебе дан готовый HTML лендинга и короткая правка от пользователя.\n"
        "ТВОЯ ЗАДАЧА: точечно изменить ТОЛЬКО то, что просит пользователь, полностью сохранив остальную вёрстку, "
        "CSS-переменные, OpenGraph/JSON-LD в <head>, табы прайса, FAQ-аккордеон, модалку записи и скрипт.\n"
        "Не пиши пояснений и не оборачивай в ```html — верни только полный готовый HTML от <!DOCTYPE html> до </html>.\n\n"
        f"{design_context}"
    )
    prompt = (
        f"ПОЖЕЛАНИЕ ПОЛЬЗОВАТЕЛЯ:\n{user_instruction.strip()}\n\n"
        f"ТЕКУЩИЙ HTML:\n{current_html[:32000]}"
    )

    raw_response: str | None = None
    groq_cfg = _get_provider_config("groq")
    if groq_cfg:
        for fast_model in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3-32b", "llama-3.3-70b-versatile"):
            try:
                client = get_openai_client(
                    provider_name="groq",
                    base_url=groq_cfg["base_url"],
                    api_key=groq_cfg["api_key"],
                    timeout=28.0,
                )
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=fast_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=8000,
                        temperature=0.35,
                    ),
                    timeout=28.0,
                )
                content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
                if content and ("<html" in content.lower() or "<!doctype" in content.lower()):
                    raw_response = content
                    break
            except Exception as exc:
                logger.debug("Groq refine model %s skipped: %s", fast_model, exc)

    if not raw_response:
        raw_response = await ask_ai(
            prompt=prompt,
            system_prompt=system_prompt,
            task_type="fast",
            max_tokens=7000,
            temperature=0.35,
        )

    cleaned = raw_response.strip()
    cleaned = re.sub(r"^```(?:html)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start_idx = cleaned.lower().find("<!doctype html")
    if start_idx == -1:
        start_idx = cleaned.lower().find("<html")
    if start_idx != -1:
        end_idx = cleaned.lower().rfind("</html>")
        if end_idx != -1:
            cleaned = cleaned[start_idx : end_idx + 7]
        else:
            cleaned = cleaned[start_idx:] + "\n</html>"
    if "<body" not in cleaned.lower():
        raise ValueError("Модель вернула неполный HTML при докрутке")
    return cleaned


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
