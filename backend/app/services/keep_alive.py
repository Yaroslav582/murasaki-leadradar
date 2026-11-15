from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class KeepAliveService:
    """Prevents cloud hosting (e.g. Render free tier) from sleeping by self-pinging every 8 minutes."""

    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("KeepAliveService started")

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("KeepAliveService stopped")

    async def _loop(self) -> None:
        # Resolve target ping URL
        target_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not target_url:
            public_url = getattr(settings, "public_base_url", "")
            if public_url and "localhost" not in public_url and "127.0.0.1" not in public_url:
                target_url = public_url
            else:
                target_url = "https://murasaki-leadradar-1.onrender.com"

        target_url = target_url.rstrip("/") + "/health"
        logger.info("KeepAlive target URL: %s", target_url)

        # Wait 30 seconds after startup before first ping
        await asyncio.sleep(30)

        while self._running:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(target_url)
                    logger.info("Keep-alive self-ping %s -> status %s", target_url, resp.status_code)
            except Exception as e:
                logger.debug("Keep-alive ping notice: %s", e)

            # Render free instances sleep after 15 min of inactivity.
            # We ping every 8 minutes (480 seconds) to keep it constantly awake.
            await asyncio.sleep(480)


keep_alive_service = KeepAliveService()
