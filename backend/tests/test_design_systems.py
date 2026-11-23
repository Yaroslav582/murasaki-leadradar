from __future__ import annotations

import pytest
from app.services.design_systems import (
    STYLES_CATALOG,
    build_llm_design_context,
    detect_style_by_category,
    get_all_styles,
    get_style,
    load_design_md_file,
    resolve_style_id,
)
from app.services.landing import generate_landing_html, render_jinja_demo


def test_all_six_styles_exist_and_have_design_md():
    expected_styles = [
        "dark_cyber_neon",
        "warm_artisan_coffee",
        "luxury_editorial",
        "acid_neo_brutalism",
        "clean_swiss_trust",
        "playful_pastel",
    ]
    all_styles = get_all_styles()
    style_ids = [s["id"] for s in all_styles]

    for expected in expected_styles:
        assert expected in style_ids
        raw_md = load_design_md_file(expected)
        assert len(raw_md) > 100
        assert "version: alpha" in raw_md or "Design System" in raw_md
        assert "colors:" in raw_md or "Colors" in raw_md


def test_style_resolution_and_niche_detection():
    # Direct match
    assert resolve_style_id("dark_cyber_neon") == "dark_cyber_neon"
    assert resolve_style_id("luxury_editorial") == "luxury_editorial"

    # Aliases
    assert resolve_style_id("dark_industrial") == "dark_cyber_neon"
    assert resolve_style_id("editorial_light") == "luxury_editorial"
    assert resolve_style_id("warm_appetite") == "warm_artisan_coffee"
    assert resolve_style_id("clean_trust") == "clean_swiss_trust"

    # Niche auto-detection
    assert detect_style_by_category("Автосервис") == "dark_cyber_neon"
    assert detect_style_by_category("Кофейня и выпечка") == "warm_artisan_coffee"
    assert detect_style_by_category("Салон красоты и спа") == "luxury_editorial"
    assert detect_style_by_category("Digital агентство") == "acid_neo_brutalism"
    assert detect_style_by_category("Бабл-ти бар") == "playful_pastel"
    assert detect_style_by_category("Юридическая фирма") == "clean_swiss_trust"


def test_llm_design_context_contains_tokens():
    ctx = build_llm_design_context("dark_cyber_neon", "Автосервис")
    assert "DESIGN.md" in ctx
    assert "#FF4500" in ctx
    assert "Unbounded" in ctx


def test_rendering_each_style_generates_valid_html():
    lead = {
        "name": "Тестовая Компания",
        "category": "Услуги",
        "city": "Москва",
        "address": "ул. Тестовая, 1",
        "phone": "+7 999 111-22-33",
        "rating": 4.9,
        "reviews_count": 28,
        "photos": ["https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800"],
    }

    content_json = {
        "hero_title": "Премиальное качество для вас",
        "hero_subtitle": "Быстрая запись за 1 минуту",
        "usp_list": [{"title": "Опыт", "desc": "Более 5 лет"}],
        "services": [{"name": "Базовая услуга", "price": "от 2000 ₽", "desc": "Под ключ"}],
        "faq": [{"question": "Как записаться?", "answer": "Нажмите кнопку"}],
    }

    styles = [
        "dark_cyber_neon",
        "warm_artisan_coffee",
        "luxury_editorial",
        "acid_neo_brutalism",
        "clean_swiss_trust",
        "playful_pastel",
    ]

    for s_id in styles:
        html = render_jinja_demo(
            template_id=s_id,
            business_dict=lead,
            content_json=content_json,
            hero_image=lead["photos"][0],
            gallery_photos=[],
        )
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
        assert "Тестовая Компания" in html
        assert "Murasaki_website" in html


@pytest.mark.asyncio
async def test_api_styles_endpoint(client):
    response = await client.get("/api/demos/styles")
    assert response.status_code == 200
    data = response.json()
    assert "styles" in data
    assert len(data["styles"]) == 6
    ids = [s["id"] for s in data["styles"]]
    assert "dark_cyber_neon" in ids
    assert "warm_artisan_coffee" in ids
