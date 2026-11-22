from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import sample_user_agents

logger = logging.getLogger(__name__)

STATIC_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "media"
STATIC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

TG_URL_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,40})",
    re.I,
)
BG_IMAGE_REGEX = re.compile(r"url\(['\"]?(https?://[^'\")]+)['\"]?\)", re.I)

TG_SYSTEM_EXCLUDES = {
    "joinchat", "share", "addstickers", "proxy", "login", "setlanguage",
    "invoice", "giftcode", "addtheme", "bg", "c", "murasaki_radar_1438_bot",
    "botfather", "stickers",
}

# ── English search keywords for aesthetic niche fallback ─────────────────────
NICHE_SEARCH_QUERIES: dict[str, dict[str, Any]] = {
    "Бьюти": {
        "query": "beauty salon interior aesthetic spa",
        "hero": "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1607779097040-26e80aa78e66?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Автосервисы": {
        "query": "car detailing garage mechanics workshop",
        "hero": "https://images.unsplash.com/photo-1486006920555-c77dce18193b?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1517524008697-84bbe3c3fd98?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1625047509168-a7026f36de04?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Рестораны": {
        "query": "restaurant food dish dining aesthetic cafe",
        "hero": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Медицина": {
        "query": "modern dental clinic doctor hospital aesthetic",
        "hero": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1666214280557-f1b5022eb634?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Юристы": {
        "query": "modern law firm office lawyer corporate boardroom",
        "hero": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1450133064473-71024230f91b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Фитнес": {
        "query": "fitness gym workout crossfit athletic interior",
        "hero": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Default": {
        "query": "modern office creative workspace business interior",
        "hero": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=800&q=80",
        ],
    },
}


def _get_public_media_url(file_name: str) -> str:
    base = settings.public_base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/static/uploads/media/{file_name}"


async def persist_remote_image(image_url: str, timeout: float = 6.0) -> str:
    """Downloads remote image (especially Telegram CDN expiring links) and saves it permanently."""
    if not image_url or not image_url.startswith("http"):
        return image_url

    # Check if already a local/stored media url
    if "/static/uploads/media/" in image_url:
        return image_url

    # Only persist Telegram or ephemeral links to avoid unnecessary re-downloads of stable Unsplash/Yandex
    is_ephemeral = any(domain in image_url for domain in ("telesco.pe", "telegram.org", "cdn-telegram", "t.me", "tg.org"))

    try:
        url_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:16]
        target_path = STATIC_UPLOADS_DIR / f"{url_hash}.jpg"

        if target_path.exists() and target_path.stat().st_size > 1000:
            return _get_public_media_url(target_path.name)

        if not is_ephemeral:
            # For persistent CDNs (Unsplash, Yandex avatars.mds), return original URL
            return image_url

        headers = {
            "User-Agent": sample_user_agents(settings.user_agent_list),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(timeout), follow_redirects=True) as client:
            resp = await client.get(image_url)
            if resp.status_code == 200 and len(resp.content) > 1024:
                # Basic check for image content-type or bytes
                ct = resp.headers.get("content-type", "").lower()
                if "image" in ct or resp.content[:3] in (b"\xff\xd8\xff", b"\x89PN", b"GIF", b"RIF"):
                    target_path.write_bytes(resp.content)
                    return _get_public_media_url(target_path.name)
    except Exception as exc:
        logger.debug("Could not persist image %s: %s", image_url[:60], exc)

    return image_url


def is_trash_or_screenshot(url: str) -> bool:
    """Filter out chat screenshots, text-heavy vertical receipts, or price lists based on url heuristics."""
    lowered = url.lower()
    bad_markers = (
        "screenshot", "screen_", "chat_", "perepiska", "otzyv_screen",
        "receipt", "chek", "price_list", "prajs", "prays", "schet",
        "document", "scan_", "vypiska", "rekvizity",
    )
    if any(m in lowered for m in bad_markers):
        return True

    # Detect extreme vertical price ratios if encoded in Yandex URL dimensions (e.g. /1200x3600/)
    dim_match = re.search(r"/(\d{3,4})x(\d{3,4})/", lowered)
    if dim_match:
        w, h = int(dim_match.group(1)), int(dim_match.group(2))
        if h > 0 and (w / h < 0.45 or h / w > 2.2):
            return True

    return False


def extract_tg_username(raw: str | None) -> str | None:
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


async def scrape_tg_channel_posts(username: str, limit: int = 15) -> list[str]:
    """Scrapes direct image URLs from the last 10-15 messages in a public Telegram channel."""
    clean_username = extract_tg_username(username)
    if not clean_username:
        return []

    url = f"https://t.me/s/{clean_username}"
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None

    photos: list[str] = []
    seen: set[str] = set()

    try:
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(8.0), follow_redirects=True, proxy=proxy) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")

            # Channel avatar
            avatar_wrap = soup.select_one(".tgme_page_photo_image")
            if avatar_wrap:
                img_tag = avatar_wrap.find("img")
                if img_tag and img_tag.get("src"):
                    p_url = str(img_tag["src"]).strip()
                    if p_url and p_url not in seen:
                        seen.add(p_url)
                        photos.append(p_url)

            # Photos in channel posts
            wraps = soup.select(".tgme_widget_message_photo_wrap")
            for wrap in reversed(wraps):  # latest first
                style_attr = wrap.get("style", "")
                m = BG_IMAGE_REGEX.search(style_attr)
                if m:
                    img_link = m.group(1).strip()
                    if img_link and img_link not in seen:
                        seen.add(img_link)
                        photos.append(img_link)
                if len(photos) >= limit:
                    break
    except Exception as exc:
        logger.debug("Failed scraping TG channel %s: %s", clean_username, exc)

    return photos


async def probe_tg_profile_for_channels(profile_handle: str) -> list[str]:
    """Probes a personal TG user profile for attached channels or channel links in bio."""
    username = extract_tg_username(profile_handle)
    if not username:
        return []

    discovered_channels: list[str] = []

    # 1. Try Telethon client if active
    try:
        from app.services.telegram_service import telegram_manager
        client = await telegram_manager.get_active_client()
        if client:
            entity = await client.get_entity(username)
            from telethon.tl.functions.users import GetFullUserRequest
            full_user = await client(GetFullUserRequest(id=entity))
            # Check personal channel id if available
            p_chan_id = getattr(full_user.full_user, "personal_channel_id", None)
            if p_chan_id:
                try:
                    chan_ent = await client.get_entity(p_chan_id)
                    chan_user = getattr(chan_ent, "username", None)
                    if chan_user:
                        discovered_channels.append(chan_user)
                except Exception:
                    pass

            # Check bio / about text for links
            about = getattr(full_user.full_user, "about", "") or ""
            for match in TG_URL_REGEX.finditer(about):
                c_name = match.group(1)
                if c_name and c_name.lower() != username.lower() and c_name not in TG_SYSTEM_EXCLUDES:
                    discovered_channels.append(c_name)
    except Exception as exc:
        logger.debug("Telethon profile probe notice for %s: %s", username, exc)

    # 2. Web fallback (t.me/username preview bio inspection)
    if not discovered_channels:
        try:
            url = f"https://t.me/{username}"
            headers = {"User-Agent": sample_user_agents(settings.user_agent_list)}
            async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(5.0), follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    desc = soup.select_one(".tgme_page_description")
                    if desc:
                        text = desc.get_text()
                        for match in TG_URL_REGEX.finditer(text):
                            c_name = match.group(1)
                            if c_name and c_name.lower() != username.lower() and c_name not in TG_SYSTEM_EXCLUDES:
                                discovered_channels.append(c_name)
                        # Also look for @mentions
                        for mention in re.findall(r"@([A-Za-z0-9_]{4,40})", text):
                            if mention.lower() != username.lower() and mention not in TG_SYSTEM_EXCLUDES:
                                discovered_channels.append(mention)
        except Exception:
            pass

    return list(dict.fromkeys(discovered_channels))


def get_niche_fallback(category: str | None) -> dict[str, Any]:
    cat = (category or "").lower()
    if any(k in cat for k in ("бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "спа", "массаж", "ногти", "брови")):
        return NICHE_SEARCH_QUERIES["Бьюти"]
    if any(k in cat for k in ("авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто")):
        return NICHE_SEARCH_QUERIES["Автосервисы"]
    if any(k in cat for k in ("ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "пицц", "суши", "бургер", "бар", "кухн", "кондитер")):
        return NICHE_SEARCH_QUERIES["Рестораны"]
    if any(k in cat for k in ("медицин", "клиник", "стоматолог", "доктор", "врач", "зуб", "анализ")):
        return NICHE_SEARCH_QUERIES["Медицина"]
    if any(k in cat for k in ("юрист", "юрид", "адвокат", "нотариус", "финанс", "бухгалтер", "аудит", "b2b", "недвижим")):
        return NICHE_SEARCH_QUERIES["Юристы"]
    if any(k in cat for k in ("фитнес", "тренажер", "спорт", "йога", "кроссфит", "бассейн")):
        return NICHE_SEARCH_QUERIES["Фитнес"]
    return NICHE_SEARCH_QUERIES["Default"]


async def collect_media(lead_dict: dict[str, Any], max_items: int = 12) -> dict[str, Any]:
    """Cascading media collector for business lead.

    Priority order:
    1. Yandex Maps: Organization photos + review attachments (filtering out chat screenshots & vertical price lists).
    2. Direct Telegram Channel: Photos from the last 10-15 messages.
    3. Telegram Personal Account: Probing bio and personal channel for attached channels, then fetching work photos.
    4. Media persistence: All Telegram CDN images are saved locally to prevent link expiration.
    5. Niche fallback: If total real photos < 2, map category to aesthetic query and curated Unsplash collection.
    """
    collected: list[str] = []
    seen: set[str] = set()
    logo_url = lead_dict.get("logo_url")
    socials = lead_dict.get("social_links") or {}
    category = lead_dict.get("category") or ""

    # ── 1. Yandex Maps photos & review attachments ───────────────────────────
    raw_yandex_photos = list(lead_dict.get("photos") or [])
    for p in raw_yandex_photos:
        if p and p not in seen and not is_trash_or_screenshot(p):
            seen.add(p)
            collected.append(p)

    # ── 2. Direct Telegram channel parsing ───────────────────────────────────
    tg_url = socials.get("telegram")
    if tg_url:
        tg_photos = await scrape_tg_channel_posts(tg_url, limit=12)
        for p in tg_photos:
            if p and p not in seen and not is_trash_or_screenshot(p):
                seen.add(p)
                collected.append(p)
                if not logo_url and len(collected) == 1:
                    logo_url = p

    # ── 3. Telegram personal profile probe ───────────────────────────────────
    if len(collected) < max_items and tg_url:
        # Check if the given telegram link was a user profile rather than a channel
        profile_channels = await probe_tg_profile_for_channels(tg_url)
        for chan in profile_channels:
            chan_photos = await scrape_tg_channel_posts(chan, limit=8)
            for p in chan_photos:
                if p and p not in seen and not is_trash_or_screenshot(p):
                    seen.add(p)
                    collected.append(p)
            if len(collected) >= max_items:
                break

    # ── 4. Persistent saving for Telegram images ─────────────────────────────
    persisted: list[str] = []
    for p in collected[:max_items]:
        saved_url = await persist_remote_image(p)
        persisted.append(saved_url)
    collected = persisted

    # ── 5. Niche Fallback (if real photos < 2) ───────────────────────────────
    if len(collected) < 2:
        fallback_data = get_niche_fallback(category)
        if not logo_url and fallback_data.get("hero"):
            logo_url = fallback_data["hero"]

        if fallback_data.get("hero") and fallback_data["hero"] not in collected:
            collected.append(fallback_data["hero"])

        for g in fallback_data.get("gallery", []):
            if g not in collected and len(collected) < max_items:
                collected.append(g)

    return {
        "photos": collected[:max_items],
        "logo_url": logo_url or (collected[0] if collected else None),
        "count": len(collected),
    }

