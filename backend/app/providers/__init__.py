from __future__ import annotations

from app.providers.base import BaseProvider, PlaceResult, ProviderError
from app.providers.demo import DemoProvider
from app.providers.google import GooglePlacesProvider
from app.providers.osm import OSMProvider
from app.providers.scraper import ScraperProvider
from app.providers.twogis import TwoGisProvider
from app.providers.vk import VKProvider
from app.providers.yandex import YandexMapsProvider
from app.providers.yandex_web import YandexMapsWebProvider
from app.providers.zoon import ZoonProvider


def get_provider(source: str) -> BaseProvider:
    match source:
        case "demo":
            return DemoProvider()
        case "google":
            return GooglePlacesProvider()
        case "twogis":
            return TwoGisProvider()
        case "yandex":
            return YandexMapsProvider()
        case "yandex_web":
            return YandexMapsWebProvider()
        case "osm":
            return OSMProvider()
        case "scraper":
            return ScraperProvider()
        case "vk":
            return VKProvider()
        case "zoon":
            return ZoonProvider()
        case _:
            raise ProviderError(f"Неизвестный источник данных: {source}")


__all__ = [
    "BaseProvider",
    "DemoProvider",
    "GooglePlacesProvider",
    "OSMProvider",
    "PlaceResult",
    "ProviderError",
    "ScraperProvider",
    "TwoGisProvider",
    "VKProvider",
    "YandexMapsProvider",
    "YandexMapsWebProvider",
    "ZoonProvider",
    "get_provider",
]
