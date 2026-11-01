from __future__ import annotations

import asyncio

import httpx

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.location",
        "places.regularOpeningHours.weekdayDescriptions",
        "places.priceLevel",
        "places.primaryTypeDisplayName",
        "places.types",
        "places.googleMapsUri",
        "nextPageToken",
    ]
)

PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


class GooglePlacesProvider(BaseProvider):
    source = "google"
    base_url = "https://places.googleapis.com/v1"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.google_places_api_key
        if not self.api_key:
            raise ProviderError(
                "Не задан GOOGLE_PLACES_API_KEY. Укажите ключ в backend/.env "
                "или используйте источник demo."
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
        per_category = max(1, min(20, limit // len(categories) + 1))
        results: list[PlaceResult] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            for category in categories:
                text_query = query or f"{category} {city}".strip()
                page_token: str | None = None
                for _ in range(3):
                    payload: dict = {
                        "textQuery": text_query,
                        "languageCode": "ru",
                        "regionCode": "RU",
                        "pageSize": per_category,
                    }
                    if latitude is not None and longitude is not None:
                        location_bias: dict = {
                            "circle": {
                                "center": {"latitude": latitude, "longitude": longitude},
                                "radius": float(radius or 5000),
                            }
                        }
                        payload["locationBias"] = location_bias
                    if page_token:
                        payload["pageToken"] = page_token

                    response = await client.post(
                        f"{self.base_url}/places:searchText",
                        headers={
                            "X-Goog-Api-Key": self.api_key,
                            "X-Goog-FieldMask": FIELD_MASK,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code >= 400:
                        detail = response.text[:300]
                        raise ProviderError(f"Google Places API: {response.status_code} {detail}")

                    data = response.json()
                    for place in data.get("places", []):
                        source_id = place.get("id")
                        if not source_id or source_id in seen:
                            continue
                        seen.add(source_id)
                        results.append(self._to_place(place, category or None))
                        if len(results) >= limit:
                            return results

                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                    await asyncio.sleep(0.2)
        return results

    def _to_place(self, place: dict, fallback_category: str | None) -> PlaceResult:
        location = place.get("location") or {}
        primary = (place.get("primaryTypeDisplayName") or {}).get("text")
        return PlaceResult(
            name=(place.get("displayName") or {}).get("text", "Без названия"),
            category=fallback_category or primary or "Бизнес",
            city="",
            address=place.get("formattedAddress", ""),
            phone=place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
            website_url=place.get("websiteUri"),
            rating=place.get("rating"),
            reviews_count=int(place.get("userRatingCount") or 0),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            opening_hours=(place.get("regularOpeningHours") or {}).get("weekdayDescriptions", []),
            price_level=PRICE_LEVELS.get(place.get("priceLevel", "")),
            source=self.source,
            source_id=place.get("id"),
        )
