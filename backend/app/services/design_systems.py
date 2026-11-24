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

# Mapping from style ID to canonical metadata, colors, typography and niche rules
STYLES_CATALOG: dict[str, dict[str, Any]] = {
    "dark_cyber_neon": {
        "id": "dark_cyber_neon",
        "name": "Dark Cyber Neon",
        "name_ru": "Тёмный кибер / Неон",
        "description": "Глубокий графитовый фон, неоновые оранжево-бирюзовые акценты, технологичные бейджи и матовая эстетика. Идеально для мужского сегмента, авто и IT.",
        "tags": ["Авто", "Детейлинг", "IT / AI", "Киберспорт", "Сервисы", "Спорт"],
        "tone": "dark",
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
            "ремонт авто", "it", "компьютер", "техник", "кибер"
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
        "tone": "light",
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
            "ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "выпечк", "кондитер", "чай"
        ],
        "template_file": "warm_artisan_coffee.html",
        "legacy_template_alias": "warm_appetite",
    },
    "luxury_editorial": {
        "id": "luxury_editorial",
        "name": "Luxury Editorial",
        "name_ru": "Премиум глянец и эстетика",
        "description": "Элегантная журнальная эстетика, алебастровый фон, утончённые шрифты с засечками, шалфейные и золотые детали. Для бьюти-индустрии и премиум-сегмента.",
        "tags": ["Бьюти", "Косметология", "Спа", "Мода", "Парикмахерские", "Массаж"],
        "tone": "light",
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
            "бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "одежд", "спа", "ногти", "брови", "массаж", "мода"
        ],
        "template_file": "luxury_editorial.html",
        "legacy_template_alias": "editorial_light",
    },
    "acid_neo_brutalism": {
        "id": "acid_neo_brutalism",
        "name": "Acid Neo-Brutalism",
        "name_ru": "Кислотный нео-брутализм",
        "description": "Дерзкий контраст тёмного графита и кислотно-лаймового (#D4FF00), массивный акцидентный гротеск, стикеры и резкая геометрия. Для агентств и ярких брендов.",
        "tags": ["Digital-агентства", "Streetwear", "Студии", "Мерч", "Креатив", "Маркетинг"],
        "tone": "vibrant",
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
            "агентств", "дизайн", "digital", "маркетинг", "стритвер", "streetwear", "музык", "шоу", "креатив"
        ],
        "template_file": "acid_neo_brutalism.html",
        "legacy_template_alias": "dark_industrial",
    },
    "clean_swiss_trust": {
        "id": "clean_swiss_trust",
        "name": "Clean Swiss Trust",
        "name_ru": "Швейцарский минимализм",
        "description": "Чистый белый холст, строгая сетка, королевский синий акцент, плашки гарантий и лицензий. Высочайший уровень солидности и доверия для B2B и медицины.",
        "tags": ["Медицина", "Юристы", "Стоматология", "B2B", "Бухгалтерия", "Аудит"],
        "tone": "light",
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
            "медицин", "клиник", "стоматолог", "юрист", "адвокат", "бухгалтер", "аудит", "нотариус", "b2b", "недвижим"
        ],
        "template_file": "clean_swiss_trust.html",
        "legacy_template_alias": "clean_trust",
    },
    "playful_pastel": {
        "id": "playful_pastel",
        "name": "Playful Pastel & Sweet",
        "name_ru": "Мягкая пастель и фреш",
        "description": "Нежная ягодная палитра, мягкие скругления (pills), сочные малиново-клубничные акценты, дружелюбные округлые шрифты. Для десертов, бабл-ти и радости.",
        "tags": ["Бабл-ти", "Десерты", "Торты", "Детские центры", "Подарки", "Праздники"],
        "tone": "light",
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
            "бабл", "bubble", "мороженое", "торт", "десерт", "сладост", "дети", "детск", "подарк", "шары", "праздник"
        ],
        "template_file": "playful_pastel.html",
        "legacy_template_alias": "warm_appetite",
    },
    "vintage_barber_leather": {
        "id": "vintage_barber_leather",
        "name": "Vintage Barber & Leather",
        "name_ru": "Винтажный барбер и кожа",
        "description": "Брутальная эстетика выделанной кожи, теплой латуни (#C28840) и дуба. Плотный ретро-гротеск Oswald, гербы, атмосфера мужского клуба и мастерства.",
        "tags": ["Барбершопы", "Тату", "Мастерские", "Мужской клуб", "Кожгалантерея"],
        "tone": "dark",
        "preview_colors": {
            "bg": "#1C1917",
            "card": "#292524",
            "accent": "#C28840",
            "text": "#FAFAF9",
            "subtext": "#A8A29E",
            "badge_bg": "#3F3935",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">',
        "font_heading": "'Oswald', sans-serif",
        "font_body": "'Roboto', system-ui, sans-serif",
        "recommended_niches": [
            "барбер", "барбершоп", "тату", "мастерск", "кожа", "мужск", "брить"
        ],
        "template_file": "vintage_barber_leather.html",
        "legacy_template_alias": "dark_cyber_neon",
    },
    "industrial_heavy_steel": {
        "id": "industrial_heavy_steel",
        "name": "Industrial Heavy Steel",
        "name_ru": "Индустриальный металл и стройка",
        "description": "Мощный индустриальный характер: холодная сталь, дорожно-строительный янтарный акцент (#F59E0B), сверхтяжёлый монолитный шрифт Russo One и надёжность.",
        "tags": ["Строительство", "Ремонт", "Спецтехника", "Металлопрокат", "Монтаж", "Производство"],
        "tone": "dark",
        "preview_colors": {
            "bg": "#1E2022",
            "card": "#2B2D31",
            "accent": "#F59E0B",
            "text": "#F3F4F6",
            "subtext": "#9CA3AF",
            "badge_bg": "#383B40",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Russo+One&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Russo One', sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "стройк", "строитель", "спецтехник", "металл", "бетон", "монтаж", "производств", "кран", "экскаватор", "кровл", "жби"
        ],
        "template_file": "industrial_heavy_steel.html",
        "legacy_template_alias": "dark_cyber_neon",
    },
    "organic_botanical_sage": {
        "id": "organic_botanical_sage",
        "name": "Organic Botanical Sage",
        "name_ru": "Ботаника и эко-органика",
        "description": "Спокойный шалфейный фон (#F3F6F2), глубокие лесные зелёные тона (#2D4A3E), воздушный шрифт Tenor Sans, дышащая верстка и природная утонченность.",
        "tags": ["Цветы", "Эко-лавки", "Йога", "Флористика", "Органика", "Сад"],
        "tone": "light",
        "preview_colors": {
            "bg": "#F3F6F2",
            "card": "#FFFFFF",
            "accent": "#2D4A3E",
            "text": "#1A2821",
            "subtext": "#4E6357",
            "badge_bg": "#E5ECE3",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Tenor+Sans&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Tenor Sans', serif",
        "font_body": "'Plus Jakarta Sans', system-ui, sans-serif",
        "recommended_niches": [
            "цветы", "флорист", "букет", "эко", "органик", "йог", "сад", "растени", "веган", "трав"
        ],
        "template_file": "organic_botanical_sage.html",
        "legacy_template_alias": "luxury_editorial",
    },
    "tokyo_neo_izakaya": {
        "id": "tokyo_neo_izakaya",
        "name": "Tokyo Neo-Izakaya",
        "name_ru": "Японский стритфуд и суши",
        "description": "Атмосфера вечернего Сибуя: глубокий графит (#121212), алые неоновые акценты (#E63946), плотная акцидентная типографика Dela Gothic One и яркие плашки меню.",
        "tags": ["Суши", "Рамен", "Доставка еды", "Азиатская кухня", "Япония", "Стритфуд"],
        "tone": "vibrant",
        "preview_colors": {
            "bg": "#121212",
            "card": "#1E1E1E",
            "accent": "#E63946",
            "text": "#FDF0D5",
            "subtext": "#A8A8A8",
            "badge_bg": "#2A1F21",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Dela Gothic One', cursive, sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "суши", "ролл", "рамен", "азиатск", "японск", "вок", "лапш", "том ям", "гёдза"
        ],
        "template_file": "tokyo_neo_izakaya.html",
        "legacy_template_alias": "warm_artisan_coffee",
    },
    "kinetic_sport_volt": {
        "id": "kinetic_sport_volt",
        "name": "Kinetic Sport Volt",
        "name_ru": "Фитнес-драйв и энергия",
        "description": "Высокооктановый спортивный стиль: тёмный фон спортзала (#0D0E12), агрессивный малиново-красный электро-акцент (#FF2A54), скошенные углы Chakra Petch.",
        "tags": ["Фитнес", "Кроссфит", "Единоборства", "Тренажерный зал", "Спорт", "Бокс"],
        "tone": "vibrant",
        "preview_colors": {
            "bg": "#0D0E12",
            "card": "#171922",
            "accent": "#FF2A54",
            "text": "#FFFFFF",
            "subtext": "#94A3B8",
            "badge_bg": "#271822",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Chakra Petch', sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "фитнес", "кроссфит", "единоборств", "бокс", "тренажер", "спортзал", "gym", "тренер", "бассейн", "борьб"
        ],
        "template_file": "kinetic_sport_volt.html",
        "legacy_template_alias": "dark_cyber_neon",
    },
    "bold_diner_grill": {
        "id": "bold_diner_grill",
        "name": "Bold Diner & Grill",
        "name_ru": "Сочный крафт и бургеры",
        "description": "Аппетитный винтажный дайнер: теплый кремовый фон (#FFF8EB), сочный томатно-красный акцент (#DC2626), массивные монолитные плашки Rubik Mono One.",
        "tags": ["Бургерные", "Пиццерии", "Стритфуд", "Гриль", "Барбекю", "Стейк-хаусы"],
        "tone": "vibrant",
        "preview_colors": {
            "bg": "#FFF8EB",
            "card": "#FFFFFF",
            "accent": "#DC2626",
            "text": "#2B1810",
            "subtext": "#6B4F3B",
            "badge_bg": "#FEEED4",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Rubik+Mono+One&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Rubik Mono One', sans-serif",
        "font_body": "'Plus Jakarta Sans', system-ui, sans-serif",
        "recommended_niches": [
            "бургер", "пицц", "гриль", "барбекю", "стейк", "шашлык", "мясо", "хот-дог", "пивн", "бургерн"
        ],
        "template_file": "bold_diner_grill.html",
        "legacy_template_alias": "warm_artisan_coffee",
    },
    "architectural_brutal_loft": {
        "id": "architectural_brutal_loft",
        "name": "Architectural Brutal Loft",
        "name_ru": "Архитектурный бетон и лофт",
        "description": "Монументальный архитектурный минимализм: текстурный бетон (#EAEAEA), строгие пропорции Space Grotesk, глубокая терракота (#B91C1C) и инженерная сетка.",
        "tags": ["Интерьеры", "Мебель", "Недвижимость", "Архитектура", "Дизайн", "Лофт"],
        "tone": "light",
        "preview_colors": {
            "bg": "#EAEAEA",
            "card": "#FFFFFF",
            "accent": "#B91C1C",
            "text": "#171717",
            "subtext": "#525252",
            "badge_bg": "#DCDCDC",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Space Grotesk', sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "интерьер", "мебел", "дизайн интерьер", "архитектур", "лофт", "фасад", "окна", "кухни на заказ"
        ],
        "template_file": "architectural_brutal_loft.html",
        "legacy_template_alias": "clean_swiss_trust",
    },
    "nordic_hygge_wood": {
        "id": "nordic_hygge_wood",
        "name": "Nordic Hygge Wood",
        "name_ru": "Скандинавский уют и дом",
        "description": "Скандинавская философия хюгге: натуральный лен (#F9F7F4), светлая древесина (#D4A373), чистый шрифт Montserrat, много воздуха и ощущение чистоты.",
        "tags": ["Клининг", "Химчистка", "Апартаменты", "Уютный дом", "Текстиль", "Отели"],
        "tone": "light",
        "preview_colors": {
            "bg": "#F9F7F4",
            "card": "#FFFFFF",
            "accent": "#D4A373",
            "text": "#262320",
            "subtext": "#6E6862",
            "badge_bg": "#EFE9E0",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Montserrat', sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "клининг", "химчистк", "апартамент", "уборк", "стирк", "постель", "посуточно", "отель", "гостиниц"
        ],
        "template_file": "nordic_hygge_wood.html",
        "legacy_template_alias": "clean_swiss_trust",
    },
    "midnight_velvet_lounge": {
        "id": "midnight_velvet_lounge",
        "name": "Midnight Velvet Lounge",
        "name_ru": "Ночной лаунж и кальянные",
        "description": "Бархат ночи: глубокий аметистовый холст (#130D1A), неоновое фиолетовое свечение (#A855F7), дымчатые градиенты и кинематографичная римская антиква Cinzel.",
        "tags": ["Кальянные", "Лаунж-бары", "Клубы", "Караоке", "Коктейль-бары", "Ночной отдых"],
        "tone": "dark",
        "preview_colors": {
            "bg": "#130D1A",
            "card": "#1E142B",
            "accent": "#A855F7",
            "text": "#FAF5FF",
            "subtext": "#C084FC",
            "badge_bg": "#2B1D3D",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Cinzel', serif",
        "font_body": "'Plus Jakarta Sans', system-ui, sans-serif",
        "recommended_niches": [
            "кальян", "лаунж", "lounge", "бар", "клуб", "караоке", "коктейл", "ночн", "hookah"
        ],
        "template_file": "midnight_velvet_lounge.html",
        "legacy_template_alias": "dark_cyber_neon",
    },
    "clean_tech_lab": {
        "id": "clean_tech_lab",
        "name": "Clean Tech Lab",
        "name_ru": "Техно-сервис и гаджеты",
        "description": "Стерильная точность инженеров: светлый технологичный фон (#F4F6F9), моноширинный акцент JetBrains Mono, технический синий (#2563EB) и гарантийные бейджи.",
        "tags": ["Ремонт техники", "Электроника", "Сервисные центры", "Смартфоны", "ПК", "IT-услуги"],
        "tone": "light",
        "preview_colors": {
            "bg": "#F4F6F9",
            "card": "#FFFFFF",
            "accent": "#2563EB",
            "text": "#0F172A",
            "subtext": "#475569",
            "badge_bg": "#E2E8F0",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'JetBrains Mono', monospace",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "ремонт телефон", "ремонт техник", "сервисн", "apple", "ноутбук", "смартфон", "компьютерн", "электроник"
        ],
        "template_file": "clean_tech_lab.html",
        "legacy_template_alias": "clean_swiss_trust",
    },
    "nature_camp_glamping": {
        "id": "nature_camp_glamping",
        "name": "Nature Camp & Glamping",
        "name_ru": "Эко-туризм и глэмпинг",
        "description": "Хвойный лес и тепло костра: глубокий хвойный фон (#1A2E26), янтарный костровой акцент (#D97706), надежный брусковый шрифт Bitter и дух приключений.",
        "tags": ["Глэмпинги", "Базы отдыха", "Туры", "Кемпинг", "Походы", "Эко-отели"],
        "tone": "dark",
        "preview_colors": {
            "bg": "#1A2E26",
            "card": "#243D33",
            "accent": "#D97706",
            "text": "#F4FBF7",
            "subtext": "#96B9AA",
            "badge_bg": "#304E42",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Bitter:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Bitter', serif",
        "font_body": "'Plus Jakarta Sans', system-ui, sans-serif",
        "recommended_niches": [
            "глэмпинг", "база отдых", "тур", "поход", "кемпинг", "экскурси", "шале", "домик в лес", "сплав"
        ],
        "template_file": "nature_camp_glamping.html",
        "legacy_template_alias": "dark_cyber_neon",
    },
    "modern_edtech_campus": {
        "id": "modern_edtech_campus",
        "name": "Modern EdTech Campus",
        "name_ru": "Образование и академия",
        "description": "Академическая структура и энергия прогресса: белоснежное пространство (#FFFFFF), умный ультрамарин (#4F46E5), шрифт Plus Jakarta Sans и лицензии.",
        "tags": ["Автошколы", "Курсы", "Языковые школы", "Репетиторы", "Онлайн-школы", "Коучинг"],
        "tone": "light",
        "preview_colors": {
            "bg": "#FFFFFF",
            "card": "#F8FAFC",
            "accent": "#4F46E5",
            "text": "#0F172A",
            "subtext": "#475569",
            "badge_bg": "#EEF2FF",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Plus Jakarta Sans', sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "recommended_niches": [
            "автошкол", "курс", "языков", "школ", "обучени", "репетитор", "академи", "английск", "подготовк"
        ],
        "template_file": "modern_edtech_campus.html",
        "legacy_template_alias": "clean_swiss_trust",
    },
    "friendly_pet_care": {
        "id": "friendly_pet_care",
        "name": "Friendly Pet Care",
        "name_ru": "Забота о питомцах",
        "description": "Тепло, забота и профессиональный уход: мягкий сливочный фон (#FFF9F2), лечебный бирюзовый акцент (#0D9488), ласковый округлый шрифт Fredoka.",
        "tags": ["Ветклиники", "Груминг", "Зоотовары", "Кинологи", "Передержка", "Ветврачи"],
        "tone": "light",
        "preview_colors": {
            "bg": "#FFF9F2",
            "card": "#FFFFFF",
            "accent": "#0D9488",
            "text": "#1C2D27",
            "subtext": "#506960",
            "badge_bg": "#E6F4F1",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Fredoka', cursive, sans-serif",
        "font_body": "'Plus Jakarta Sans', system-ui, sans-serif",
        "recommended_niches": [
            "ветклиник", "ветеринар", "груминг", "зоо", "питом", "собак", "кошек", "зоомагазин", "кинолог"
        ],
        "template_file": "friendly_pet_care.html",
        "legacy_template_alias": "playful_pastel",
    },
    "obsidian_gold_luxury": {
        "id": "obsidian_gold_luxury",
        "name": "Obsidian & Gold Luxury",
        "name_ru": "Ювелирный ночной шик",
        "description": "Абсолютный обсидиановый эксклюзив: зеркальный черный бархат (#09090B), сияющее королевское золото (#D4AF37), высокая антиква Bodoni Moda и роскошь.",
        "tags": ["Ювелирка", "Премиум-услуги", "VIP", "Часы", "Золото", "Антиквариат"],
        "tone": "dark",
        "preview_colors": {
            "bg": "#09090B",
            "card": "#141418",
            "accent": "#D4AF37",
            "text": "#FAFAFA",
            "subtext": "#A1A1AA",
            "badge_bg": "#27272A",
        },
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,600;0,6..96,700;1,6..96,600&family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Bodoni Moda', serif",
        "font_body": "'Montserrat', system-ui, sans-serif",
        "recommended_niches": [
            "ювелир", "золот", "бриллиант", "vip", "премиум", "часы", "украшени", "ломбард"
        ],
        "template_file": "obsidian_gold_luxury.html",
        "legacy_template_alias": "luxury_editorial",
    },
}

# Alias mapping for backwards compatibility
STYLE_ALIASES = {
    "editorial_light": "luxury_editorial",
    "dark_industrial": "dark_cyber_neon",
    "warm_appetite": "warm_artisan_coffee",
    "clean_trust": "clean_swiss_trust",
    "clean_light": "luxury_editorial",
    "industrial_dark": "industrial_heavy_steel",
    "warm_craft": "warm_artisan_coffee",
    "strict_corporate": "clean_swiss_trust",
    "modern_minimal": "clean_swiss_trust",
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
    """Smart heuristic to recommend the best matching design style from all 20 styles."""
    cat = (category or "").lower()

    # 1. Specialized Nightlife / Hookah / Club
    if any(k in cat for k in ("кальян", "лаунж", "lounge", "караоке", "hookah", "ночн", "коктейл")):
        return "midnight_velvet_lounge"

    # 2. Asian / Sushi / Ramen street food
    if any(k in cat for k in ("суши", "ролл", "рамен", "азиатск", "японск", "вок", "лапш", "том ям", "гёдза")):
        return "tokyo_neo_izakaya"

    # 3. Burgers / Pizza / Grill / BBQ
    if any(k in cat for k in ("бургер", "пицц", "гриль", "барбекю", "стейк", "шашлык", "мясо", "хот-дог", "пивн")):
        return "bold_diner_grill"

    # 4. Barber / Tattoo / Leather craft
    if any(k in cat for k in ("барбер", "барбершоп", "тату", "кожгалантере", "брить")):
        return "vintage_barber_leather"

    # 5. Sports / Fitness / Combat / Gym
    if any(k in cat for k in ("фитнес", "кроссфит", "единоборств", "бокс", "тренажер", "спортзал", "gym", "тренер", "бассейн", "борьб")):
        return "kinetic_sport_volt"

    # 6. Pets & Vet care
    if any(k in cat for k in ("ветклиник", "ветеринар", "груминг", "зоо", "питом", "собак", "кошек", "зоомагазин", "кинолог")):
        return "friendly_pet_care"

    # 7. Jewelry & Luxury / VIP
    if any(k in cat for k in ("ювелир", "золот", "бриллиант", "vip", "часы", "украшени", "ломбард")):
        return "obsidian_gold_luxury"

    # 8. Glamping & Nature tours
    if any(k in cat for k in ("глэмпинг", "база отдых", "тур", "поход", "кемпинг", "экскурси", "шале", "домик в лес", "сплав")):
        return "nature_camp_glamping"

    # 9. Flowers & Organic Botanical
    if any(k in cat for k in ("цветы", "флорист", "букет", "эко-лав", "органик", "йог", "сад", "растени", "веган", "трав")):
        return "organic_botanical_sage"

    # 10. Education / Courses / Driving school
    if any(k in cat for k in ("автошкол", "курс", "языков", "школ", "обучени", "репетитор", "академи", "английск", "подготовк")):
        return "modern_edtech_campus"

    # 11. Gadget & Tech repair
    if any(k in cat for k in ("ремонт телефон", "ремонт техник", "apple", "ноутбук", "смартфон", "компьютерн", "электроник")):
        return "clean_tech_lab"

    # 12. Auto, Detailing & Cyber
    if any(k in cat for k in ("авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто", "кибер", "gadget", "it-")):
        return "dark_cyber_neon"

    # 13. Heavy Steel & Construction
    if any(k in cat for k in ("стройк", "строитель", "спецтехник", "металл", "бетон", "производств", "кран", "экскаватор", "кровл", "жби", "строймонтаж")):
        return "industrial_heavy_steel"

    # 14. Architecture & Loft Furniture
    if any(k in cat for k in ("интерьер", "мебел", "дизайн интерьер", "архитектур", "лофт", "фасад", "окна", "кухни на заказ")):
        return "architectural_brutal_loft"

    # 15. Cleaning & Nordic Hygge
    if any(k in cat for k in ("клининг", "химчистк", "апартамент", "уборк", "стирк", "постель", "посуточно", "отель", "гостиниц")):
        return "nordic_hygge_wood"

    # 16. Sweet pastel (bubble tea, desserts, kids)
    if any(k in cat for k in ("бабл", "bubble", "мороженое", "торт", "десерт", "сладост", "дети", "детск", "подарк", "шары", "праздник")):
        return "playful_pastel"

    # 17. Creative & Digital Neo-brutalism
    if any(k in cat for k in ("digital", "диджитал", "агентств", "стритвер", "streetwear", "мерч", "продакшн", "креатив")):
        return "acid_neo_brutalism"

    # 18. Beauty & Fashion Editorial
    if any(k in cat for k in ("бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "одежд", "спа", "ногти", "брови", "массаж", "мода")):
        return "luxury_editorial"

    # 19. Coffee & Bakery Craft
    if any(k in cat for k in ("кофе", "пекарн", "кондитер", "выпечк", "ресторан", "кафе", "доставка еды", "кухн", "чай")):
        return "warm_artisan_coffee"

    # 20. Default to clean swiss trust for corporate, legal, medical, and general businesses
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
