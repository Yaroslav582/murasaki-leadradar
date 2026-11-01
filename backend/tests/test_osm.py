from __future__ import annotations

from app.providers.osm import (
    build_overpass_query,
    detect_category,
    element_to_place,
    nominatim_item_to_place,
)


def test_build_overpass_query_for_city_and_categories() -> None:
    query = build_overpass_query(
        city="Москва",
        categories=["Бьюти", "Рестораны"],
        query=None,
        limit=25,
    )
    assert "55.6058,37.3673,55.9058,37.8673" in query
    assert "shop" in query and "beauty" in query
    assert "amenity" in query and "restaurant" in query
    assert "out center 100;" in query
    assert "автосервис" not in query


def test_build_overpass_query_for_unknown_city_uses_area() -> None:
    query = build_overpass_query(
        city="Урюпинск",
        categories=["Бьюти"],
        query=None,
        limit=10,
    )
    assert 'area["name"="Урюпинск"]' in query
    assert "(area.a)" in query


def test_build_overpass_query_around_coordinates() -> None:
    query = build_overpass_query(
        city="Москва",
        categories=["Медицина"],
        query=None,
        limit=10,
        latitude=55.75,
        longitude=37.61,
        radius=3000,
    )
    assert "around:3000,55.75,37.61" in query
    assert "area[" not in query


def test_element_to_place_enriches_contacts() -> None:
    element = {
        "type": "node",
        "id": 123,
        "lat": 55.76,
        "lon": 37.6,
        "tags": {
            "name": "Студия Aurora",
            "shop": "beauty",
            "phone": "+7 (999) 123-45-67",
            "website": "aurora.ru",
            "contact:telegram": "@aurora",
            "contact:whatsapp": "+7 999 123-45-67",
            "email": "hi@aurora.ru",
            "addr:street": "ул. Тверская",
            "addr:housenumber": "10",
            "opening_hours": "Mo-Fr 10:00-21:00; Sa 11:00-18:00",
        },
    }
    place = element_to_place(element, "Москва")
    assert place is not None
    assert place.name == "Студия Aurora"
    assert place.category == "Бьюти"
    assert place.website_url == "https://aurora.ru"
    assert place.social_links["telegram"] == "https://t.me/aurora"
    assert place.social_links["whatsapp"] == "https://wa.me/79991234567"
    assert place.emails == ["hi@aurora.ru"]
    assert place.address == "Москва, ул. Тверская, 10"
    assert place.opening_hours == ["Mo-Fr 10:00-21:00", "Sa 11:00-18:00"]
    assert place.source_id == "node/123"


def test_element_without_actionable_contacts_is_skipped() -> None:
    element = {
        "type": "way",
        "id": 456,
        "center": {"lat": 55.7, "lon": 37.6},
        "tags": {"name": "Кафе без контактов", "amenity": "cafe"},
    }
    assert element_to_place(element, "Москва") is None


def test_element_without_business_tag_is_skipped() -> None:
    element = {
        "type": "node",
        "id": 789,
        "lat": 55.7,
        "lon": 37.6,
        "tags": {"name": "Просто точка", "phone": "+79990000000"},
    }
    assert element_to_place(element, "Москва") is None


def test_detect_category() -> None:
    assert detect_category({"shop": "car_repair"}) == "Автосервисы"
    assert detect_category({"amenity": "dentist"}) == "Медицина"
    assert detect_category({"leisure": "fitness_centre"}) == "Фитнес"
    assert detect_category({"tourism": "hotel"}) == "Отели"
    assert detect_category({"shop": "clothes"}) == "Магазины"
    assert detect_category({"craft": "carpenter"}) == "Услуги"


def test_nominatim_item_to_place() -> None:
    item = {
        "osm_type": "node",
        "osm_id": 11274527557,
        "lat": "55.5487043",
        "lon": "37.5599016",
        "category": "shop",
        "type": "beauty",
        "name": "Салон Аврора",
        "address": {
            "house_number": "23",
            "road": "Ливенская улица",
            "city": "Москва",
        },
        "extratags": {
            "phone": "7 (904) 567-51-34",
            "opening_hours": "Mo-Su 09:00-21:00",
        },
    }
    place = nominatim_item_to_place(item, "Москва")
    assert place is not None
    assert place.name == "Салон Аврора"
    assert place.category == "Бьюти"
    assert place.phone == "7 (904) 567-51-34"
    assert place.address == "Москва, Ливенская улица, 23"
    assert place.source_id == "node/11274527557"
    assert place.opening_hours == ["Mo-Su 09:00-21:00"]

