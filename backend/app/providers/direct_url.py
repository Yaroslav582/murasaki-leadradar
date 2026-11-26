from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import PlaceResult, ProviderError, sample_user_agents
from app.providers.twogis import FIELDS as TWOGIS_FIELDS
from app.providers.twogis import TwoGisProvider
from app.providers.yandex_web import (
    ORG_ID_RE,
    PHONE_RE,
    _clean_yandex_url,
    _extract_item_photos,
    _parse_links,
    _parse_rating,
    org_page_to_place,
)

DGIS_FIRM_RE = re.compile(r"/firm/(\d+)")


def is_direct_org_url(value: str | None) -> bool:
    if not value:
        return False
    val = value.strip().lower()
    if not val.startswith(("http://", "https://")):
        return False
    return ("yandex." in val and "/maps/org/" in val) or ("2gis." in val and "/firm/" in val)


def _find_org_dict_in_state(obj: Any) -> dict | None:
    """Recursively locate an organization item dict inside Yandex Maps state JSON."""
    if isinstance(obj, dict):
        if obj.get("id") and (obj.get("title") or obj.get("name")) and (
            "fullAddress" in obj or "address" in obj or "phones" in obj or "ratingData" in obj
        ):
            return obj
        for val in obj.values():
            found = _find_org_dict_in_state(val)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_org_dict_in_state(item)
            if found:
                return found
    return None


def _extract_city_from_address(address: str, fallback: str = "Россия") -> str:
    if not address:
        return fallback
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return fallback
    for part in parts:
        clean = re.sub(r"^(?:г\.|город)\s*", "", part, flags=re.I).strip()
        if clean and not any(ch.isdigit() for ch in clean) and len(clean) >= 3:
            if not any(w in clean.lower() for w in ("область", "край", "республика", "россия", "улица", "ул.", "проспект", "пр-т")):
                return clean
    return fallback


async def _parse_yandex_org_url(url: str, fallback_city: str = "") -> PlaceResult:
    org_match = ORG_ID_RE.search(url)
    org_id = org_match.group(1) if org_match else None
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
        "Referer": "https://yandex.ru/maps/",
    }
    proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0, proxy=proxy) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise ProviderError(f"Яндекс Карты вернули статус {resp.status_code}")
        html_text = resp.text

    # 1. Try embedded Yandex state JSON
    for raw_json in re.findall(r'<script[^>]*class="[^"]*state[^"]*"[^>]*>([\s\S]*?)</script>', html_text):
        try:
            state = json.loads(raw_json)
        except Exception:
            continue
        org = _find_org_dict_in_state(state)
        if org:
            name = str(org.get("title") or org.get("shortTitle") or org.get("name") or "").strip()
            address = str(org.get("fullAddress") or org.get("address") or "").strip()
            city = fallback_city or _extract_city_from_address(address, "Россия")
            coords = org.get("coordinates")
            lat = coords[1] if isinstance(coords, list) and len(coords) >= 2 else None
            lon = coords[0] if isinstance(coords, list) and len(coords) >= 2 else None
            phone = None
            for p in org.get("phones") or []:
                val = p.get("number") or p.get("value") if isinstance(p, dict) else None
                if val:
                    phone = val
                    break
            urls = [_clean_yandex_url(u) for u in (org.get("urls") or []) if _clean_yandex_url(u)]
            website = urls[0] if urls else None
            socials: dict[str, str] = {}
            for s in org.get("socialLinks") or []:
                if not isinstance(s, dict):
                    continue
                stype = (s.get("type") or "").lower()
                shref = s.get("href") or ""
                if "wa.me" in shref or "whatsapp" in stype:
                    socials["whatsapp"] = shref
                elif "t.me" in shref or "telegram" in stype:
                    socials["telegram"] = shref.split("?")[0]
                elif "vk.com" in shref or "vk.ru" in shref or "vkontakte" in stype:
                    socials["vk"] = shref.split("?")[0]
                elif "instagram.com" in shref or "instagram" in stype:
                    socials["instagram"] = shref.split("?")[0]
            rating_data = org.get("ratingData") or {}
            rating = rating_data.get("ratingValue")
            reviews_count = int(rating_data.get("reviewCount") or rating_data.get("ratingCount") or 0)
            hours_text = org.get("workingTimeText")
            cats = org.get("categories") or []
            cat_name = cats[0].get("name") if cats and isinstance(cats[0], dict) else "Организация"
            logo_url, photos = _extract_item_photos(org)
            if name:
                return PlaceResult(
                    name=name,
                    category=cat_name or "Организация",
                    city=city,
                    address=address,
                    phone=phone,
                    website_url=website,
                    social_links=socials,
                    rating=float(rating) if rating is not None else None,
                    reviews_count=reviews_count,
                    latitude=lat,
                    longitude=lon,
                    opening_hours=[hours_text] if hours_text else [],
                    source="yandex_web",
                    source_id=str(org.get("id") or org_id or ""),
                    photos=photos,
                    logo_url=logo_url,
                )

    # 2. Fallback to HTML/Meta parsing
    soup = BeautifulSoup(html_text, "html.parser")
    h1 = soup.find("h1")
    name = h1.get_text(" ", strip=True) if h1 else ""
    if not name:
        og_t = soup.find("meta", attrs={"property": "og:title"})
        if og_t and og_t.get("content"):
            name = str(og_t["content"]).split(" — Яндекс")[0].strip()
    title = soup.title.get_text(" ", strip=True) if soup.title else name
    body_text = soup.get_text("\n", strip=True)
    links = [str(a["href"]) for a in soup.find_all("a", href=True) if str(a["href"]).startswith("http")]
    photos = []
    for img in soup.find_all("img", src=True):
        src = str(img["src"])
        if ("avatars.mds.yandex.net" in src or "get-altay" in src) and src not in photos:
            photos.append(src)
        if len(photos) >= 6:
            break

    if name:
        place = org_page_to_place(
            name=name,
            title=title,
            url=url,
            body=body_text,
            external_links=links,
            city=fallback_city or "Россия",
            fallback_category="",
            photos=photos,
        )
        if place:
            return place

    raise ProviderError("Не удалось извлечь карточку организации из ссылки Яндекс Карт (возможна капча).")


async def _parse_2gis_org_url(url: str, fallback_city: str = "") -> PlaceResult:
    firm_match = DGIS_FIRM_RE.search(url)
    firm_id = firm_match.group(1) if firm_match else None
    if not firm_id:
        raise ProviderError("Некорректная ссылка 2ГИС: не найден ID организации (/firm/...).")

    proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None

    # 1. Use official 2GIS API if key is configured
    if settings.twogis_api_key:
        async with httpx.AsyncClient(timeout=settings.http_timeout, proxy=proxy) as client:
            resp = await client.get(
                "https://catalog.api.2gis.com/3.0/items/byid",
                params={"id": firm_id, "key": settings.twogis_api_key, "fields": TWOGIS_FIELDS, "locale": "ru_RU"},
            )
            if resp.status_code == 200:
                items = (resp.json().get("result") or {}).get("items") or []
                if items:
                    provider = TwoGisProvider(api_key=settings.twogis_api_key)
                    return provider._to_place(items[0], fallback_city or "Россия", None)

    # 2. Public HTML / JSON-LD / OpenGraph fallback
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0, proxy=proxy) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise ProviderError(f"2ГИС вернул статус {resp.status_code}")
        html_text = resp.text

    soup = BeautifulSoup(html_text, "html.parser")
    name = ""
    address = ""
    phone = None
    website = None
    category = "Организация"
    rating = None
    reviews_count = 0

    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(sc.get_text() or "{}")
            if isinstance(data, list):
                data = data[0] if data else {}
            if isinstance(data, dict) and data.get("name"):
                name = str(data.get("name") or "").strip()
                phone = data.get("telephone") or phone
                addr_obj = data.get("address")
                if isinstance(addr_obj, dict):
                    address = str(addr_obj.get("streetAddress") or "").strip()
                    if not fallback_city and addr_obj.get("addressLocality"):
                        fallback_city = str(addr_obj["addressLocality"])
                elif isinstance(addr_obj, str):
                    address = addr_obj.strip()
                agg = data.get("aggregateRating")
                if isinstance(agg, dict):
                    rating = float(agg["ratingValue"]) if agg.get("ratingValue") else None
                    reviews_count = int(agg.get("reviewCount") or 0)
                if data.get("url") and "2gis" not in str(data["url"]):
                    website = str(data["url"])
                break
        except Exception:
            continue

    if not name:
        h1 = soup.find("h1")
        name = h1.get_text(" ", strip=True) if h1 else ""
    if not name:
        og_t = soup.find("meta", attrs={"property": "og:title"})
        if og_t and og_t.get("content"):
            name = str(og_t["content"]).split(",")[0].strip()

    if not name:
        raise ProviderError("Не удалось извлечь данные организации со страницы 2ГИС.")

    body_text = soup.get_text("\n", strip=True)
    if not phone:
        pm = PHONE_RE.search(body_text)
        phone = pm.group(0).strip() if pm else None

    links = [str(a["href"]) for a in soup.find_all("a", href=True) if str(a["href"]).startswith("http") and "2gis." not in str(a["href"])]
    parsed_web, socials = _parse_links(links)
    website = website or parsed_web
    if not rating:
        rating, reviews_count = _parse_rating(body_text)

    city = fallback_city or _extract_city_from_address(address, "Россия")
    return PlaceResult(
        name=name,
        category=category,
        city=city,
        address=address,
        phone=phone,
        website_url=website,
        social_links=socials,
        rating=rating,
        reviews_count=reviews_count,
        source="twogis",
        source_id=firm_id,
    )


async def parse_direct_org_url(url: str, fallback_city: str = "") -> PlaceResult:
    """Parse a single organization directly from a Yandex Maps or 2GIS URL."""
    clean_url = (url or "").strip()
    parsed = urlparse(clean_url)
    host = parsed.netloc.lower()
    if "yandex." in host and "/maps/org/" in parsed.path:
        return await _parse_yandex_org_url(clean_url, fallback_city=fallback_city)
    if "2gis." in host and "/firm/" in parsed.path:
        return await _parse_2gis_org_url(clean_url, fallback_city=fallback_city)
    raise ProviderError(
        "Поддерживаются прямые ссылки на карточки Яндекс Карт (https://yandex.ru/maps/org/...) "
        "и 2ГИС (https://2gis.ru/.../firm/...)."
    )
