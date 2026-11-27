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
TG_ADMIN_HANDLE_REGEX = re.compile(
    r"(?:(?<![A-Za-z0-9_.])@|(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/)([A-Za-z][A-Za-z0-9_]{4,31})(?![A-Za-z0-9_])",
    re.I,
)
BG_IMAGE_REGEX = re.compile(r"url\(['\"]?(https?://[^'\")]+)['\"]?\)", re.I)

TG_SYSTEM_EXCLUDES = {
    "joinchat", "share", "addstickers", "proxy", "login", "setlanguage",
    "invoice", "giftcode", "addtheme", "bg", "c", "murasaki_radar_1438_bot",
}

NON_STANDALONE_SITE_DOMAINS = (
    "t.me", "telegram.me", "wa.me", "whatsapp.com", "vk.com", "vk.ru",
    "instagram.com", "taplink.cc", "taplink.ru", "linktr.ee", "msto.me",
    "yandex.ru", "ya.ru", "2gis.ru", "2gis.com", "dikidi.net", "dikidi.ru",
    "yclients.com", "ok.ru", "youtube.com", "youtu.be", "dzen.ru", "avito.ru",
)
EXTERNAL_URL_REGEX = re.compile(r"https?://[^\s<>\"'()]+", re.I)


def classify_external_links(
    text_chunks: list[str] | None = None,
    explicit_urls: list[str] | None = None,
) -> dict[str, Any]:
    """Detect whether profile/bio links include a standalone custom website.

    Returns ``{"has_own_website": bool, "website_url": str | None, "priority": "high" | "low"}``.
    Phone, TG, WhatsApp, VK, Instagram, Taplink, Yandex Maps and 2GIS keep ``priority="high"``.
    """
    candidates: list[str] = []
    for u in (explicit_urls or []):
        if isinstance(u, str) and u.strip().startswith(("http://", "https://")):
            candidates.append(u.strip())
    for chunk in (text_chunks or []):
        if isinstance(chunk, str):
            candidates.extend(EXTERNAL_URL_REGEX.findall(chunk))

    for raw in candidates:
        cleaned = raw.rstrip(".,;:!?)]")
        host = (urlparse(cleaned).hostname or "").lower().lstrip("www.")
        if not host or "." not in host:
            continue
        is_social_or_agg = any(
            host == dom or host.endswith(f".{dom}")
            for dom in NON_STANDALONE_SITE_DOMAINS
        )
        if not is_social_or_agg:
            return {
                "has_own_website": True,
                "website_url": cleaned,
                "priority": "low",
            }

    return {
        "has_own_website": False,
        "website_url": None,
        "priority": "high",
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


def _extract_admin_username(soup: BeautifulSoup, channel_username: str) -> str | None:
    """Find first personal admin/manager @username in channel bio or recent posts."""
    own = channel_username.lower()

    def _scan_element(elem: Any) -> str | None:
        chunks = [elem.get_text(" ", strip=True)]
        for link in elem.find_all("a"):
            href = link.get("href")
            if href:
                chunks.append(str(href))
        for text in chunks:
            for match in TG_ADMIN_HANDLE_REGEX.finditer(text):
                cand = match.group(1)
                low = cand.lower()
                if low == own or low in TG_SYSTEM_EXCLUDES or low.endswith("bot"):
                    continue
                return cand
        return None

    for selector in (".tgme_channel_info_description", ".tgme_page_description"):
        for elem in soup.select(selector):
            found = _scan_element(elem)
            if found:
                return found

    for elem in reversed(soup.select(".tgme_widget_message_text")):
        found = _scan_element(elem)
        if found:
            return found

    return None


async def scrape_telegram_channel(
    channel_url_or_username: str,
    limit_photos: int = 6,
) -> dict[str, Any]:
    """Lightweight web scraper for public Telegram channel (https://t.me/s/{username}).

    Extracts:
      - Channel avatar (.tgme_page_photo_image img or background-image)
      - Direct photo URLs from recent posts (.tgme_widget_message_photo_wrap)
      - Admin/manager username from channel bio or recent posts
    """
    username = extract_tg_username(channel_url_or_username)
    if not username:
        return {"avatar_url": None, "photos": [], "admin_username": None}

    target_url = f"https://t.me/s/{username}"
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None

    avatar_url: str | None = None
    photos: list[str] = []
    admin_username: str | None = None
    seen: set[str] = set()
    link_info: dict[str, Any] = {"has_own_website": False, "website_url": None, "priority": "high"}

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
                return {
                    "avatar_url": None,
                    "photos": [],
                    "admin_username": None,
                    "has_own_website": False,
                    "website_url": None,
                    "priority": "high",
                }

            soup = BeautifulSoup(resp.text, "html.parser")
            admin_username = _extract_admin_username(soup, username)
            bio_chunks = [el.get_text(" ", strip=True) for el in soup.select(".tgme_channel_info_description, .tgme_page_description")]
            bio_links = [
                str(a.get("href"))
                for el in soup.select(".tgme_channel_info_description, .tgme_page_description")
                for a in el.find_all("a")
                if a.get("href")
            ]
            link_info = classify_external_links(text_chunks=bio_chunks, explicit_urls=bio_links)

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
            if limit_photos > 0:
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
        "admin_username": admin_username,
        "has_own_website": link_info["has_own_website"],
        "website_url": link_info["website_url"],
        "priority": link_info["priority"],
    }

