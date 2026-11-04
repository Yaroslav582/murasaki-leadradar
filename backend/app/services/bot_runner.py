from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WEB_APP_URL = "https://frontend-mocha-three-gfa8fzsldf.vercel.app"

WELCOME_TEXT = (
    "👋 **Добро пожаловать в Murasaki LeadRadar!**\n\n"
    "🚀 **Ваш личный радар заказов и AI-ассистент:**\n"
    "• Мониторинг заказов с бирж **Kwork** и **FL.ru** в реальном времени\n"
    "• Радар Telegram-каналов и чатов фриланса\n"
    "• Умные вежливые отклики от нейросети (MXR gpt-6-sol)\n"
    "• Автопостинг промо с портфолио по расписанию\n\n"
    "👇 Нажмите кнопку ниже, чтобы открыть Mini App прямо в Telegram:"
)


class TelegramBotRunner:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not settings.telegram_bot_token:
            logger.info("Bot runner: no TELEGRAM_BOT_TOKEN set.")
            return
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _poll_loop(self) -> None:
        token = settings.telegram_bot_token
        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0
        logger.info("Starting Telegram Bot long-polling loop for @%s", getattr(settings, "telegram_bot_username", "bot"))

        async with httpx.AsyncClient(timeout=35) as client:
            while self._running:
                try:
                    resp = await client.get(
                        f"{base_url}/getUpdates",
                        params={"offset": offset, "timeout": 20},
                    )
                    if resp.status_code != 200:
                        await asyncio.sleep(3)
                        continue

                    data = resp.json()
                    updates = data.get("result", [])
                    for update in updates:
                        update_id = update.get("update_id", 0)
                        offset = max(offset, update_id + 1)

                        msg = update.get("message")
                        if not msg:
                            continue

                        chat_id = msg.get("chat", {}).get("id")
                        text = (msg.get("text") or "").strip()

                        if text.startswith("/start"):
                            await client.post(
                                f"{base_url}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": WELCOME_TEXT,
                                    "parse_mode": "Markdown",
                                    "reply_markup": {
                                        "inline_keyboard": [
                                            [
                                                {
                                                    "text": "🚀 Открыть LeadRadar Mini App",
                                                    "web_app": {"url": WEB_APP_URL},
                                                }
                                            ],
                                            [
                                                {
                                                    "text": "💼 Портфолио Murasaki",
                                                    "url": "https://murasaki-portfolio.vercel.app/",
                                                }
                                            ],
                                        ]
                                    },
                                },
                            )
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("Bot poll error (retrying): %s", exc)
                    await asyncio.sleep(2)


bot_runner = TelegramBotRunner()
