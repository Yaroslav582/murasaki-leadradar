"""
Proxy module exposing app.services.ai_router as services.ai_router
"""
from app.config import DEFAULT_TEXT_MODELS_CHAIN, DEFAULT_VISION_MODELS_CHAIN
from app.services.ai_router import (
    AIRateLimiter,
    AIQuotaExceededError,
    AllProvidersFailedError,
    ask_ai,
    ask_ai_json,
    ask_ai_vision,
    extract_json_payload,
    generate_demo_json,
    get_ai_router_stats,
    get_task_chain,
    get_text_models_chain,
    get_vision_models_chain,
    parse_model_chain,
    rate_limiter,
    sort_business_photos,
)

__all__ = [
    "DEFAULT_TEXT_MODELS_CHAIN",
    "DEFAULT_VISION_MODELS_CHAIN",
    "AIRateLimiter",
    "AIQuotaExceededError",
    "AllProvidersFailedError",
    "ask_ai",
    "ask_ai_json",
    "ask_ai_vision",
    "extract_json_payload",
    "generate_demo_json",
    "get_ai_router_stats",
    "get_task_chain",
    "get_text_models_chain",
    "get_vision_models_chain",
    "parse_model_chain",
    "rate_limiter",
    "sort_business_photos",
]
