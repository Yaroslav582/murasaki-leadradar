"""
Service for managing DESIGN.md design systems inspired by VoltAgent/awesome-design-md.
Provides design token definitions, moodboards, typography specs, and LLM design context.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DESIGN_SYSTEMS_DIR = Path(__file__).resolve().parent.parent / "design_systems"

# Mapping from style ID to canonical metadata and aliases
STYLES_CATALOG: dict[str, dict[str, Any]] = {
    "dark_cyber_neon": {
        "id": "dark_cyber_neon",
        "name": "Dark Cyber Neon",
        "name_ru": "Тёмный кибер / Неон",
        "description": "Глубокий графитовый фон, неоновые оранжево-бирюзовые акценты, технологичные бейджи и матовая эстетика. Идеально для мужского сегмента, авто и IT.",
        "tags": ["Авто", "Детейлинг", "IT / AI", "Киберспорт", "Барбершопы", "Спорт"],
        "preview_colors": {
            "bg": "#08090C",
            "card": "#12141C",
            "accent": "#FF4500",
            "text": "#F8FAFC",
            "subtext": "#94A3B8",
            "badge_bg": "#1E2230",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Unbounded:wght@600;700;800;900&display=swap" rel="stylesheet">',
        "font_heading": "'Unbounded', sans-serif",
        "font_body": "'Inter', -apple-system, sans-serif",
        "recommended_niches": [
            "авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто",
            "барбер", "спорт", "стройк", "ремонт авто", "it", "компьютер", "техник"
        ],
        "template_file": "dark_cyber_neon.html",
        "legacy_template_alias": "dark_industrial",
    },
    "warm_artisan_coffee": {
        "id": "warm_artisan_coffee",
        "name": "Warm Artisan Coffee",
        "name_ru": "Тёплый крафт и кофе",
        "description": "Уютная пергаментная палитра, аппетитные кофейно-карамельные акценты, шрифты с засечками и крафтовая тактильность. Атмосфера тепла и свежей выпечки.",
        "tags": ["Кофейни", "Пекарни", "Кондитерские", "Рестораны", "Доставка еды"],
        "preview_colors": {
            "bg": "#FAF6F0",
            "card": "#FFFFFF",
            "accent": "#C85A32",
            "text": "#281D17",
            "subtext": "#63534B",
            "badge_bg": "#F2ECE4",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Playfair Display', Georgia, serif",
        "font_body": "'Plus Jakarta Sans', -apple-system, sans-serif",
        "recommended_niches": [
            "ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "пицц", "суши", "бургер", "бар", "кухн", "кондитер", "еда"
        ],
        "template_file": "warm_artisan_coffee.html",
        "legacy_template_alias": "warm_appetite",
    },
    "luxury_editorial": {
        "id": "luxury_editorial",
        "name": "Luxury Editorial",
        "name_ru": "Премиум глянец и эстетика",
        "description": "Элегантная журнальная эстетика, алебастровый фон, утончённые шрифты с засечками, шалфейные и золотые детали. Для индустрии красоты и премиум-сегмента.",
        "tags": ["Бьюти", "Косметология", "Спа", "Мода", "Архитектура", "Дизайн интерьера"],
        "preview_colors": {
            "bg": "#F7F5F0",
            "card": "#FFFFFF",
            "accent": "#3E5848",
            "text": "#18181B",
            "subtext": "#52525B",
            "badge_bg": "#EFEAE1",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Cormorant Garamond', 'Playfair Display', Georgia, serif",
        "font_body": "'Inter', -apple-system, sans-serif",
        "recommended_niches": [
            "бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "цветы", "одежд", "спа", "ногти", "брови", "массаж"
        ],
        "template_file": "luxury_editorial.html",
        "legacy_template_alias": "editorial_light",
    },
    "acid_neo_brutalism": {
        "id": "acid_neo_brutalism",
        "name": "Acid Neo-Brutalism",
        "name_ru": "Нео-брутализм и диджитал",
        "description": "Дерзкий контраст тёмного графита и кислотно-лаймового (#D4FF00), массивный акцидентный гротеск, стикеры и резкая геометрия. Для агентств и ярких брендов.",
        "tags": ["Digital-агентства", "Streetwear", "Тату", "Студии", "Мерч", "Креатив"],
        "preview_colors": {
            "bg": "#0D0E12",
            "card": "#161822",
            "accent": "#D4FF00",
            "text": "#FFFFFF",
            "subtext": "#CBD5E1",
            "badge_bg": "#222533",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Syne', sans-serif",
        "font_body": "'Space Grotesk', -apple-system, sans-serif",
        "recommended_niches": [
            "агентств", "дизайн", "digital", "маркетинг", "тату", "стритвер", "streetwear", "музык", "шоу", "мото"
        ],
        "template_file": "acid_neo_brutalism.html",
        "legacy_template_alias": "dark_industrial",
    },
    "clean_swiss_trust": {
        "id": "clean_swiss_trust",
        "name": "Clean Swiss Trust",
        "name_ru": "Швейцарский минимализм",
        "description": "Чистый белый холст, строгая сетка, королевский синий акцент, плашки гарантий и лицензий. Высочайший уровень солидности и доверия для B2B и медицины.",
        "tags": ["Медицина", "Юристы", "Стоматология", "B2B", "Недвижимость", "Клининг"],
        "preview_colors": {
            "bg": "#F8FAFC",
            "card": "#FFFFFF",
            "accent": "#2563EB",
            "text": "#0F172A",
            "subtext": "#475569",
            "badge_bg": "#EDF2F7",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">',
        "font_heading": "'Inter', -apple-system, sans-serif",
        "font_body": "'Inter', -apple-system, sans-serif",
        "recommended_niches": [
            "медицин", "клиник", "стоматолог", "юрист", "адвокат", "бухгалтер", "аудит", "нотариус", "b2b", "недвижим", "клининг", "ремонт"
        ],
        "template_file": "clean_swiss_trust.html",
        "legacy_template_alias": "clean_trust",
    },
    "playful_pastel": {
        "id": "playful_pastel",
        "name": "Playful Pastel & Sweet",
        "name_ru": "Игривый пастельный и фреш",
        "description": "Нежная ягодная палитра, мягкие скругления (pills), сочные малиново-клубничные акценты, дружелюбные округлые шрифты. Для сладкого, бабл-ти и радости.",
        "tags": ["Бабл-ти", "Десерты", "Торты", "Детские центры", "Зоосалоны", "Подарки"],
        "preview_colors": {
            "bg": "#FFF4F6",
            "card": "#FFFFFF",
            "accent": "#E11D48",
            "text": "#38141F",
            "subtext": "#75394A",
            "badge_bg": "#FFE4E8",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Comfortaa:wght@600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Comfortaa', cursive, sans-serif",
        "font_body": "'Plus Jakarta Sans', -apple-system, sans-serif",
        "recommended_niches": [
            "бабл-ти", "мороженое", "торт", "десерт", "сладост", "дети", "детск", "зоо", "груминг", "подарк", "шары", "праздник"
        ],
        "template_file": "playful_pastel.html",
        "legacy_template_alias": "warm_appetite",
    },
}

# Alias mapping for backwards compatibility
STYLE_ALIASES = {
    "editorial_light": "luxury_editorial",
    "dark_industrial": "dark_cyber_neon",
    "warm_appetite": "warm_artisan_coffee",
    "clean_trust": "clean_swiss_trust",
    "clean_light": "luxury_editorial",
    "industrial_dark": "dark_cyber_neon",
    "warm_craft": "warm_artisan_coffee",
    "strict_corporate": "clean_swiss_trust",
    "modern_minimal": "dark_cyber_neon",
}


def load_design_md_file(style_id: str) -> str:
    """Reads raw DESIGN.md file content for a given style ID."""
    canonical_id = STYLE_ALIASES.get(style_id, style_id)
    path = DESIGN_SYSTEMS_DIR / canonical_id / "DESIGN.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read DESIGN.md for %s: %s", style_id, e)
    return ""


def get_all_styles() -> list[dict[str, Any]]:
    """Returns metadata for all available design styles including DESIGN.md preview."""
    results = []
    for s_id, s_info in STYLES_CATALOG.items():
        item = dict(s_info)
        raw_md = load_design_md_file(s_id)
        item["design_md"] = raw_md
        results.append(item)
    return results


def detect_style_by_category(category: str | None) -> str:
    """Smart heuristic to recommend the best matching design style by business category."""
    cat = (category or "").lower()
    
    # Check playful/sweet first so 'бабл-ти бар' doesn't get captured by generic 'бар'
    if any(k in cat for k in ("бабл", "bubble", "десерт", "торт", "сладост", "морожен", "детск", "игров", "зоо", "груминг", "шары")):
        return "playful_pastel"

    # Check creative/digital/neo-brutalism
    if any(k in cat for k in ("digital", "диджитал", "агентств", "streetwear", "стритвер", "тату", "мерч", "продакшн", "креатив")):
        return "acid_neo_brutalism"

    # Check beauty/luxury editorial
    if any(k in cat for k in ("бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "цветы", "одежд", "спа", "ногти", "брови", "массаж", "мода")):
        return "luxury_editorial"

    # Check coffee/bakery/food
    if any(k in cat for k in ("кофе", "пекарн", "кондитер", "выпечк", "ресторан", "кафе", "доставка еды", "пицц", "суши", "бургер", "кухн")):
        return "warm_artisan_coffee"

    # Check automotive/tech/cyber
    if any(k in cat for k in ("авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто", "барбер", "спорт", "стройк", "кибер", "gadget", "it-")):
        return "dark_cyber_neon"

    # Default to clean swiss trust for corporate, medical, legal, and other
    return "clean_swiss_trust"


def resolve_style_id(style_id: str | None, category: str | None = None) -> str:
    """Resolves any style string (or None) into a valid canonical style_id."""
    if not style_id or style_id.lower() in ("auto", "default", "none"):
        return detect_style_by_category(category)
    cleaned = style_id.lower().strip()
    if cleaned in STYLES_CATALOG:
        return cleaned
    if cleaned in STYLE_ALIASES:
        return STYLE_ALIASES[cleaned]
    return detect_style_by_category(category)


def get_style(style_id: str | None, category: str | None = None) -> dict[str, Any]:
    """Retrieves full design style metadata and token rules."""
    canonical_id = resolve_style_id(style_id, category)
    info = STYLES_CATALOG.get(canonical_id, STYLES_CATALOG["clean_swiss_trust"])
    result = dict(info)
    result["design_md"] = load_design_md_file(canonical_id)
    return result


def build_llm_design_context(style_id: str | None, category: str | None = None) -> str:
    """
    Constructs a formal DESIGN.md specification block to inject into AI LLM prompts,
    enforcing pixel-perfect alignment with VoltAgent/awesome-design-md standards.
    """
    style = get_style(style_id, category)
    md_content = style.get("design_md") or ""
    colors = style.get("preview_colors", {})
    heading_font = style.get("font_heading", "sans-serif")
    body_font = style.get("font_body", "sans-serif")

    return f"""
<!-- DESIGN.md Specification ({style['name']}) [VoltAgent/awesome-design-md standard] -->
ДИЗАЙН-КОД СТИЛЯ: «{style['name_ru']}» ({style['name']})
1. ЦВЕТОВЫЕ ТОКЕНЫ:
   - Основной фон (Canvas): {colors.get('bg')}
   - Фон карточек (Surface): {colors.get('card')}
   - Главный акцент (Primary Action): {colors.get('accent')}
   - Цвет заголовков: {colors.get('text')}
   - Цвет подзаголовков/текста: {colors.get('subtext')}
2. ТИПОГРАФИКА:
   - Шрифты Google Fonts: {heading_font} (для заголовков), {body_font} (для основного текста)
   - Подключи Google Fonts в <head>: {style.get('font_css', '')}
3. АТМОСФЕРА И ПРАВИЛА:
   {style.get('description', '')}

Полная спецификация DESIGN.md:
{md_content[:1200]}
"""
