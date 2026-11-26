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

# ── Sub-niche detection & same-origin curated stock photography ─────────────
SUBNICHE_KEYS = (
    "hair",
    "barber",
    "nails",
    "beauty",
    "coffee",
    "restaurant",
    "dental",
    "clinic",
    "auto",
    "fitness",
    "flowers",
    "office",
)

NICHE_SEARCH_QUERIES: dict[str, dict[str, str]] = {
    "hair": {"query": "hair salon haircut hairstylist"},
    "barber": {"query": "barbershop men haircut fade"},
    "nails": {"query": "nail studio manicure pedicure"},
    "beauty": {"query": "cosmetology spa facial beauty"},
    "coffee": {"query": "specialty coffee cafe bakery"},
    "restaurant": {"query": "modern restaurant dining dishes"},
    "dental": {"query": "modern dental clinic dentistry"},
    "clinic": {"query": "medical clinic doctor center"},
    "auto": {"query": "car detailing auto service"},
    "fitness": {"query": "fitness gym workout yoga"},
    "flowers": {"query": "flower shop bouquet florist"},
    "office": {"query": "modern business office consulting"},
}


def _stock_base_url(public_url: str = "") -> str:
    if public_url and public_url.strip().startswith(("http://", "https://")):
        parsed = urlparse(public_url.strip())
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    base = (settings.public_base_url or "http://127.0.0.1:8000").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return base


def detect_subniche(
    category: str | None,
    business_name: str | None = None,
    services: list[Any] | None = None,
) -> str:
    """Resolve granular visual sub-niche from category, business name, and service titles."""
    primary_text = f"{category or ''} {business_name or ''}".lower()
    srv_text = " ".join(
        str(s.get("name") or s.get("category") or "") if isinstance(s, dict) else str(s)
        for s in (services or [])
    ).lower()
    text = f"{primary_text} {srv_text}"

    # 1. Explicit barbershop (avoid misclassifying unisex hair salons that list "Мужская стрижка")
    is_unisex_salon = any(k in text for k in ("женск", "окрашиван", "мелирован", "укладк", "причес", "балаяж", "шатуш"))
    if any(k in primary_text for k in ("барбер", "barber", "мужская парикмахерская")) or (
        not is_unisex_salon and ("мужск" in primary_text and any(k in primary_text for k in ("стриж", "бород")))
    ):
        return "barber"
    if any(k in text for k in ("маникюр", "педикюр", "ногт", "ногтев", "nail", "гель-лак")) and "парикмах" not in primary_text:
        return "nails"
    if any(k in text for k in ("парикмах", "волос", "колорист", "окрашиван", "мелирован", "укладк", "стриж", "кератин", "причес", "hair")):
        return "hair"
    if any(k in text for k in ("бьюти", "красот", "косметол", "спа", "spa", "массаж", "брови", "ресниц", "эпиляц", "шугаринг", "перманент", "визаж", "эстетик", "салон")):
        return "beauty"
    if any(k in text for k in ("кофейн", "кофе", "coffee", "пекарн", "кондитер", "выпечк", "десерт", "торт", "булочн", "круассан")):
        return "coffee"
    if any(k in text for k in ("ресторан", "кафе", "бар ", "паб", "пицц", "суши", "ролл", "бургер", "шашлык", "бистро", "столов", "доставка еды", "кухн", "общепит")):
        return "restaurant"
    if any(k in text for k in ("стоматолог", "зубн", "дента", "ортодонт", "имплант", "брекет")):
        return "dental"
    if any(k in text for k in ("клиник", "медицин", "медцентр", "врач", "доктор", "анализ", "узи", "диагност", "терапевт", "остеопат", "ветеринар", "здоров")):
        return "clinic"
    if any(k in text for k in ("автосервис", "детейлинг", "шиномонтаж", "автомойк", "мойк", "кузов", "тюнинг", " сто ", "авто", "мотор", "машин")):
        return "auto"
    if any(k in text for k in ("фитнес", "тренажер", "спорт", "йога", "пилатес", "кроссфит", "бассейн", "единобор", "бокс", "танц", "стретч")):
        return "fitness"
    if any(k in text for k in ("цвет", "букет", "флорист", "магазин", "бутик", "одежд", "подарк", "ювелир", "шоурум")):
        return "flowers"
    return "office"


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


SUBNICHE_WORK_CAPTIONS: dict[str, tuple[str, str, str]] = {
    "hair": ("Укладка и причёска", "Сложное окрашивание", "Мужская стрижка"),
    "barber": ("Мужская стрижка фейд", "Оформление бороды", "Укладка волос"),
    "nails": ("Нюдовый маникюр", "Французский маникюр", "Педикюр с покрытием"),
    "beauty": ("Уходовая процедура", "Брови и ресницы", "Расслабляющий массаж"),
    "coffee": ("Капучино и круассан", "Свежая выпечка", "Освежающий айс-латте"),
    "restaurant": ("Авторская паста", "Блюдо с креветками", "Авторские коктейли"),
    "dental": ("Осмотр и диагностика", "Эстетика улыбки", "Лечение под микроскопом"),
    "clinic": ("Консультация врача", "УЗИ и диагностика", "Приём специалиста"),
    "auto": ("Полировка кузова", "Компьютерная диагностика", "Детейлинг салона"),
    "fitness": ("Персональная тренировка", "Йога и пилатес", "Функциональный тренинг"),
    "flowers": ("Авторский букет", "Букет пионов и роз", "Сборка композиций"),
    "office": ("Консультация специалиста", "Разбор проекта", "Работа команды"),
}


def get_niche_fallback(
    category: str | None,
    business_name: str | None = None,
    services: list[Any] | None = None,
    public_url: str = "",
) -> dict[str, Any]:
    sub = detect_subniche(category, business_name=business_name, services=services)
    base = _stock_base_url(public_url)
    works = [f"{base}/static/stock/{sub}/works_{i}.jpg" for i in (1, 2, 3)]
    interior = [f"{base}/static/stock/{sub}/interior_{i}.jpg" for i in (1, 2, 3)]
    captions = SUBNICHE_WORK_CAPTIONS.get(sub, ("Работа мастера", "Результат процедуры", "Пример услуги"))
    work_captions = {works[idx]: captions[idx] for idx in range(3)}
    return {
        "subniche": sub,
        "query": NICHE_SEARCH_QUERIES.get(sub, {}).get("query", sub),
        "hero": f"{base}/static/stock/{sub}/hero.jpg",
        "works": works,
        "work_captions": work_captions,
        "interior": interior,
        "gallery": works + interior,
    }


async def _fetch_yandex_org_gallery(source_id: str | None, limit: int = 8) -> list[str]:
    """Best-effort fetch of full gallery photos from Yandex Maps org gallery HTML."""
    oid = str(source_id or "").strip()
    if not oid or not oid.isdigit():
        return []
    url = f"https://yandex.ru/maps/org/{oid}/gallery/"
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None
    found: list[str] = []
    try:
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(4.0), follow_redirects=True, proxy=proxy) as client:
            resp = await client.get(url)
            if resp.status_code != 200 or "captcha" in resp.text.lower()[:2000]:
                return []
            for m in re.finditer(r"https://avatars\.mds\.yandex\.net/get-altay/\d+/[A-Za-z0-9_-]+/(?:orig|XXL|XL|L)", resp.text):
                u = m.group(0)
                if u not in found:
                    found.append(u)
                if len(found) >= limit:
                    break
    except Exception:
        pass
    return found


async def collect_media(lead_dict: dict[str, Any], max_items: int = 12) -> dict[str, Any]:
    """Cascading media collector for business lead.

    Priority order:
    1. Yandex Maps: Organization photos & gallery (filtering out chat screenshots, stock placeholders & price lists).
    2. Direct Telegram Channel: Photos from the last 10-15 messages.
    3. Telegram Personal Account: Probing bio and personal channel for attached channels, then fetching work photos.
    4. Media persistence: All Telegram CDN images are saved locally to prevent link expiration.
    5. Niche fallback: Separate role-matched same-origin stock photos (`hero`, `works`, `interior`).
    """
    collected: list[str] = []
    seen: set[str] = set()
    logo_url = lead_dict.get("logo_url")
    socials = lead_dict.get("social_links") or {}
    category = lead_dict.get("category") or ""

    # ── 1. Yandex Maps photos & review attachments ───────────────────────────
    raw_yandex_photos = list(lead_dict.get("photos") or [])
    for p in raw_yandex_photos:
        if not p or p in seen:
            continue
        low = p.lower()
        if "images.unsplash.com" in low or "/static/stock/" in low:
            continue
        if not is_trash_or_screenshot(p):
            seen.add(p)
            collected.append(p)

    if len(collected) < 4 and lead_dict.get("source_id"):
        for gp in await _fetch_yandex_org_gallery(lead_dict.get("source_id"), limit=max_items):
            if gp not in seen and not is_trash_or_screenshot(gp):
                seen.add(gp)
                collected.append(gp)

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
    real_photos = list(persisted)
    combined = list(persisted)

    # ── 5. Granular sub-niche Fallback (if real photos < 2) ──────────────────
    if len(combined) < 2:
        fallback_data = get_niche_fallback(
            category,
            business_name=lead_dict.get("name"),
            services=lead_dict.get("services"),
        )
        if not logo_url and fallback_data.get("hero"):
            logo_url = fallback_data["hero"]

        if fallback_data.get("hero") and fallback_data["hero"] not in combined:
            combined.append(fallback_data["hero"])

        for g in fallback_data.get("gallery", []):
            if g not in combined and len(combined) < max_items:
                combined.append(g)

    return {
        "photos": combined[:max_items],
        "real_photos": real_photos[:max_items],
        "logo_url": logo_url or (combined[0] if combined else None),
        "count": len(combined),
    }

