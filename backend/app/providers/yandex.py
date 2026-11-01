from __future__ import annotations

import math

import httpx

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError
from app.providers.demo import CITIES

CATEGORY_QUERIES = {
    "Бьюти": "салон красоты",
    "Рестораны": "ресторан",
    "Автосервисы": "автосервис",
    "Медицина": "клиника",
    "Фитнес": "фитнес клуб",
    "Отели": "отель",
    "Услуги": "услуги",
    "Магазины": "магазин",
}


def _first_phone(company: dict) -> str | None:
    for phone in company.get("Phones") or []:
        if isinstance(phone, str):
            value = phone
        else:
            value = phone.get("formatted") or phone.get("phone")
        if value:
            return str(value).strip()
    return None


def _parse_urls(company: dict) -> tuple[str | None, dict[str, str]]:
    website: str | None = None
    socials: dict[str, str] = {}
    for item in company.get("Urls") or []:
        if isinstance(item, str):
            value = item
        else:
            value = str(item.get("url") or item.get("value") or "")
        value = value.strip()
        if not value:
            continue
        lowered = value.lower()
        if "t.me/" in lowered or "telegram.me/" in lowered:
            socials["telegram"] = value
        elif "wa.me/" in lowered or "whatsapp" in lowered:
            socials["whatsapp"] = value
        elif "instagram.com/" in lowered:
            socials["instagram"] = value
        elif website is None:
            website = value
    return website, socials


def _parse_rating(company: dict, properties: dict) -> tuple[float | None, int]:
    raw = company.get("rating") or properties.get("rating")
    count = company.get("review_count") or properties.get("review_count") or 0
    if isinstance(raw, dict):
        count = raw.get("count") or raw.get("review_count") or count
        raw = raw.get("score") or raw.get("value")
    try:
        rating = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        rating = None
    try:
        reviews_count = int(count or 0)
    except (TypeError, ValueError):
        reviews_count = 0
    return rating, reviews_count


def feature_to_place(feature: dict, city: str, fallback_category: str) -> PlaceResult | None:
    properties = feature.get("properties") or {}
    company = properties.get("CompanyMetaData") or {}
    if not company:
        return None

    name = company.get("name") or properties.get("name")
    if not name:
        return None
    company_id = company.get("id") or properties.get("id") or feature.get("id")
    if not company_id:
        return None

    website, socials = _parse_urls(company)
    rating, reviews_count = _parse_rating(company, properties)

    hours_text = (company.get("Hours") or {}).get("text") or ""
    hours = [part.strip() for part in hours_text.replace(";", "; ").split(";") if part.strip()]

    categories = [
        category.get("name")
        for category in company.get("Categories") or []
        if isinstance(category, dict) and category.get("name")
    ]
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    longitude = coordinates[0] if len(coordinates) > 1 else None
    latitude = coordinates[1] if len(coordinates) > 1 else None

    return PlaceResult(
        name=str(name),
        category=fallback_category or (categories[0] if categories else "Бизнес"),
        city=city,
        address=str(company.get("address") or properties.get("description") or ""),
        phone=_first_phone(company),
        website_url=website,
        social_links=socials,
        rating=rating,
        reviews_count=reviews_count,
        latitude=latitude,
        longitude=longitude,
        opening_hours=hours,
        source="yandex",
        source_id=str(company_id),
    )


class YandexMapsProvider(BaseProvider):
    """Yandex Geosearch API provider (requires a paid Maps API key)."""

    source = "yandex"
    base_url = "https://search-maps.yandex.ru/v1/"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.yandex_maps_api_key
        if not self.api_key:
            raise ProviderError(
                "Не задан YANDEX_MAPS_API_KEY. Получите ключ API Геопоиска в кабинете "
                "Яндекс Карт и укажите его в backend/.env."
            )

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
        terms = (
            [(categories[0] if categories else "", query)]
            if query
            else [
                (category, CATEGORY_QUERIES.get(category, category))
                for category in (categories or [""])
            ]
        )
        results: list[PlaceResult] = []
        seen: set[str] = set()

        city_coords = CITIES.get(city)
        if latitude is not None and longitude is not None:
            center_lat, center_lon = latitude, longitude
        elif city_coords:
            center_lat, center_lon = city_coords[0], city_coords[1]
        else:
            center_lat = center_lon = None

        radius_m = radius or 15000
        spn: str | None = None
        if center_lat is not None and center_lon is not None:
            delta_lat = radius_m / 111_000
            delta_lon = delta_lat / max(math.cos(math.radians(center_lat)), 0.2)
            spn = f"{2 * delta_lon:.4f},{2 * delta_lat:.4f}"

        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            for category, term in terms:
                page = 0
                while len(results) < limit and page < 5:
                    params: dict = {
                        "apikey": self.api_key,
                        "text": f"{term} {city}".strip(),
                        "lang": "ru_RU",
                        "type": "biz",
                        "results": min(50, limit - len(results)),
                        "skip": page * 50,
                    }
                    if center_lat is not None and center_lon is not None and spn:
                        params["ll"] = f"{center_lon},{center_lat}"
                        params["spn"] = spn
                        params["rspn"] = "1"

                    response = await client.get(self.base_url, params=params)
                    if response.status_code == 403:
                        raise ProviderError(
                            "Яндекс отклонил ключ (403). Проверьте YANDEX_MAPS_API_KEY, "
                            "подключённый тариф и ограничения ключа."
                        )
                    if response.status_code == 429:
                        raise ProviderError("Превышен лимит запросов Яндекс Геопоиска (429).")
                    if response.status_code >= 400:
                        raise ProviderError(
                            f"Яндекс Геопоиск: {response.status_code} {response.text[:300]}"
                        )

                    data = response.json()
                    features = data.get("features") or []
                    if not features:
                        break

                    for feature in features:
                        place = feature_to_place(feature, city, category)
                        if place is None or place.source_id in seen:
                            continue
                        seen.add(place.source_id or "")
                        results.append(place)
                        if len(results) >= limit:
                            return results

                    if len(features) < params["results"]:
                        break
                    page += 1
        return results
