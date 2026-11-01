from __future__ import annotations

from app.providers.yandex_web import org_page_to_place

BODY = """ЯА Студия
5
До 22:00
Карты · Москва · Салоны бровей и ресниц
ЯА Студия
Рейтинг 
5,0
184 оценки
Открыто до 22:00
+7 (999) 910-93-63
Показать телефон
Адрес
Котельническая наб., 33, корп. 1, Москварядом белая дверь, подъезд 3
Показать входыМаршрут
Контакты
+7 (999) 910-93-63
ya-prolash.ru
"""

LINKS = [
    "http://ya-prolash.ru/?erid=3MtFQRkqfB2huzBcHHttGQXVu4UF2Q",
    "https://ya-prolash.ru/",
    "https://t.me/ya_prolash",
    "https://t.me/mapsyandex",
    "https://wa.me/79990000000?text=%D0%9E%D0%B1%D1%80%D0%B0%D1%89%D0%B5%D0%BD%D0%B8%D0%B5+%D0%B8%D0%B7+%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81+%D0%9A%D0%B0%D1%80%D1%82",
    "https://wa.me/79999109363?text=hello",
    "https://www.youtube.com/@ya_prolash",
    "https://yandex.ru/maps/",
]


def test_org_page_to_place() -> None:
    place = org_page_to_place(
        name="ЯА Студия",
        title="ЯА Студия, салон бровей и ресниц, Котельническая наб., 33, корп. 1, Москва — Яндекс Карты",
        url="https://yandex.ru/maps/org/yaa_studiya/57116436027/?ll=37.648097%2C55.740735&z=16",
        body=BODY,
        external_links=LINKS,
        city="Москва",
        fallback_category="Бьюти",
    )
    assert place is not None
    assert place.name == "ЯА Студия"
    assert place.category == "Бьюти"
    assert place.phone == "+7 (999) 910-93-63"
    assert place.website_url == "https://ya-prolash.ru/"
    assert place.social_links["telegram"] == "https://t.me/ya_prolash"
    assert place.social_links["whatsapp"].startswith("https://wa.me/79999109363")
    assert "79990000000" not in place.social_links["whatsapp"]
    assert place.address.startswith("Котельническая наб., 33, корп. 1, Москва")
    assert place.rating == 5.0
    assert place.reviews_count == 184
    assert place.opening_hours == ["Открыто до 22:00"]
    assert place.latitude == 55.740735
    assert place.longitude == 37.648097
    assert place.source == "yandex_web"
    assert place.source_id == "57116436027"


def test_org_page_without_id_is_skipped() -> None:
    place = org_page_to_place(
        name="Без ID",
        title="Без ID",
        url="https://yandex.ru/maps/",
        body=BODY,
        external_links=[],
        city="Москва",
        fallback_category="Бьюти",
    )
    assert place is None
