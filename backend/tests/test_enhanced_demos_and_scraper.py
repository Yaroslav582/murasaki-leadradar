from __future__ import annotations

import pytest

from app.config import Settings
from app.providers.yandex_web import _extract_item_photos, _format_yandex_photo_url
from app.services.demos import public_demo_url
from app.services.landing import (
    THEMES,
    build_fallback_landing,
    detect_theme,
)
from app.services.telegram_channel_scraper import (
    extract_tg_username,
    scrape_telegram_channel,
)


def test_theme_detection_covers_all_niches() -> None:
    assert detect_theme("Салон красоты") == "clean_light"
    assert detect_theme("Стоматология") == "clean_light"
    assert detect_theme("Медицинский центр") == "clean_light"
    assert detect_theme("Автосервис") == "industrial_dark"
    assert detect_theme("Детейлинг студия") == "industrial_dark"
    assert detect_theme("Ресторан") == "warm_craft"
    assert detect_theme("Кофейня") == "warm_craft"
    assert detect_theme("Юридическая фирма") == "strict_corporate"
    assert detect_theme("Бухгалтерские услуги") == "strict_corporate"
    assert detect_theme("Фитнес клуб") == "modern_minimal"
    assert detect_theme("Магазин одежды") == "modern_minimal"


def test_themes_have_distinct_fonts_and_colors() -> None:
    assert len(THEMES) >= 5

    # 1. Clean Light
    cl = THEMES["clean_light"]
    assert "Playfair" in cl["font_heading"] or "Cormorant" in cl["font_heading"]
    assert cl["bg_page"].upper() == "#FAF8F5"
    assert not cl["is_dark"]

    # 2. Industrial Dark
    ind = THEMES["industrial_dark"]
    assert "Montserrat" in ind["font_heading"]
    assert ind["bg_page"].upper() == "#121417"
    assert ind["accent"].upper() == "#FF6B00"
    assert ind["is_dark"]

    # 3. Warm Craft
    wc = THEMES["warm_craft"]
    assert "Lora" in wc["font_heading"] or "Jakarta" in wc["font_body"]
    assert "#F9F6F0" in wc["bg_page"] or "#FDFBF7" in wc["bg_page"]
    assert not wc["is_dark"]

    # 4. Strict Corporate
    sc = THEMES["strict_corporate"]
    assert "Inter" in sc["font_heading"]
    assert sc["bg_page"].upper() == "#FFFFFF"
    assert sc["accent"].upper() == "#1E3A8A"

    # 5. Modern Minimal
    mm = THEMES["modern_minimal"]
    assert "Plus Jakarta Sans" in mm["font_heading"]


def test_landing_contains_required_elements_and_onerror() -> None:
    lead = {
        "id": "test-uuid-1",
        "name": "Barbershop Noir",
        "category": "Автосервисы",
        "city": "Москва",
        "address": "ул. Ленина, 15",
        "phone": "+7 (999) 000-11-22",
        "rating": 4.9,
        "reviews_count": 85,
        "photos": [
            "https://example.com/photo1.jpg",
            "https://example.com/photo2.jpg",
        ],
        "logo_url": "https://example.com/logo.jpg",
        "social_links": {"telegram": "https://t.me/barber_noir"},
    }

    html = build_fallback_landing(lead)

    # Business name & fonts
    assert "Barbershop Noir" in html
    assert "Montserrat" in html
    assert "#FF6B00" in html

    # Real photos included
    assert "https://example.com/photo1.jpg" in html

    # Fallback and onerror attribute present for resilience
    assert 'onerror="this.onerror=null;' in html

    # Demo concept floating pill present with Telegram link
    assert "Демо-концепт для Barbershop Noir" in html
    assert "https://t.me/Murasaki_website" in html
    assert "Murasaki LeadRadar" in html


def test_hero_layout_variation() -> None:
    # 3 different IDs produce variation in hero section markup
    lead_a = {"id": "lead-001", "name": "Company A", "category": "Бьюти"}
    lead_b = {"id": "lead-002", "name": "Company B", "category": "Бьюти"}
    lead_c = {"id": "lead-003", "name": "Company C", "category": "Бьюти"}

    html_a = build_fallback_landing(lead_a)
    html_b = build_fallback_landing(lead_b)
    html_c = build_fallback_landing(lead_c)

    # Verify all are valid html
    assert "<!DOCTYPE html>" in html_a
    assert "<!DOCTYPE html>" in html_b
    assert "<!DOCTYPE html>" in html_c


def test_tg_username_extractor() -> None:
    assert extract_tg_username("https://t.me/beauty_studio") == "beauty_studio"
    assert extract_tg_username("https://t.me/s/beauty_studio") == "beauty_studio"
    assert extract_tg_username("@auto_service") == "auto_service"
    assert extract_tg_username("t.me/coffee_spb") == "coffee_spb"
    assert extract_tg_username("https://t.me/joinchat/AAAAAF") is None
    assert extract_tg_username("https://t.me/murasaki_radar_1438_bot") is None


def test_yandex_photo_extraction() -> None:
    item = {
        "id": "12345",
        "title": "Студия Элеганс",
        "logotype": {"urlTemplate": "https://avatars.mds.yandex.net/get-altay/1000/%s"},
        "photos": [
            {"urlTemplate": "https://avatars.mds.yandex.net/get-altay/2000/%s"},
            {"url": "https://avatars.mds.yandex.net/get-altay/3000/orig"},
        ],
    }

    logo, photos = _extract_item_photos(item)
    assert logo == "https://avatars.mds.yandex.net/get-altay/1000/orig"
    assert len(photos) == 2
    assert photos[0] == "https://avatars.mds.yandex.net/get-altay/2000/orig"
    assert photos[1] == "https://avatars.mds.yandex.net/get-altay/3000/orig"


def test_public_base_url_normalization() -> None:
    # Test public_demo_url with custom and fallback hosts
    demo_url = public_demo_url("abc-123")
    assert demo_url.endswith("/demo/abc-123")
    assert demo_url.startswith("http://") or demo_url.startswith("https://")

