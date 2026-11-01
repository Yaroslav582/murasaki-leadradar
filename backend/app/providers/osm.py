from __future__ import annotations

import asyncio
import re
import time

import httpx

from app.providers.base import BaseProvider, PlaceResult, ProviderError
from app.providers.demo import CITIES, get_city_coords

OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

CACHE_TTL_SECONDS = 600
_cache: dict[str, tuple[float, list[PlaceResult]]] = {}

SELECTORS: dict[str, list[str]] = {
    "Бьюти": [
        'nwr["shop"~"beauty|hairdresser"]["name"]({scope});',
        'nwr["leisure"="spa"]["name"]({scope});',
    ],
    "Рестораны": [
        'nwr["amenity"~"restaurant|cafe|bar|fast_food|pub"]["name"]({scope});',
    ],
    "Автосервисы": [
        'nwr["shop"~"car_repair|tyres|car_parts"]["name"]({scope});',
        'nwr["amenity"="car_wash"]["name"]({scope});',
    ],
    "Медицина": [
        'nwr["amenity"~"clinic|dentist|doctors|hospital|pharmacy"]["name"]({scope});',
        'nwr["healthcare"]["name"]({scope});',
    ],
    "Фитнес": [
        'nwr["leisure"~"fitness_centre|sports_centre"]["name"]({scope});',
    ],
    "Отели": [
        'nwr["tourism"~"hotel|guest_house|hostel|apartment|motel"]["name"]({scope});',
    ],
    "Услуги": [
        'nwr["craft"]["name"]({scope});',
        'nwr["office"~"company|consulting|lawyer|accountant|insurance|estate_agent"]["name"]({scope});',
    ],
    "Магазины": [
        'nwr["shop"~"clothes|shoes|jewelry|furniture|electronics|gift|florist|cosmetics|optician|books|toys"]["name"]({scope});',
    ],
}

BUSINESS_TAGS = ("shop", "amenity", "tourism", "leisure", "office", "craft", "healthcare")

SEARCH_TERMS: dict[str, list[str]] = {
    "Бьюти": ["салон красоты", "барбершоп", "парикмахерская", "маникюр"],
    "Рестораны": ["ресторан", "кафе", "кофейня"],
    "Автосервисы": ["автосервис", "шиномонтаж", "автомойка"],
    "Медицина": ["клиника", "стоматология", "медцентр"],
    "Фитнес": ["фитнес клуб", "спортзал"],
    "Отели": ["отель", "гостиница"],
    "Услуги": ["ателье", "ремонт", "мастерская"],
    "Магазины": ["магазин", "бутик"],
}
DEFAULT_TERMS = [
    "салон красоты",
    "ресторан",
    "автосервис",
    "клиника",
    "фитнес клуб",
    "отель",
    "магазин",
]


def _clean(value: str | None) -> str:
    return (value or "").replace('"', "").replace("\\", "").strip()


def build_overpass_query(
    *,
    city: str,
    categories: list[str],
    query: str | None,
    limit: int,
    latitude: float | None = None,
    longitude: float | None = None,
    radius: int | None = None,
) -> str:
    if latitude is not None and longitude is not None:
        scope = f"around:{int(radius or 5000)},{latitude},{longitude}"
        area_block = ""
    else:
        city_coords = get_city_coords(city)
        if city_coords is not None:
            lat, lon = city_coords[0], city_coords[1]
            scope = f"{lat - 0.15},{lon - 0.25},{lat + 0.15},{lon + 0.25}"
            area_block = ""
        else:
            area_block = f'area["name"="{_clean(city)}"]["boundary"="administrative"]->.a;'
            scope = "area.a"

    if query:
        selectors = [f'nwr["name"~"{_clean(query)}",i]["name"]({scope});']
    else:
        chosen = categories or list(SELECTORS)
        selectors = []
        for category in chosen:
            for selector in SELECTORS.get(category, []):
                if selector not in selectors:
                    selectors.append(selector)
        if not selectors:
            for values in SELECTORS.values():
                selectors.extend(values)

    body = "\n".join(selector.format(scope=scope) for selector in selectors)
    out_limit = max(50, min(1200, limit * 4))
    return f"[out:json][timeout:30];\n{area_block}\n(\n{body}\n);\nout center {out_limit};"


def _normalize_website(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def _social_from_tags(tags: dict, key: str, kind: str) -> str | None:
    value = tags.get(f"contact:{key}") or tags.get(key)
    if not value:
        return None
    value = value.strip()
    if kind == "telegram":
        value = value.replace("https://t.me/", "").replace("http://t.me/", "").lstrip("@")
        return f"https://t.me/{value}" if value else None
    if kind == "instagram":
        value = re.sub(r"^https?://(www\.)?instagram\.com/", "", value).strip("/@")
        return f"https://instagram.com/{value}" if value else None
    if kind == "whatsapp":
        digits = re.sub(r"\D", "", value)
        return f"https://wa.me/{digits}" if len(digits) >= 10 else None
    return value or None


def detect_category(tags: dict) -> str:
    shop = tags.get("shop", "")
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    healthcare = tags.get("healthcare", "")

    if shop in ("car_repair", "tyres", "car_parts") or amenity == "car_wash":
        return "Автосервисы"
    if shop in ("beauty", "hairdresser") or leisure == "spa":
        return "Бьюти"
    if amenity in ("restaurant", "cafe", "bar", "fast_food", "pub"):
        return "Рестораны"
    if amenity in ("clinic", "dentist", "doctors", "hospital", "pharmacy") or healthcare:
        return "Медицина"
    if leisure in ("fitness_centre", "sports_centre"):
        return "Фитнес"
    if tourism in ("hotel", "guest_house", "hostel", "apartment", "motel"):
        return "Отели"
    if shop:
        return "Магазины"
    return "Услуги"


def element_to_place(element: dict, city: str) -> PlaceResult | None:
    tags = element.get("tags") or {}
    name = tags.get("name:ru") or tags.get("name")
    if not name:
        return None
    if not any(tags.get(tag) for tag in BUSINESS_TAGS):
        return None

    phone = tags.get("phone") or tags.get("contact:phone")
    website = _normalize_website(tags.get("website") or tags.get("contact:website"))
    socials: dict[str, str] = {}
    for key, kind in (("telegram", "telegram"), ("instagram", "instagram"), ("whatsapp", "whatsapp")):
        value = _social_from_tags(tags, key, kind)
        if value:
            socials[key] = value

    raw_emails = tags.get("email") or tags.get("contact:email") or ""
    emails = [
        email.strip()
        for email in re.split(r"[;,]", raw_emails)
        if email.strip() and "@" in email
    ][:5]

    if not (phone or website or socials or emails):
        return None

    street = tags.get("addr:street")
    number = tags.get("addr:housenumber")
    address = tags.get("addr:full") or (
        f"{street}, {number}" if street and number else street or ""
    )
    if city and address and city.lower() not in address.lower():
        address = f"{city}, {address}"

    center = element.get("center") or {}
    latitude = center.get("lat", element.get("lat"))
    longitude = center.get("lon", element.get("lon"))
    hours_raw = tags.get("opening_hours") or ""
    hours = [part.strip() for part in hours_raw.split(";") if part.strip()]

    return PlaceResult(
        name=name,
        category=detect_category(tags),
        city=tags.get("addr:city") or city,
        address=address,
        phone=phone,
        website_url=website,
        social_links=socials,
        emails=emails,
        opening_hours=hours,
        latitude=latitude,
        longitude=longitude,
        source="osm",
        source_id=f"{element.get('type')}/{element.get('id')}",
    )


def nominatim_item_to_place(item: dict, city: str) -> PlaceResult | None:
    address = item.get("address") or {}
    extratags = item.get("extratags") or {}
    category = item.get("category") or item.get("class") or ""
    place_type = item.get("type") or ""

    tags: dict[str, str] = {str(key): str(value) for key, value in extratags.items() if value}
    if item.get("name"):
        tags["name"] = str(item["name"])
    if category and place_type:
        tags[category] = place_type
    if address.get("road"):
        tags["addr:street"] = str(address["road"])
    if address.get("house_number"):
        tags["addr:housenumber"] = str(address["house_number"])
    if address.get("city"):
        tags["addr:city"] = str(address["city"])

    try:
        latitude = float(item["lat"]) if item.get("lat") else None
        longitude = float(item["lon"]) if item.get("lon") else None
    except (TypeError, ValueError):
        latitude = longitude = None

    element = {
        "type": item.get("osm_type") or "node",
        "id": item.get("osm_id"),
        "lat": latitude,
        "lon": longitude,
        "tags": tags,
    }
    return element_to_place(element, city)


class OSMProvider(BaseProvider):
    """Free OpenStreetMap source via the Overpass API (no keys required)."""

    source = "osm"

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
        if not city and latitude is None:
            raise ProviderError("Укажите город для поиска в OpenStreetMap")

        overpass_query = build_overpass_query(
            city=city,
            categories=categories,
            query=query,
            limit=limit,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
        )
        cached = _cache.get(overpass_query)
        if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1][:limit]

        headers = {
            "User-Agent": "LeadRadar/0.1 (local lead research; contact: admin@localhost)",
            "Accept": "application/json",
        }

        data: dict | None = None
        last_error = ""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30), headers=headers) as client:
            for endpoint in OVERPASS_ENDPOINTS:
                try:
                    response = await client.post(endpoint, data={"data": overpass_query})
                    if response.status_code >= 400:
                        last_error = f"{response.status_code} {response.text[:200]}"
                        continue
                    data = response.json()
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = f"{type(exc).__name__}: {exc}"
                    continue

        if data is None:
            try:
                fallback = await self._nominatim_fallback(
                    city=city,
                    categories=categories,
                    query=query,
                    limit=limit,
                )
            except ProviderError as exc:
                if cached:
                    return cached[1][:limit]
                raise ProviderError(
                    "Не удалось получить данные OSM. "
                    f"Overpass: {last_error or 'нет ответа'}. Nominatim: {exc}"
                ) from exc

            if fallback:
                _cache[overpass_query] = (time.monotonic(), fallback)
                if len(_cache) > 50:
                    oldest = min(_cache, key=lambda key: _cache[key][0])
                    _cache.pop(oldest, None)
            return fallback[:limit]

        results: list[PlaceResult] = []
        seen: set[str] = set()
        for element in data.get("elements", []):
            place = element_to_place(element, city)
            if place is None or (place.source_id and place.source_id in seen):
                continue
            if place.source_id:
                seen.add(place.source_id)
            results.append(place)
            if len(results) >= limit:
                break

        _cache[overpass_query] = (time.monotonic(), results)
        if len(_cache) > 50:
            oldest = min(_cache, key=lambda key: _cache[key][0])
            _cache.pop(oldest, None)
        return results

    async def _nominatim_fallback(
        self,
        *,
        city: str,
        categories: list[str],
        query: str | None,
        limit: int,
    ) -> list[PlaceResult]:
        if query:
            terms = [query]
        else:
            terms = []
            for category in categories:
                for term in SEARCH_TERMS.get(category, [category]):
                    if term not in terms:
                        terms.append(term)
            if not terms:
                terms = DEFAULT_TERMS

        headers = {
            "User-Agent": "LeadRadar/0.1 (local lead research; contact: admin@localhost)",
            "Accept": "application/json",
        }
        results: list[PlaceResult] = []
        seen: set[str] = set()
        successful_requests = 0
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(30), headers=headers) as client:
            for index, term in enumerate(terms):
                if len(results) >= limit:
                    break
                params = {
                    "q": f"{term} {city}".strip(),
                    "format": "jsonv2",
                    "extratags": 1,
                    "addressdetails": 1,
                    "limit": min(50, max(10, limit - len(results))),
                    "countrycodes": "ru",
                    "accept-language": "ru",
                }
                try:
                    response = await client.get(NOMINATIM_URL, params=params)
                    if response.status_code >= 400:
                        errors.append(f"{response.status_code} {response.text[:120]}")
                    else:
                        successful_requests += 1
                        for item in response.json():
                            place = nominatim_item_to_place(item, city)
                            if place is None or (place.source_id and place.source_id in seen):
                                continue
                            if place.source_id:
                                seen.add(place.source_id)
                            results.append(place)
                            if len(results) >= limit:
                                break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{type(exc).__name__}: {exc}")

                if index < len(terms) - 1 and len(results) < limit:
                    await asyncio.sleep(1.1)

        if successful_requests == 0:
            raise ProviderError(errors[-1] if errors else "нет ответа")
        return results
