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


EXPECTED_TWENTY_FOUR_STYLES = [
    "dark_cyber_neon",
    "warm_artisan_coffee",
    "luxury_editorial",
    "acid_neo_brutalism",
    "clean_swiss_trust",
    "playful_pastel",
    "vintage_barber_leather",
    "industrial_heavy_steel",
    "organic_botanical_sage",
    "tokyo_neo_izakaya",
    "kinetic_sport_volt",
    "bold_diner_grill",
    "architectural_brutal_loft",
    "nordic_hygge_wood",
    "midnight_velvet_lounge",
    "clean_tech_lab",
    "nature_camp_glamping",
    "modern_edtech_campus",
    "friendly_pet_care",
    "obsidian_gold_luxury",
    "matte_graphite_titanium",
    "monochrome_slate_studio",
    "cool_grey_concrete",
    "deep_slate_fintech",
]


def test_all_twenty_four_styles_exist_and_have_design_md():
    all_styles = get_all_styles()
    assert len(all_styles) == 24
    style_ids = [s["id"] for s in all_styles]

    for expected in EXPECTED_TWENTY_FOUR_STYLES:
        assert expected in style_ids
        raw_md = load_design_md_file(expected)
        assert len(raw_md) > 100
        assert "version: alpha" in raw_md or "Design System" in raw_md
        assert "colors:" in raw_md or "Colors" in raw_md


def test_style_resolution_and_niche_detection():
    # Direct match
    assert resolve_style_id("dark_cyber_neon") == "dark_cyber_neon"
    assert resolve_style_id("obsidian_gold_luxury") == "obsidian_gold_luxury"
    assert resolve_style_id("vintage_barber_leather") == "vintage_barber_leather"
    assert resolve_style_id("matte_graphite_titanium") == "matte_graphite_titanium"
    assert resolve_style_id("monochrome_slate_studio") == "monochrome_slate_studio"

    # Aliases
    assert resolve_style_id("dark_industrial") == "dark_cyber_neon"
    assert resolve_style_id("editorial_light") == "luxury_editorial"
    assert resolve_style_id("warm_appetite") == "warm_artisan_coffee"
    assert resolve_style_id("clean_trust") == "clean_swiss_trust"

    # Niche auto-detection for all 24 categories
    assert detect_style_by_category("Фотостудия и видеосъемка") == "monochrome_slate_studio"
    assert detect_style_by_category("Финансовый консалтинг и инвестиции") == "deep_slate_fintech"
    assert detect_style_by_category("Керамогранит и вентилируемые фасады") == "cool_grey_concrete"
    assert detect_style_by_category("Hi-Fi аудио и акустика") == "matte_graphite_titanium"
    assert detect_style_by_category("Барбершоп и стрижка") == "vintage_barber_leather"
    assert detect_style_by_category("Строительство и спецтехника") == "industrial_heavy_steel"
    assert detect_style_by_category("Цветы и флористика") == "organic_botanical_sage"
    assert detect_style_by_category("Суши и рамен бар") == "tokyo_neo_izakaya"
    assert detect_style_by_category("Фитнес и кроссфит") == "kinetic_sport_volt"
    assert detect_style_by_category("Бургерная и гриль") == "bold_diner_grill"
    assert detect_style_by_category("Дизайн интерьера и лофт") == "architectural_brutal_loft"
    assert detect_style_by_category("Клининг и химчистка") == "nordic_hygge_wood"
    assert detect_style_by_category("Кальянная и лаунж") == "midnight_velvet_lounge"
    assert detect_style_by_category("Ремонт телефонов и ноутбуков") == "clean_tech_lab"
    assert detect_style_by_category("Глэмпинг и база отдыха") == "nature_camp_glamping"
    assert detect_style_by_category("Автошкола и курсы") == "modern_edtech_campus"
    assert detect_style_by_category("Ветклиника и груминг") == "friendly_pet_care"
    assert detect_style_by_category("Ювелирный салон и золото") == "obsidian_gold_luxury"
    assert detect_style_by_category("Автосервис и шиномонтаж") == "dark_cyber_neon"
    assert detect_style_by_category("Кофейня и выпечка") == "warm_artisan_coffee"
    assert detect_style_by_category("Салон красоты и спа") == "luxury_editorial"
    assert detect_style_by_category("Digital агентство") == "acid_neo_brutalism"
    assert detect_style_by_category("Бабл-ти и десерты") == "playful_pastel"
    assert detect_style_by_category("Юридическая фирма") == "clean_swiss_trust"


def test_llm_design_context_contains_tokens():
    ctx = build_llm_design_context("vintage_barber_leather", "Барбершоп")
    assert "DESIGN.md" in ctx
    assert "#C28840" in ctx
    assert "Oswald" in ctx

    ctx_graphite = build_llm_design_context("matte_graphite_titanium", "Аудио лаборатория")
    assert "DESIGN.md" in ctx_graphite
    assert "#94A3B8" in ctx_graphite
    assert "Manrope" in ctx_graphite


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
        "advantages": [{"title": "Опыт", "text": "Более 5 лет"}],
        "services": [{"name": "Базовая услуга", "price": "от 2000 ₽", "desc": "Под ключ"}],
        "about_text": "Мы заботимся о каждом клиенте.",
        "reviews": [{"author": "Алексей", "text": "Отличный сервис!"}],
    }

    for s_id in EXPECTED_TWENTY_FOUR_STYLES:
        html = render_jinja_demo(
            template_id=s_id,
            business_dict=lead,
            content_json=content_json,
            hero_image=lead["photos"][0],
            gallery_photos=[],
        )
        assert "<!DOCTYPE html>" in html
        assert lead["name"] in html
        assert "Murasaki_website" in html
