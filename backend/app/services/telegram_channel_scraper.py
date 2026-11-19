from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import sample_user_agents

logger = logging.getLogger(__name__)

TG_URL_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,40})",
    re.I,
)
BG_IMAGE_REGEX = re.compile(r"url\(['\"]?(https?://[^'\")]+)['\"]?\)", re.I)

TG_SYSTEM_EXCLUDES = {
    "joinchat", "share", "addstickers", "proxy", "login", "setlanguage",
    "invoice", "giftcode", "addtheme", "bg", "c", "murasaki_radar_1438_bot",
}


def extract_tg_username(raw: str | None) -> str | None:
    """Extract clean public username from any TG link or handle."""
    if not raw:
        return None
    val = raw.strip()
    match = TG_URL_REGEX.search(val)
    if match:
        name = match.group(1).lstrip("@")
    else:
        name = val.lstrip("@").strip()

    if "/" in name or "?" in name or len(name) < 4:
        return None
    if name.lower() in TG_SYSTEM_EXCLUDES or name.lower().endswith("bot"):
        return None
    return name


async def scrape_telegram_channel(
    channel_url_or_username: str,
    limit_photos: int = 6,
) -> dict[str, Any]:
    """Lightweight web scraper for public Telegram channel (https://t.me/s/{username}).

    Extracts:
      - Channel avatar (.tgme_page_photo_image img or background-image)
      - Direct photo URLs from recent posts (.tgme_widget_message_photo_wrap)
    """
    username = extract_tg_username(channel_url_or_username)
    if not username:
        return {"avatar_url": None, "photos": []}

    target_url = f"https://t.me/s/{username}"
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None

    avatar_url: str | None = None
    photos: list[str] = []
    seen: set[str] = set()

    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(8.0),
            follow_redirects=True,
            proxy=proxy,
        ) as client:
            resp = await client.get(target_url)
            if resp.status_code != 200:
                logger.debug("TG preview for %s returned status %s", username, resp.status_code)
                return {"avatar_url": None, "photos": []}

            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. Channel avatar
            avatar_wrap = soup.select_one(".tgme_page_photo_image")
            if avatar_wrap:
                img_tag = avatar_wrap.find("img")
                if img_tag and img_tag.get("src"):
                    avatar_url = str(img_tag["src"]).strip()
                else:
                    style_attr = avatar_wrap.get("style", "")
                    bg_match = BG_IMAGE_REGEX.search(style_attr)
                    if bg_match:
                        avatar_url = bg_match.group(1).strip()

            # 2. Photos from recent messages (.tgme_widget_message_photo_wrap)
            photo_wraps = soup.select(".tgme_widget_message_photo_wrap")
            for wrap in photo_wraps:
                if len(photos) >= limit_photos:
                    break
                style_attr = wrap.get("style", "")
                bg_match = BG_IMAGE_REGEX.search(style_attr)
                img_url: str | None = None
                if bg_match:
                    img_url = bg_match.group(1).strip()
                else:
                    img_elem = wrap.find("img")
                    if img_elem and img_elem.get("src"):
                        img_url = str(img_elem["src"]).strip()

                if img_url and img_url.startswith("http") and img_url not in seen:
                    seen.add(img_url)
                    photos.append(img_url)

    except Exception as exc:
        logger.debug("Could not scrape TG channel %s: %s", username, exc)

    return {
        "avatar_url": avatar_url,
        "photos": photos,
    }

