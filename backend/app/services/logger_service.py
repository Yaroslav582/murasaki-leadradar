from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.db import SessionLocal
from app.models import SystemLog

logger = logging.getLogger(__name__)


async def log_system_event(
    module: str,
    message: str,
    level: str = "INFO",
    details: dict[str, Any] | None = None,
) -> None:
    """Persists a structured log event into the Supabase system_logs table."""
    try:
        async with SessionLocal() as session:
            entry = SystemLog(
                level=level.upper(),
                module=module,
                message=message,
                details=details or {},
            )
            session.add(entry)
            await session.commit()
    except Exception as exc:
        logger.debug("Failed to write to Supabase system_logs: %s", exc)


def log_event_bg(
    module: str,
    message: str,
    level: str = "INFO",
    details: dict[str, Any] | None = None,
) -> None:
    """Non-blocking background helper for logging to Supabase."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(log_system_event(module, message, level, details))
    except RuntimeError:
        pass
