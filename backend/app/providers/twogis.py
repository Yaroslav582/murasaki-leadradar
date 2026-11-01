from __future__ import annotations

import httpx

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError
from app.providers.demo import CITIES, get_city_coords

FIELDS = ",".join(
    [
        "items.point",
        "items.address",
        "items.contact_groups",
        "items.rubrics",
        "items.reviews",
        "items.schedule",
        "items.full_name",
        "items.name",
    ]
)

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


class TwoGisProvider(BaseProvider):
    source = "twogis"
    base_url = "https://catalog.api.2gis.com/3.0/items"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.twogis_api_key
        if not self.api_key:
            raise ProviderError(
                "Не задан TWOGIS_API_KEY. Бесплатный ключ на 1000 запросов/день можно получить "
                "за 1 минуту на https://dev.2gis.ru (или https://platform.2gis.ru) и указать в backend/.env."
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
        categories = categories or [""]
        results: list[PlaceResult] = []
        seen: set[str] = set()

        city_coords = get_city_coords(city)
        effective_lat = latitude if latitude is not None else (city_coords[0] if city_coords else None)
        effective_lon = longitude if longitude is not None else (city_coords[1] if city_coords else None)

        proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None
        async with httpx.AsyncClient(timeout=settings.http_timeout, proxy=proxy) as client:
            for category in categories:
                search_term = CATEGORY_QUERIES.get(category, category)
                if query:
                    q = query if city and city.lower() in query.lower() else f"{query} {city}".strip()
                else:
                    q = f"{search_term} {city}".strip()
                page = 1
                while len(results) < limit and page <= 5:
                    params: dict = {
                        "q": q,
                        "key": self.api_key,
                        "fields": FIELDS,
                        "type": "branch",
                        "page": page,
                        "page_size": min(10, limit),
                        "locale": "ru_RU",
                    }
                    if effective_lat is not None and effective_lon is not None:
                        params["point"] = f"{effective_lon},{effective_lat}"
                        params["radius"] = radius or 25000
                        params["sort"] = "distance"
                    response = await client.get(self.base_url, params=params)
                    if response.status_code >= 400:
                        raise ProviderError(f"2GIS API: {response.status_code} {response.text[:300]}")

                    data = response.json()
                    meta = data.get("meta", {})
                    if meta.get("code") not in (None, 200):
                        raise ProviderError(f"2GIS API: {meta.get('error', {}).get('message', 'unknown error')}")

                    items = (data.get("result") or {}).get("items", [])
                    if not items:
                        break

                    for item in items:
                        item_id = str(item.get("id") or "")
                        if not item_id or item_id in seen:
                            continue
                        seen.add(item_id)
                        results.append(self._to_place(item, city, category or None))
                        if len(results) >= limit:
                            return results
                    if len(items) < params["page_size"]:
                        break
                    page += 1
        return results

    def _to_place(self, item: dict, city: str, fallback_category: str | None) -> PlaceResult:
        phone: str | None = None
        website: str | None = None
        for group in item.get("contact_groups") or []:
            for contact in group.get("contacts") or []:
                if contact.get("type") in ("phone", "phone_number") and not phone:
                    phone = contact.get("value") or contact.get("text")
                if contact.get("type") in ("website", "url") and not website:
                    website = contact.get("url") or contact.get("value")

        rubrics = [rubric.get("name", "") for rubric in item.get("rubrics") or []]
        reviews = item.get("reviews") or {}
        point = item.get("point") or {}
        address = item.get("full_address_name") or item.get("address_name") or ""
        schedule = item.get("schedule") or {}
        hours: list[str] = []
        if isinstance(schedule, dict):
            for day, value in schedule.items():
                if isinstance(value, dict) and value.get("working_hours"):
                    hours.append(f"{day}: {value['working_hours']}")
        elif isinstance(schedule, str):
            hours.append(schedule)

        return PlaceResult(
            name=item.get("name") or item.get("full_name") or "Без названия",
            category=fallback_category or (rubrics[0] if rubrics else "Бизнес"),
            city=city,
            address=address,
            phone=phone,
            website_url=website,
            rating=reviews.get("rating") or reviews.get("org_rating"),
            reviews_count=int(reviews.get("review_count") or reviews.get("org_review_count") or 0),
            latitude=point.get("lat"),
            longitude=point.get("lon"),
            opening_hours=hours,
            source=self.source,
            source_id=str(item.get("id")),
        )
