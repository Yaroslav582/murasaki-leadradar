from __future__ import annotations

import pytest

from app.config import settings
from app.providers.base import ProviderError
from app.providers.yandex import YandexMapsProvider, feature_to_place

FEATURE = {
    "geometry": {"type": "Point", "coordinates": [37.6, 55.7]},
    "properties": {
        "CompanyMetaData": {
            "id": "123456",
            "name": "Студия Aurora",
            "address": "Москва, ул. Тверская, 10",
            "Phones": [{"formatted": "+7 (999) 123-45-67"}],
            "Urls": [
                {"url": "https://aurora.ru"},
                {"url": "https://t.me/aurora"},
            ],
            "Categories": [{"name": "Салон красоты"}],
            "Hours": {"text": "Ежедневно 10:00–21:00"},
            "rating": {"score": "4.8", "count": "124"},
        }
    },
}


def test_feature_to_place() -> None:
    place = feature_to_place(FEATURE, "Москва", "Бьюти")
    assert place is not None
    assert place.name == "Студия Aurora"
    assert place.category == "Бьюти"
    assert place.phone == "+7 (999) 123-45-67"
    assert place.website_url == "https://aurora.ru"
    assert place.social_links["telegram"] == "https://t.me/aurora"
    assert place.rating == 4.8
    assert place.reviews_count == 124
    assert place.latitude == 55.7
    assert place.longitude == 37.6
    assert place.opening_hours == ["Ежедневно 10:00–21:00"]
    assert place.source == "yandex"
    assert place.source_id == "123456"


def test_feature_without_company_is_skipped() -> None:
    assert feature_to_place({"properties": {}}, "Москва", "Бьюти") is None


def test_provider_requires_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "yandex_maps_api_key", None)
    with pytest.raises(ProviderError, match="YANDEX_MAPS_API_KEY"):
        YandexMapsProvider()
