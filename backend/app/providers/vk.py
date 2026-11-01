from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError

PHONE_RE = re.compile(r"(?:\+7|8)[\s(]*\d{3}[)\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
TG_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)")
WA_RE = re.compile(r"(?:https?://)?wa\.me/(\d+)")
INSTA_RE = re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_\.]+)")


def _clean_site(site: str | None) -> str | None:
    if not site:
        return None
    site = site.strip()
    if not site:
        return None
    # Skip social links disguised as website
    lowered = site.lower()
    if any(s in lowered for s in ("vk.com", "vk.ru", "t.me", "instagram.com", "wa.me")):
        return None
    if not site.startswith(("http://", "https://")):
        site = f"https://{site}"
    try:
        parsed = urlparse(site)
        if parsed.netloc and "." in parsed.netloc:
            return site
    except Exception:
        pass
    return None


class VKProvider(BaseProvider):
    """Free VK (ВКонтакте) business community search.

    Perfect for finding small local businesses without a standalone website
    (hairdressers, beauty salons, car repairs, clinics, cafes, craftsmen).
    Requires a free VK Service Token (Сервисный ключ доступа), which takes
    30 seconds to get on dev.vk.com.
    """

    source = "vk"
    api_url = "https://api.vk.com/method"
    api_version = "5.199"

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token or settings.vk_access_token

    async def search(
        self,
        *,
        city: str,
        categories: list[str],
        query: str | None,
        limit: int,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: int | None = None,
    ) -> list[PlaceResult]:
        if not self.access_token:
            raise ProviderError(
                "Не задан VK_ACCESS_TOKEN. "
                "Чтобы собирать лиды из ВКонтакте бесплатно: "
                "откройте https://vk.com/apps?act=manage -> «Создать приложение» (тип Standalone) -> "
                "раздел «Настройки» -> скопируйте «Сервисный ключ доступа» и добавьте в backend/.env как VK_ACCESS_TOKEN."
            )
        categories = categories or [""]
        results: list[PlaceResult] = []
        seen: set[str] = set()

        proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None

        async with httpx.AsyncClient(timeout=settings.http_timeout, proxy=proxy) as client:
            for category in categories:
                if len(results) >= limit:
                    break

                text = query or f"{category} {city}".strip()
                search_params = {
                    "q": text,
                    "type": "group",
                    "count": min(limit * 2, 200),
                    "v": self.api_version,
                    "access_token": self.access_token,
                }

                resp = await client.get(f"{self.api_url}/groups.search", params=search_params)
                if resp.status_code >= 400:
                    raise ProviderError(f"VK API HTTP error {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                if "error" in data:
                    err_msg = data["error"].get("error_msg", "unknown error")
                    raise ProviderError(f"VK API error: {err_msg}")

                items = (data.get("response") or {}).get("items") or []
                if not items:
                    continue

                group_ids = [str(item["id"]) for item in items if "id" in item][:limit * 2]
                if not group_ids:
                    continue

                # Fetch rich details for each community
                details_params = {
                    "group_ids": ",".join(group_ids),
                    "fields": "description,site,contacts,phone,city,country,status,addresses,links",
                    "v": self.api_version,
                    "access_token": self.access_token,
                }
                details_resp = await client.get(f"{self.api_url}/groups.getById", params=details_params)
                if details_resp.status_code >= 400:
                    continue

                details_data = details_resp.json()
                groups_info = (details_data.get("response") or {}).get("groups") or details_data.get("response") or []

                for g in groups_info:
                    gid = str(g.get("id") or "")
                    if not gid or gid in seen:
                        continue
                    seen.add(gid)

                    place = self._to_place(g, city, category)
                    if place:
                        results.append(place)
                        if len(results) >= limit:
                            return results

        return results

    def _to_place(self, g: dict, city: str, fallback_category: str) -> PlaceResult:
        screen_name = g.get("screen_name") or f"club{g.get('id')}"
        vk_url = f"https://vk.com/{screen_name}"

        # Contact links
        socials = {"vk": vk_url}

        desc = g.get("description") or ""
        status = g.get("status") or ""
        full_text = f"{desc}\n{status}"

        # Telegram
        tg_match = TG_RE.search(full_text)
        if tg_match:
            socials["telegram"] = f"https://t.me/{tg_match.group(1)}"

        # WhatsApp
        wa_match = WA_RE.search(full_text)
        if wa_match:
            socials["whatsapp"] = f"https://wa.me/{wa_match.group(1)}"

        # Instagram
        insta_match = INSTA_RE.search(full_text)
        if insta_match:
            socials["instagram"] = f"https://instagram.com/{insta_match.group(1)}"

        # Phone extraction
        phone = g.get("phone")
        if not phone:
            for contact in g.get("contacts") or []:
                c_phone = contact.get("phone")
                if c_phone:
                    phone = c_phone
                    break
        if not phone:
            phone_match = PHONE_RE.search(full_text)
            if phone_match:
                phone = phone_match.group(0)

        # Website
        raw_site = g.get("site")
        website = _clean_site(raw_site)

        # Address
        address = ""
        addresses = (g.get("addresses") or {}).get("items") or []
        if addresses:
            main_addr = addresses[0]
            address = main_addr.get("address") or ""
        if not address and city:
            address = city

        return PlaceResult(
            name=g.get("name") or "Сообщество VK",
            category=fallback_category or "Бизнес",
            city=city,
            address=address,
            phone=phone,
            website_url=website,
            social_links=socials,
            rating=None,
            reviews_count=g.get("members_count") or 0,
            latitude=None,
            longitude=None,
            opening_hours=[],
            source=self.source,
            source_id=str(g.get("id")),
        )
