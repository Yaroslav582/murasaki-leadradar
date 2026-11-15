"""
Proxy module exposing app.services.ai_router as services.ai_router
"""
from app.services.ai_router import (
    ask_ai,
    get_ai_router_stats,
    get_task_chain,
    rate_limiter,
    AIRateLimiter,
    AIQuotaExceededError,
    AllProvidersFailedError,
)

__all__ = [
    "ask_ai",
    "get_ai_router_stats",
    "get_task_chain",
    "rate_limiter",
    "AIRateLimiter",
    "AIQuotaExceededError",
    "AllProvidersFailedError",
]
