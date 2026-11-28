from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import re
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.services.ai_router import ask_ai

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "demos"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def format_tel_href(phone: str | None) -> str:
    """Strictly formats any phone number into tel:+79991234567, never about:invalid."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return ""
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return f"tel:+{digits}"


MURASAKI_BADGE_SNIPPET = """
<!-- Concept preview bar -->
<div class="fixed bottom-3 inset-x-3 z-50 mx-auto max-w-md pointer-events-none">
  <div class="pointer-events-auto flex items-center justify-between gap-2 rounded-lg border border-black/10 bg-white/95 px-3 py-1.5 shadow-md backdrop-blur-sm">
    <p class="truncate text-[11px] font-medium text-slate-600">
      Макет для {business_name}
    </p>
    <a href="https://t.me/Murasaki_website" target="_blank" rel="noopener" class="shrink-0 rounded-md bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white transition hover:bg-slate-800">
      Обсудить запуск
    </a>
  </div>
</div>
"""


def inject_murasaki_badge(html_text: str, business_name: str = "") -> str:
    """Ensures the Murasaki LeadRadar demo badge is injected into HTML before </body>."""
    if not html_text:
        return html_text
    if "Murasaki_website" in html_text:
        return html_text
    badge = MURASAKI_BADGE_SNIPPET.replace("{business_name}", html.escape(business_name or "бизнеса"))
    body_idx = html_text.lower().rfind("</body>")
    if body_idx != -1:
        return html_text[:body_idx] + badge + "\n" + html_text[body_idx:]
    return html_text + "\n" + badge

CITY_PREPOSITIONAL = {
    "Москва": "Москве",
    "Санкт-Петербург": "Санкт-Петербурге",
    "Новосибирск": "Новосибирске",
    "Екатеринбург": "Екатеринбурге",
    "Казань": "Казани",
    "Нижний Новгород": "Нижнем Новгороде",
    "Челябинск": "Челябинске",
    "Красноярск": "Красноярске",
    "Самара": "Самаре",
    "Уфа": "Уфе",
    "Ростов-на-Дону": "Ростове-на-Дону",
    "Краснодар": "Краснодаре",
    "Омск": "Омске",
    "Воронеж": "Воронеже",
    "Пермь": "Перми",
    "Волгоград": "Волгограде",
    "Саратов": "Саратове",
    "Тюмень": "Тюмени",
    "Тольятти": "Тольятти",
    "Барнаул": "Барнауле",
    "Ижевск": "Ижевске",
    "Махачкала": "Махачкале",
    "Хабаровск": "Хабаровске",
    "Ульяновск": "Ульяновске",
    "Иркутск": "Иркутске",
    "Владивосток": "Владивостоке",
    "Ярославль": "Ярославле",
    "Кемерово": "Кемерове",
    "Томск": "Томске",
    "Набережные Челны": "Набережных Челнах",
    "Севастополь": "Севастополе",
    "Ставрополь": "Ставрополе",
    "Оренбург": "Оренбурге",
    "Новокузнецк": "Новокузнецке",
    "Рязань": "Рязани",
    "Балашиха": "Балашихе",
    "Пенза": "Пензе",
    "Чебоксары": "Чебоксарах",
    "Липецк": "Липецке",
    "Калининград": "Калининграде",
    "Астрахань": "Астрахани",
    "Тула": "Туле",
    "Киров": "Кирове",
    "Сочи": "Сочи",
    "Курск": "Курске",
    "Улан-Удэ": "Улан-Удэ",
    "Сургут": "Сургуте",
    "Тверь": "Твери",
    "Магнитогорск": "Магнитогорске",
    "Иваново": "Иваново",
    "Брянск": "Брянске",
    "Белгород": "Белгороде",
    "Владимир": "Владимире",
    "Чита": "Чите",
    "Архангельск": "Архангельске",
    "Калуга": "Калуге",
    "Смоленск": "Смоленске",
    "Саранск": "Саранске",
    "Череповец": "Череповце",
    "Курган": "Кургане",
    "Вологда": "Вологде",
    "Орёл": "Орле",
    "Владикавказ": "Владикавказе",
    "Подольск": "Подольске",
    "Грозный": "Грозном",
    "Мурманск": "Мурманске",
    "Тамбов": "Тамбове",
    "Петрозаводск": "Петрозаводске",
    "Стерлитамак": "Стерлитамаке",
    "Кострома": "Костроме",
    "Нижневартовск": "Нижневартовске",
    "Новороссийск": "Новороссийске",
    "Йошкар-Ола": "Йошкар-Оле",
    "Таганрог": "Таганроге",
    "Сыктывкар": "Сыктывкаре",
    "Нальчик": "Нальчике",
    "Шахты": "Шахтах",
    "Дзержинск": "Дзержинске",
    "Благовещенск": "Благовещенске",
    "Великий Новгород": "Великом Новгороде",
    "Псков": "Пскове",
    "Симферополь": "Симферополе",
    "Якутск": "Якутске",
}

BUSINESS_NOUNS = {
    "Бьюти": "студия красоты",
    "Рестораны": "ресторан",
    "Автосервисы": "автосервис",
    "Медицина": "клиника",
    "Фитнес": "фитнес-клуб",
    "Отели": "отель",
    "Услуги": "компания",
    "Магазины": "магазин",
    "Юристы": "юридическая компания",
}

BUSINESS_PLURAL_GENITIVE = {
    "Бьюти": "салонов красоты и студий",
    "Рестораны": "ресторанов и кафе",
    "Автосервисы": "автосервисов и СТО",
    "Медицина": "клиник и медцентров",
    "Фитнес": "фитнес-клубов и студий",
    "Отели": "отелей и гостиниц",
    "Услуги": "компаний сферы услуг",
    "Магазины": "магазинов",
    "Юристы": "юридических и консалтинговых компаний",
}

# ── High-Quality Niche Fallback Images (Unsplash curated) ─────────────────────
NICHE_FALLBACK_IMAGES: dict[str, dict[str, Any]] = {
    "Бьюти": {
        "hero": "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1607779097040-26e80aa78e66?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Автосервисы": {
        "hero": "https://images.unsplash.com/photo-1486006920555-c77dce18193b?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1517524008697-84bbe3c3fd98?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1625047509168-a7026f36de04?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Рестораны": {
        "hero": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Медицина": {
        "hero": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1666214280557-f1b5022eb634?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Юристы": {
        "hero": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1450133064473-71024230f91b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Фитнес": {
        "hero": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=800&q=80",
        ],
    },
    "Default": {
        "hero": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=800&q=80",
        ],
    },
}

# ── 5 Design Themes with Distinct Fonts, Colors & Aesthetics ───────────────────
THEMES: dict[str, dict[str, Any]] = {
    # 1. Clean Light (Beauty, Medicine, Dentistry, Salons)
    "clean_light": {
        "name": "Clean Light",
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,600;0,700;1,600&display=swap" rel="stylesheet">',
        "font_heading": "'Playfair Display', 'Cormorant Garamond', Georgia, serif",
        "font_body": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "bg_page": "#FAF8F5",
        "bg_container": "#FAF8F5",
        "bg_card": "#FFFFFF",
        "border_color": "#EFEAE1",
        "text_primary": "#1C1917",
        "text_secondary": "#57534E",
        "text_muted": "#A8A29E",
        "accent": "#2E5A44",  # Sage green
        "accent_text": "#FFFFFF",
        "accent_hover": "#244735",
        "accent_soft": "#EBF3EE",
        "accent_border": "#D5E5DC",
        "badge_border": "border-[#E8E2D6]",
        "badge_bg": "bg-[#F3EFE8]",
        "radius": "rounded-2xl",
        "radius_inner": "rounded-xl",
        "shadow": "shadow-[0_4px_20px_rgba(46,90,68,0.06)]",
        "is_dark": False,
    },
    # 2. Industrial Dark (Auto Services, Detailing, Construction, Repair)
    "industrial_dark": {
        "name": "Industrial Dark",
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">',
        "font_heading": "'Montserrat', sans-serif",
        "font_body": "'Montserrat', -apple-system, BlinkMacSystemFont, sans-serif",
        "bg_page": "#121417",
        "bg_container": "#121417",
        "bg_card": "#1B1E23",
        "border_color": "#282C34",
        "text_primary": "#FFFFFF",
        "text_secondary": "#9CA3AF",
        "text_muted": "#6B7280",
        "accent": "#FF6B00",  # High-contrast orange
        "accent_text": "#000000",
        "accent_hover": "#E55F00",
        "accent_soft": "rgba(255, 107, 0, 0.12)",
        "accent_border": "rgba(255, 107, 0, 0.35)",
        "badge_border": "border-[#282C34]",
        "badge_bg": "bg-[#1E2228]",
        "radius": "rounded-xl",
        "radius_inner": "rounded-lg",
        "shadow": "shadow-[0_4px_24px_rgba(0,0,0,0.5)]",
        "is_dark": True,
    },
    # 3. Warm Craft (Cafes, Bakeries, Coffee, Food Delivery, Restaurants)
    "warm_craft": {
        "name": "Warm Craft",
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">',
        "font_heading": "'Lora', Georgia, serif",
        "font_body": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif",
        "bg_page": "#F9F6F0",
        "bg_container": "#F9F6F0",
        "bg_card": "#FFFFFF",
        "border_color": "#EADBCE",
        "text_primary": "#281D17",
        "text_secondary": "#63534B",
        "text_muted": "#9C8A81",
        "accent": "#C85A32",  # Warm terracotta
        "accent_text": "#FFFFFF",
        "accent_hover": "#B34E29",
        "accent_soft": "#FAEEE9",
        "accent_border": "#F0D5C9",
        "badge_border": "border-[#EADBCE]",
        "badge_bg": "bg-[#F2ECE4]",
        "radius": "rounded-2xl",
        "radius_inner": "rounded-xl",
        "shadow": "shadow-[0_6px_22px_rgba(200,90,50,0.07)]",
        "is_dark": False,
    },
    # 4. Strict Corporate (Legal, Finance, B2B, Electronics Repair)
    "strict_corporate": {
        "name": "Strict Corporate",
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">',
        "font_heading": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "font_body": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "bg_page": "#FFFFFF",
        "bg_container": "#FFFFFF",
        "bg_card": "#F8FAFC",
        "border_color": "#E2E8F0",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "text_muted": "#94A3B8",
        "accent": "#1E3A8A",  # Deep navy corporate
        "accent_text": "#FFFFFF",
        "accent_hover": "#172554",
        "accent_soft": "#EFF6FF",
        "accent_border": "#BFDBFE",
        "badge_border": "border-slate-200",
        "badge_bg": "bg-slate-100",
        "radius": "rounded-lg",
        "radius_inner": "rounded-md",
        "shadow": "shadow-sm border border-slate-200",
        "is_dark": False,
    },
    # 5. Modern Minimal (Universal for other niches, Fitness, Shops, Services)
    "modern_minimal": {
        "name": "Modern Minimal",
        "font_css": '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">',
        "font_heading": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif",
        "font_body": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif",
        "bg_page": "#0F172A",
        "bg_container": "#0F172A",
        "bg_card": "#1E293B",
        "border_color": "#334155",
        "text_primary": "#F8FAFC",
        "text_secondary": "#94A3B8",
        "text_muted": "#64748B",
        "accent": "#6366F1",  # Vibrant indigo
        "accent_text": "#FFFFFF",
        "accent_hover": "#4F46E5",
        "accent_soft": "rgba(99, 102, 241, 0.15)",
        "accent_border": "rgba(99, 102, 241, 0.35)",
        "badge_border": "border-[#334155]",
        "badge_bg": "bg-[#1E293B]",
        "radius": "rounded-2xl",
        "radius_inner": "rounded-xl",
        "shadow": "shadow-[0_8px_30px_rgba(0,0,0,0.35)]",
        "is_dark": True,
    },
}


def detect_theme(category: str | None) -> str:
    """Select the best fitting theme based on business category."""
    cat = (category or "").lower()
    # 1. Warm Craft (Food, Cafes, Restaurants)
    if any(k in cat for k in ("ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "пицц", "суши", "бар", "кухн", "кондитер")):
        return "warm_craft"
    # 2. Clean Light (Beauty, Medicine, Dentistry, Clinics)
    if any(k in cat for k in ("бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "медицин", "клиник", "стоматолог", "доктор", "врач", "спа", "массаж")):
        return "clean_light"
    # 3. Industrial Dark (Auto Services, Detailing, Construction, Repair)
    if any(k in cat for k in ("авто", "сервис", "шиномонтаж", "детейлинг", "ремонт авто", "кузов", "мойка", "стройк", "строитель", "монтаж")) or re.search(r"\bсто\b", cat):
        return "industrial_dark"
    # 4. Strict Corporate (Legal, Finance, B2B, Electronics Repair)
    if any(k in cat for k in ("юрист", "юрид", "адвокат", "нотариус", "финанс", "бухгалтер", "аудит", "b2b", "недвижим", "консалтинг", "техник", "электроник")):
        return "strict_corporate"
    # 5. Modern Minimal (Universal for other niches)
    return "modern_minimal"


PROFILES: dict[str, dict] = {
    "Бьюти": {
        "tagline": "Красота и гармония, к которой хочется возвращаться",
        "subtitle": "Онлайн-запись за 30 секунд — без звонков и ожидания подтверждения",
        "services": [
            ("Маникюр + гель-лак", "от 2 500 ₽", "Стойкое покрытие до 4 недель, дизайн в подарок"),
            ("Педикюр Smart", "от 3 200 ₽", "Аппаратная обработка, уход и покрытие"),
            ("Брови и ресницы", "от 1 900 ₽", "Коррекция формы, окрашивание хной, ламинирование"),
            ("Стрижка и авторская укладка", "от 2 800 ₽", "Индивидуальный подбор под форму лица и образ"),
        ],
        "benefits": [
            ("Запись 24/7", "Выберите удобное время онлайн за пару кликов"),
            ("Опытные мастера", "Средний стаж специалистов команды — более 5 лет"),
            ("Стерильность 100%", "Медицинская трёхэтапная стерилизация инструментов"),
            ("Уютная атмосфера", "Кофе, приятная музыка и заботливый сервис"),
        ],
        "reviews": [
            ("Анна Ковалёва", "Делала маникюр — покрытие держится идеально уже месяц! Записалась прямо с телефона за минуту."),
            ("Мария Соколова", "Лучшие мастера в городе. Внимательно выслушали пожелания, результат превзошёл ожидания."),
            ("Екатерина Васильева", "Очень уютно, чисто и бережное отношение. Теперь хожу только сюда."),
        ],
    },
    "Рестораны": {
        "tagline": "Вкус и атмосфера, которые хочется повторить",
        "subtitle": "Забронируйте столик онлайн — без звонков и долгих ожиданий ответа",
        "services": [
            ("Бизнес-ланч от шефа", "590 ₽", "Салат, суп, горячее блюдо и напиток каждый будний день"),
            ("Завтраки весь день", "от 450 ₽", "Сырники, свежие круассаны, омлеты и кофе свежей обжарки"),
            ("Паста и блюда на огне", "от 690 ₽", "Готовим из фермерских продуктов на открытой кухне"),
            ("Десерты ручной работы", "от 390 ₽", "Собственная кондитерская и сезонные авторские новинки"),
        ],
        "benefits": [
            ("Мгновенная бронь", "Выберите дату и время — столик будет ждать к вашему визиту"),
            ("Свежие продукты", "Поставки от локальных поставщиков каждое утро"),
            ("Уютный интерьер", "Идеально для свиданий, семейных ужинов и деловых встреч"),
            ("Быстрая подача", "Среднее время подачи горячих блюд — 12-15 минут"),
        ],
        "reviews": [
            ("Дмитрий Попов", "Бизнес-ланчи превосходные: большие порции, всё горячее и свежее. Персонал на высоте."),
            ("Ольга Романова", "Отмечали день рождения. Помогли с рассадкой и тортом, гости остались в восторге!"),
            ("Иван Тарасов", "Лучшая кухня в районе. Теперь бронирую столик заранее онлайн."),
        ],
    },
    "Автосервисы": {
        "tagline": "Качественный ремонт и обслуживание без скрытых доплат",
        "subtitle": "Запишитесь на осмотр онлайн — согласуем точную смету до начала работ",
        "services": [
            ("Компьютерная диагностика", "от 1 500 ₽", "Полное сканирование электронных систем и датчиков"),
            ("Техническое обслуживание", "от 2 900 ₽", "Замена моторного масла и фильтров по регламенту"),
            ("Шиномонтаж и балансировка", "от 2 400 ₽", "Точный баланс, протяжка динамометром, мойка колес"),
            ("Ремонт ходовой части", "по смете", "Восстановление подвески, тормозов и рулевого управления"),
        ],
        "benefits": [
            ("Гарантия качества", "До 12 месяцев на все выполненные работы и установленные узлы"),
            ("Честная смета", "Никаких неожиданных сумм: все позиции согласуются с вами"),
            ("Запчасти в наличии", "Оригинальные детали и сертифицированные аналоги с гарантией"),
            ("Работаем без выходных", "Принимаем автомобили с 8:00 до 21:00 ежедневно"),
        ],
        "reviews": [
            ("Сергей Мельников", "Провели диагностику за 40 минут, сразу назвали итоговую сумму. Сделали строго в срок."),
            ("Алексей Кузнецов", "Записался онлайн, приехал точно ко времени — бокс был свободен. Отличный сервис!"),
            ("Роман Дронов", "Обслуживаю здесь уже вторую машину. Честные ребята, лишнего не навязывают."),
        ],
    },
    "Медицина": {
        "tagline": "Профессиональная забота о здоровье без очередей",
        "subtitle": "Запишитесь на прием к специалисту онлайн — свободное время видно сразу",
        "services": [
            ("Первичная консультация", "от 2 500 ₽", "Осмотр врача, сбор анамнеза и составление плана лечения"),
            ("Профессиональная гигиена", "от 4 500 ₽", "Ультразвук, Air-Flow и реминерализирующая терапия"),
            ("Лечение кариеса", "от 5 900 ₽", "Современные световые пломбы с гарантией без боли"),
            ("Диагностика и анализы", "от 800 ₽", "Собственная лаборатория, результаты в день сдачи"),
        ],
        "benefits": [
            ("Квалификация", "Все специалисты имеют высшую категорию и стаж от 8 лет"),
            ("Без очередей", "Прием строго по записи, напоминание в мессенджер накануне"),
            ("Современное оборудование", "Европейские стандарты стерилизации и диагностики"),
            ("Комфорт и забота", "Внимательное отношение к каждому пациенту и деликатный подход"),
        ],
        "reviews": [
            ("Наталья Ильина", "Всегда переживала перед приемом, но здесь всё прошло максимально бережно и спокойно."),
            ("Павел Григорьев", "Записался через сайт за минуту, приняли ровно по расписанию. Лечением доволен."),
            ("Юлия Афанасьева", "Современная светлая клиника, чуткие доктора. Рекомендую всей семье."),
        ],
    },
    "Юристы": {
        "tagline": "Надежная правовая защита ваших интересов и бизнеса",
        "subtitle": "Оставьте заявку онлайн — разберем вашу ситуацию на первичной консультации",
        "services": [
            ("Юридическая консультация", "от 3 000 ₽", "Анализ документов, оценка перспектив и рисков"),
            ("Составление договоров", "от 5 000 ₽", "Разработка индивидуальных соглашений под ваши условия"),
            ("Представительство в суде", "по договору", "Полное ведение дела в арбитражных судах и судах общей юрисдикции"),
            ("Сопровождение сделок", "от 15 000 ₽", "Проверка контрагентов, чистоты объектов и налоговых последствий"),
        ],
        "benefits": [
            ("Опыт и практика", "Более 10 лет успешной защиты прав клиентов и компаний"),
            ("Прозрачный договор", "Фиксированные условия оплаты без скрытых процентов"),
            ("Конфиденциальность", "Строгое соблюдение профессиональной тайны"),
            ("Оперативность", "Приступаем к работе сразу после согласования задачи"),
        ],
        "reviews": [
            ("Артем Воронов", "Помогли решить сложный арбитражный спор в нашу пользу. Профессионалы высшего класса."),
            ("Елена Морозова", "Оформили сделку по недвижимости безупречно, выявили скрытые риски договора."),
            ("Виктор Семенов", "Регулярно обращаюсь по корпоративным вопросам. Всегда четко, быстро и по делу."),
        ],
    },
    "Фитнес": {
        "tagline": "Энергия, сила и комфорт для вашего тела каждый день",
        "subtitle": "Запишитесь на первое пробное занятие онлайн — тренер подберет программу",
        "services": [
            ("Пробная тренировка", "бесплатно", "Знакомство с клубом, фитнес-тестирование и инструктаж"),
            ("Персональный тренинг", "от 2 200 ₽", "Индивидуальный план упражнений и питания под ваши цели"),
            ("Групповые программы", "от 850 ₽", "Йога, пилатес, сайкл, функциональный тренинг и растяжка"),
            ("Клубная карта на месяц", "от 4 500 ₽", "Безлимитный доступ в тренажерный зал и SPA-зону"),
        ],
        "benefits": [
            ("Сертифицированные тренеры", "Опытные наставники с профильным спортивным образованием"),
            ("Современный зал", "Профессиональные тренажеры премиум-класса и зоны свободных весов"),
            ("Удобный график", "Открыты ежедневно с 7:00 до 23:00 без перерывов"),
            ("Комфорт", "Просторные раздевалки, финская сауна и чистые полотенца"),
        ],
        "reviews": [
            ("Ксения Лебедева", "Хожу на растяжку и йогу. Просторные залы, отличный свет и вдохновляющие тренеры!"),
            ("Максим Шевченко", "За полгода сбросил 10 кг под руководством тренера. Очень мотивирующая атмосфера."),
            ("Дарья Новикова", "Удобно записываться на тренировки со смартфона, напоминания приходят вовремя."),
        ],
    },
}

DEFAULT_PROFILE = {
    "tagline": "Современный сервис и надежные решения для вас",
    "subtitle": "Оставьте заявку онлайн — свяжемся с вами в течение 10 минут",
    "services": [
        ("Консультация специалиста", "бесплатно", "Ответим на вопросы, проанализируем задачу и подберем решение"),
        ("Базовый комплекс услуг", "по запросу", "Качественное выполнение с соблюдением стандартов"),
        ("Индивидуальный заказ", "рассчитывается", "Персональный подход под ваши требования и бюджет"),
        ("Срочное выполнение", "+25% к смете", "Оперативное решение задачи в течение 24 часов"),
    ],
    "benefits": [
        ("Онлайн-заявка 24/7", "Удобно написать в мессенджер без звонков и ожидания"),
        ("Прозрачные цены", "Согласуем точную стоимость до начала выполнения"),
        ("Гарантия результата", "Отвечаем за качество каждого этапа работы"),
        ("Поддержка клиентов", "Остаемся на связи и оперативно консультируем"),
    ],
    "reviews": [
        ("Алексей Петров", "Быстро ответили на сообщение, подробно проконсультировали и сделали всё в срок. Рекомендую!"),
        ("Марина Смирнова", "Приятно иметь дело с профессионалами. Очень удобная онлайн-запись без лишних звонков."),
        ("Игорь Васильев", "Отличный сервис, вежливые специалисты и честные понятные цены."),
    ],
}


def _safe(value: str | None, fallback: str = "") -> str:
    return html.escape((value or fallback).strip())


def _city_in(city: str | None) -> str:
    city = (city or "").strip()
    if not city:
        return "в вашем городе"
    if city in CITY_PREPOSITIONAL:
        return f"в {CITY_PREPOSITIONAL[city]}"
    clean_lower = city.lower()
    for name, prep in CITY_PREPOSITIONAL.items():
        if name.lower() == clean_lower:
            return f"в {prep}"
    return f"в городе {city}"


def _business_noun(category: str | None) -> str:
    return BUSINESS_NOUNS.get(category or "", "компания")


def _stars(rating: float | None) -> str:
    value = rating or 4.9
    filled = max(1, min(5, round(value)))
    return "★" * filled + "☆" * (5 - filled)


def _phone_digits(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def _primary_href(lead: dict) -> tuple[str, str, str]:
    socials = lead.get("social_links") or {}
    phone = _phone_digits(lead.get("phone"))
    if socials.get("whatsapp"):
        return socials["whatsapp"], "Записаться в WhatsApp", "Записаться"
    if phone:
        return f"https://wa.me/{phone}", "Записаться в WhatsApp", "Записаться"
    if socials.get("telegram"):
        return socials["telegram"], "Написать в Telegram", "Написать"
    return f"tel:{phone}" if phone else "#contacts", "Связаться с нами", "Связаться"


def _get_curated_photos(lead: dict, category: str) -> tuple[str, list[str]]:
    """Returns (hero_photo, gallery_photos) combining real lead photos with same-origin sub-niche stock."""
    from app.services.media_collector import get_niche_fallback

    fallbacks = get_niche_fallback(
        category,
        business_name=lead.get("name"),
        services=lead.get("services"),
    )

    raw_lead_photos = [
        p for p in (lead.get("photos") or [])
        if isinstance(p, str) and p.startswith("http") and "images.unsplash.com" not in p
    ]

    if raw_lead_photos:
        hero = raw_lead_photos[0]
        remaining = raw_lead_photos[1:]
    else:
        hero = fallbacks["hero"]
        remaining = []

    gallery: list[str] = []
    for p in remaining:
        if p not in gallery and p != hero:
            gallery.append(p)
        if len(gallery) >= 4:
            break

    for fb in fallbacks["gallery"]:
        if len(gallery) >= 4:
            break
        if fb not in gallery and fb != hero:
            gallery.append(fb)

    return hero, gallery


def build_fallback_landing(lead: dict) -> str:
    """Builds a rich, responsive, niche-adapted landing page with multiple hero layouts."""
    from app.services.media_collector import get_niche_fallback

    category = lead.get("category") or "Бизнес"
    theme_key = detect_theme(category)
    theme = THEMES[theme_key]
    profile = PROFILES.get(category, DEFAULT_PROFILE)

    business_name = _safe(lead.get("name"), "Ваш бизнес")
    city = _safe(lead.get("city"), "вашем городе")
    city_in = _safe(_city_in(lead.get("city")))
    rating = f"{lead.get('rating'):.1f}" if lead.get("rating") else "4.9"
    reviews_count = lead.get("reviews_count") or 128
    address = _safe(lead.get("address"), "Адрес уточняется")
    hours = "<br>".join(_safe(item) for item in (lead.get("opening_hours") or [])) or "Ежедневно 10:00–21:00"
    map_url = f"https://yandex.ru/maps/?text={quote(lead.get('name', '') + ' ' + (lead.get('address') or ''))}"

    hero_img, gallery_imgs = _get_curated_photos(lead, category)
    niche_fallback = get_niche_fallback(category, business_name=lead.get("name"))
    hero_fallback = niche_fallback["hero"]

    primary_href, primary_label, sticky_label = _primary_href(lead)
    socials = lead.get("social_links") or {}
    phone = lead.get("phone")
    phone_digits = _phone_digits(phone)

    # Secondary action buttons
    secondary: list[str] = []
    if socials.get("telegram"):
        secondary.append(
            f'<a href="{html.escape(socials["telegram"])}" target="_blank" rel="noopener" '
            f'class="inline-flex h-11 items-center justify-center gap-2 {theme["radius_inner"]} border {theme["badge_border"]} {theme["badge_bg"]} text-xs font-semibold transition hover:opacity-80" '
            f'style="color: {theme["text_primary"]};">'
            f'<svg class="w-4 h-4 fill-current text-[#229ED9]" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.56 8.16l-1.97 9.28c-.15.65-.53.81-1.08.5l-3-2.21-1.45 1.4c-.16.16-.3.3-.61.3l.21-3.05 5.56-5.02c.24-.22-.05-.34-.38-.13l-6.87 4.33-2.96-.92c-.64-.2-.66-.64.13-.95l11.57-4.46c.54-.19 1.01.14.88.93z"/></svg>'
            f'Telegram</a>'
        )
    if phone:
        secondary.append(
            f'<a href="tel:{html.escape(phone_digits)}" '
            f'class="inline-flex h-11 items-center justify-center gap-2 {theme["radius_inner"]} border {theme["badge_border"]} {theme["badge_bg"]} text-xs font-semibold transition hover:opacity-80" '
            f'style="color: {theme["text_primary"]};">'
            f'<span>📞</span> Позвонить</a>'
        )
    if not secondary:
        secondary.append(
            f'<a href="#contacts" class="inline-flex h-11 items-center justify-center {theme["radius_inner"]} border {theme["badge_border"]} {theme["badge_bg"]} text-xs font-semibold transition hover:opacity-80" '
            f'style="color: {theme["text_primary"]};">Контакты и адрес</a>'
        )

    sec_class = "grid gap-2" if len(secondary) == 1 else "grid grid-cols-2 gap-2"
    secondary_ctas_html = "".join(secondary)

    # Primary CTA button
    primary_btn_html = (
        f'<a href="{html.escape(primary_href)}" target="_blank" rel="noopener" '
        f'class="inline-flex h-12 w-full items-center justify-center {theme["radius_inner"]} text-sm font-bold transition transform hover:scale-[1.01] active:scale-[0.99]" '
        f'style="background-color: {theme["accent"]}; color: {theme["accent_text"]}; box-shadow: 0 4px 14px {theme["accent"]}40;">'
        f'{_safe(primary_label)}</a>'
    )

    # ── Layout Variation (3 Distinct Hero Styles based on business ID/name hash) ──
    seed_str = str(lead.get("id") or business_name)
    variant_idx = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16) % 3

    logo_url = lead.get("logo_url")
    logo_img_html = ""
    if logo_url and str(logo_url).startswith("http"):
        logo_img_html = (
            f'<img src="{html.escape(logo_url)}" alt="{business_name}" '
            f'class="h-12 w-12 rounded-full object-cover border-2 shadow-sm" '
            f'style="border-color: {theme["accent"]};" '
            f'onerror="this.style.display=\'none\';">'
        )

    if variant_idx == 0:
        # Variant A: Split Card Hero with Photo Card and Rating Badge
        hero_html = f"""
        <section class="px-5 pt-7 pb-6">
          <div class="flex items-center justify-between gap-3">
            <span class="inline-flex items-center gap-1.5 {theme['radius_inner']} px-3 py-1 text-xs font-semibold border {theme['badge_border']} {theme['badge_bg']}" style="color: {theme['text_secondary']};">
              <span class="h-2 w-2 rounded-full" style="background-color: {theme['accent']};"></span>
              {_safe(category)} · {city}
            </span>
            {logo_img_html}
          </div>

          <h1 class="mt-4 text-3xl font-extrabold tracking-tight [text-wrap:balance]" style="font-family: {theme['font_heading']}; color: {theme['text_primary']};">
            {business_name}
          </h1>
          <p class="mt-2 text-base font-medium [text-wrap:balance]" style="color: {theme['text_primary']};">
            {_safe(profile['tagline'])}
          </p>
          <p class="mt-1.5 text-xs leading-relaxed" style="color: {theme['text_secondary']};">
            {_safe(profile['subtitle'])}
          </p>

          <!-- Photo Card with overlay rating -->
          <div class="relative mt-5 overflow-hidden {theme['radius']} {theme['shadow']} border {theme['border_color']}">
            <img src="{html.escape(hero_img)}" alt="{business_name}" class="h-52 w-full object-cover" onerror="this.onerror=null; this.src='{hero_fallback}';">
            <div class="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full bg-black/75 px-3 py-1 text-xs font-semibold text-white backdrop-blur-md">
              <span class="text-amber-400">★</span>
              <span>{rating}</span>
              <span class="text-white/60">({reviews_count} отзывов)</span>
            </div>
          </div>

          <div class="mt-5 space-y-2.5">
            {primary_btn_html}
            <div class="{sec_class}">
              {secondary_ctas_html}
            </div>
            <p class="pt-1 text-center text-[11px]" style="color: {theme['text_muted']};">
              ⚡ Ответим в течение 5 минут • Без звонков и ожидания
            </p>
          </div>
        </section>
        """
    elif variant_idx == 1:
        # Variant B: Full-width Immersive Banner Hero
        overlay_gradient = f"linear-gradient(to bottom, rgba(0,0,0,0.2) 0%, {theme['bg_page']} 100%)"
        hero_html = f"""
        <section class="relative">
          <div class="relative h-64 w-full overflow-hidden">
            <img src="{html.escape(hero_img)}" alt="{business_name}" class="h-full w-full object-cover" onerror="this.onerror=null; this.src='{hero_fallback}';">
            <div class="absolute inset-0" style="background: {overlay_gradient};"></div>
            <div class="absolute top-4 left-4 right-4 flex items-center justify-between">
              <span class="inline-flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1 text-xs font-semibold text-white backdrop-blur-md">
                <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                {_safe(category)} · {city}
              </span>
              {logo_img_html}
            </div>
          </div>

          <div class="relative -mt-16 px-5 pb-6">
            <div class="{theme['radius']} p-5 {theme['shadow']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
              <div class="flex items-center gap-2 text-xs font-semibold" style="color: {theme['text_secondary']};">
                <span class="text-amber-400">★ {rating}</span>
                <span>•</span>
                <span>{reviews_count} проверенных отзывов на картах</span>
              </div>
              <h1 class="mt-2 text-2xl font-bold tracking-tight [text-wrap:balance]" style="font-family: {theme['font_heading']}; color: {theme['text_primary']};">
                {business_name}
              </h1>
              <p class="mt-1.5 text-sm font-medium" style="color: {theme['text_primary']};">
                {_safe(profile['tagline'])}
              </p>
              <p class="mt-1 text-xs leading-relaxed" style="color: {theme['text_secondary']};">
                {_safe(profile['subtitle'])}
              </p>

              <div class="mt-5 space-y-2.5">
                {primary_btn_html}
                <div class="{sec_class}">
                  {secondary_ctas_html}
                </div>
              </div>
            </div>
          </div>
        </section>
        """
    else:
        # Variant C: Centered Brand Hero with Logo & Quick Highlights
        hero_html = f"""
        <section class="px-5 pt-8 pb-6 text-center">
          <div class="inline-flex items-center gap-1.5 {theme['radius_inner']} px-3 py-1 text-xs font-semibold border {theme['badge_border']} {theme['badge_bg']}" style="color: {theme['text_secondary']};">
            <span class="h-2 w-2 rounded-full" style="background-color: {theme['accent']};"></span>
            {_safe(category)} · {city}
          </div>

          <div class="mt-4 flex justify-center">
            <div class="relative">
              <img src="{html.escape(logo_url or hero_img)}" alt="{business_name}" class="h-20 w-20 rounded-2xl object-cover shadow-md border-2" style="border-color: {theme['accent']};" onerror="this.onerror=null; this.src='{hero_fallback}';">
              <span class="absolute -bottom-2 -right-2 rounded-full bg-amber-400 px-2 py-0.5 text-[10px] font-bold text-black shadow">★ {rating}</span>
            </div>
          </div>

          <h1 class="mt-4 text-3xl font-extrabold tracking-tight [text-wrap:balance]" style="font-family: {theme['font_heading']}; color: {theme['text_primary']};">
            {business_name}
          </h1>
          <p class="mt-2 text-sm font-semibold" style="color: {theme['text_primary']};">
            {_safe(profile['tagline'])}
          </p>
          <p class="mt-1 text-xs max-w-sm mx-auto" style="color: {theme['text_secondary']};">
            {_safe(profile['subtitle'])}
          </p>

          <div class="relative mt-4 overflow-hidden {theme['radius']} {theme['shadow']} border {theme['border_color']}">
            <img src="{html.escape(hero_img)}" alt="{business_name}" class="h-44 w-full object-cover" onerror="this.onerror=null; this.src='{hero_fallback}';">
          </div>

          <div class="mt-5 space-y-2.5 text-left">
            {primary_btn_html}
            <div class="{sec_class}">
              {secondary_ctas_html}
            </div>
            <p class="pt-1 text-center text-[11px]" style="color: {theme['text_muted']};">
              {reviews_count} отзывов на картах • Запись онлайн за минуту
            </p>
          </div>
        </section>
        """

    # ── Service Cards ─────────────────────────────────────────────────────────
    service_cards = "".join(
        f"""<div class="flex items-start justify-between gap-3 p-4 {theme['radius_inner']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
          <div class="min-w-0 flex-1">
            <p class="text-sm font-bold truncate" style="color: {theme['text_primary']};">{_safe(name)}</p>
            <p class="mt-1 text-xs leading-relaxed" style="color: {theme['text_secondary']};">{_safe(desc)}</p>
          </div>
          <span class="shrink-0 whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-bold" style="background-color: {theme['accent_soft']}; color: {theme['accent']}; border: 1px solid {theme['accent_border']};">{_safe(price)}</span>
        </div>"""
        for name, price, desc in profile["services"]
    )

    # ── Benefit Cards ─────────────────────────────────────────────────────────
    benefit_cards = "".join(
        f"""<div class="p-4 {theme['radius_inner']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
          <div class="flex items-center gap-2">
            <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold" style="background-color: {theme['accent_soft']}; color: {theme['accent']};">✓</span>
            <p class="text-sm font-bold truncate" style="color: {theme['text_primary']};">{_safe(title)}</p>
          </div>
          <p class="mt-2 text-xs leading-relaxed" style="color: {theme['text_secondary']};">{_safe(desc)}</p>
        </div>"""
        for title, desc in profile["benefits"]
    )

    # ── Review Cards ──────────────────────────────────────────────────────────
    review_cards = "".join(
        f"""<div class="p-4 {theme['radius_inner']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
          <div class="flex items-center justify-between">
            <p class="text-sm font-bold" style="color: {theme['text_primary']};">{_safe(author)}</p>
            <span class="text-xs text-amber-400">★★★★★</span>
          </div>
          <p class="mt-2 text-xs leading-relaxed italic" style="color: {theme['text_secondary']};">«{_safe(text)}»</p>
        </div>"""
        for author, text in profile["reviews"]
    )

    # ── Gallery Section (Real photos from Yandex / Telegram / Curated) ────────
    gallery_items_html = ""
    for idx, g_img in enumerate(gallery_imgs[:4]):
        fb_src = niche_fallback["gallery"][idx % len(niche_fallback["gallery"])]
        gallery_items_html += f"""
        <div class="relative overflow-hidden {theme['radius_inner']} border {theme['border_color']} aspect-[4/3] group">
          <img src="{html.escape(g_img)}" alt="Фото {business_name} {idx+1}" class="h-full w-full object-cover transition duration-300 group-hover:scale-105" onerror="this.onerror=null; this.src='{fb_src}';">
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{business_name} — {_safe(category)} {city_in}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{theme['font_css']}
<script src="https://cdn.tailwindcss.com"></script>
<style>
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: {theme['font_body']};
    background-color: {theme['bg_page']};
    color: {theme['text_primary']};
  }}
  h1, h2, h3 {{
    font-family: {theme['font_heading']};
  }}
</style>
</head>
<body class="antialiased">

<!-- Floating Top Demo Badge -->
<div class="fixed top-3 inset-x-3 z-50 mx-auto max-w-md pointer-events-none">
  <div class="pointer-events-auto flex items-center justify-between gap-2.5 rounded-2xl border border-black/10 bg-white/95 px-3.5 py-2 shadow-xl backdrop-blur-md">
    <div class="flex items-center gap-2 min-w-0">
      <span class="relative flex h-2 w-2">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
      </span>
      <p class="truncate text-xs font-semibold text-slate-800">
        Демо-концепт для {business_name}
      </p>
    </div>
    <a href="https://t.me/Murasaki_website" target="_blank" rel="noopener" class="shrink-0 inline-flex items-center gap-1.5 rounded-xl bg-[#229ED9] px-2.5 py-1 text-[11px] font-bold text-white shadow-sm transition hover:bg-[#1C88BD]">
      <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.56 8.16l-1.97 9.28c-.15.65-.53.81-1.08.5l-3-2.21-1.45 1.4c-.16.16-.3.3-.61.3l.21-3.05 5.56-5.02c.24-.22-.05-.34-.38-.13l-6.87 4.33-2.96-.92c-.64-.2-.66-.64.13-.95l11.57-4.46c.54-.19 1.01.14.88.93z"/></svg>
      <span>Написать</span>
    </a>
  </div>
</div>

<div class="mx-auto min-h-screen max-w-md shadow-2xl pt-8" style="background-color: {theme['bg_container']};">

  <!-- HERO SECTION -->
  {hero_html}

  <!-- TAGLINE REVEAL -->
  <section class="border-y px-5 py-7" style="border-color: {theme['border_color']}; background-color: {theme['bg_card']};">
    <p class="text-[11px] font-bold uppercase tracking-wider" style="color: {theme['accent']};">Главный ориентир</p>
    <p class="mt-2 text-2xl font-bold leading-snug tracking-tight [text-wrap:balance]" style="font-family: {theme['font_heading']}; color: {theme['text_primary']};">
      Качество, за которым клиенты возвращаются снова
    </p>
    <p class="mt-2 text-xs leading-relaxed [text-wrap:pretty]" style="color: {theme['text_secondary']};">
      Честный подход, открытый расчет стоимости до начала работы и внимательное отношение к каждому посетителю.
    </p>
  </section>

  <!-- HOW IT WORKS -->
  <section class="px-5 py-7 border-b" style="border-color: {theme['border_color']};">
    <h2 class="text-lg font-bold tracking-tight" style="color: {theme['text_primary']};">Как мы работаем</h2>
    <div class="mt-4 grid grid-cols-3 gap-2 text-center">
      <div class="p-3 {theme['radius_inner']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
        <span class="text-xs font-bold" style="color: {theme['accent']};">01</span>
        <p class="mt-1 text-xs font-bold" style="color: {theme['text_primary']};">Заявка</p>
        <p class="mt-0.5 text-[10px]" style="color: {theme['text_muted']};">В один клик</p>
      </div>
      <div class="p-3 {theme['radius_inner']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
        <span class="text-xs font-bold" style="color: {theme['accent']};">02</span>
        <p class="mt-1 text-xs font-bold" style="color: {theme['text_primary']};">Детали</p>
        <p class="mt-0.5 text-[10px]" style="color: {theme['text_muted']};">За 5 минут</p>
      </div>
      <div class="p-3 {theme['radius_inner']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
        <span class="text-xs font-bold" style="color: {theme['accent']};">03</span>
        <p class="mt-1 text-xs font-bold" style="color: {theme['text_primary']};">Результат</p>
        <p class="mt-0.5 text-[10px]" style="color: {theme['text_muted']};">С гарантией</p>
      </div>
    </div>
  </section>

  <!-- SERVICES & PRICES -->
  <section class="px-5 py-7">
    <div class="flex items-end justify-between">
      <h2 class="text-lg font-bold tracking-tight" style="color: {theme['text_primary']};">Услуги и цены</h2>
      <span class="text-xs font-medium" style="color: {theme['text_muted']};">актуальный прайс</span>
    </div>
    <div class="mt-4 space-y-2.5">
      {service_cards}
    </div>
  </section>

  <!-- PHOTO GALLERY / ATMOSPHERE -->
  <section class="border-y px-5 py-7" style="border-color: {theme['border_color']}; background-color: {theme['bg_card']};">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-bold tracking-tight" style="color: {theme['text_primary']};">Атмосфера и работы</h2>
      <span class="text-xs font-medium" style="color: {theme['text_muted']};">реальные кадры</span>
    </div>
    <div class="mt-4 grid grid-cols-2 gap-2.5">
      {gallery_items_html}
    </div>
  </section>

  <!-- BENEFITS -->
  <section class="px-5 py-7">
    <h2 class="text-lg font-bold tracking-tight" style="color: {theme['text_primary']};">Почему выбирают нас</h2>
    <div class="mt-4 grid grid-cols-2 gap-2.5">
      {benefit_cards}
    </div>
  </section>

  <!-- REVIEWS -->
  <section class="border-y px-5 py-7" style="border-color: {theme['border_color']}; background-color: {theme['bg_card']};">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-bold tracking-tight" style="color: {theme['text_primary']};">Отзывы гостей</h2>
      <span class="text-xs text-amber-500 font-semibold">★ {rating} на картах</span>
    </div>
    <div class="mt-4 space-y-2.5">
      {review_cards}
    </div>
  </section>

  <!-- RISK REVERSAL -->
  <section class="px-5 py-6">
    <div class="p-4 {theme['radius_inner']} border" style="background-color: {theme['accent_soft']}; border-color: {theme['accent_border']};">
      <p class="text-xs font-bold uppercase tracking-wider" style="color: {theme['accent']};">Гарантия прозрачности</p>
      <p class="mt-1 text-sm font-bold" style="color: {theme['text_primary']};">Честная смета без неожиданных доплат</p>
      <p class="mt-1 text-xs leading-relaxed" style="color: {theme['text_secondary']};">
        Все детали и стоимость фиксируются до начала оказания услуг. Вы платите только за согласованный результат.
      </p>
    </div>
  </section>

  <!-- CONTACTS & LOCATION -->
  <section class="px-5 pb-7">
    <div class="p-5 {theme['radius']} border {theme['border_color']}" style="background-color: {theme['bg_card']};">
      <h2 class="text-lg font-bold tracking-tight" style="color: {theme['text_primary']};">Как нас найти</h2>
      <div class="mt-3.5 space-y-2 text-xs leading-relaxed" style="color: {theme['text_secondary']};">
        <p class="flex items-start gap-2"><span>📍</span><span>{address}</span></p>
        <p class="flex items-start gap-2"><span>🕘</span><span>{hours}</span></p>
      </div>
      <a href="{html.escape(map_url)}" target="_blank" rel="noopener" class="mt-4 inline-flex h-11 w-full items-center justify-center {theme['radius_inner']} border text-xs font-bold transition hover:opacity-90" style="background-color: {theme['badge_bg']}; border-color: {theme['badge_border']}; color: {theme['text_primary']};">
        Открыть на Яндекс Картах →
      </a>
    </div>
  </section>

  <!-- FOOTER -->
  <footer class="border-t px-5 py-6 text-center text-xs" style="border-color: {theme['border_color']}; color: {theme['text_muted']};">
    <p class="font-bold" style="color: {theme['text_primary']};">{business_name}</p>
    <p class="mt-1">{city} · {_safe(category)}</p>
    <div class="mt-4 pt-3 border-t border-dashed" style="border-color: {theme['border_color']};">
      <p class="text-[11px] leading-relaxed">
        💡 Этот сайт является персональным интерактивным демо-концептом, созданным на платформе <b>Murasaki LeadRadar</b>.
      </p>
      <a href="https://t.me/Murasaki_website" target="_blank" rel="noopener" class="mt-2 inline-flex items-center gap-1 font-semibold text-[#229ED9] hover:underline">
        <span>Связаться с разработчиком в Telegram</span> →
      </a>
    </div>
    <p class="mt-4 text-[10px]">© 2026 {business_name}. Все права защищены.</p>
  </footer>

  <div class="h-24"></div>
</div>

<!-- STICKY BOTTOM ACTION BAR -->
<div class="fixed inset-x-0 bottom-0 z-40 border-t backdrop-blur-xl" style="background-color: {theme['bg_page']}F0; border-color: {theme['border_color']};">
  <div class="mx-auto flex max-w-md items-center justify-between gap-3 px-4 py-3">
    <div class="min-w-0 flex-1">
      <p class="truncate text-xs font-bold" style="color: {theme['text_primary']};">{business_name}</p>
      <p class="truncate text-[11px]" style="color: {theme['text_muted']};">{_safe(profile['tagline'])}</p>
    </div>
    <a href="{html.escape(primary_href)}" target="_blank" rel="noopener" class="inline-flex h-11 shrink-0 items-center justify-center {theme['radius_inner']} px-5 text-xs font-bold transition hover:opacity-95" style="background-color: {theme['accent']}; color: {theme['accent_text']}; box-shadow: 0 4px 12px {theme['accent']}35;">
      {_safe(sticky_label)}
    </a>
  </div>
</div>

</body>
</html>
"""


def _sanitize_html(value: str) -> str:
    value = re.sub(
        r"<script(?![^>]*cdn\.tailwindcss\.com)[^>]*>.*?</script>",
        "",
        value,
        flags=re.I | re.S,
    )
    value = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", value, flags=re.I)
    value = re.sub(r"<(object|embed|form)\b[^>]*>.*?</\1>", "", value, flags=re.I | re.S)
    return value


def _extract_html(raw: str) -> str | None:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:html)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.lower().find("<!doctype html")
    if start == -1:
        start = cleaned.lower().find("<html")
    if start == -1:
        return None
    cleaned = cleaned[start:]
    if "</html>" not in cleaned.lower():
        cleaned += "\n</html>"
    if len(cleaned) < 800:
        return None
    return _sanitize_html(cleaned)


LANDING_SYSTEM = (
    "Ты ведущий UI/UX дизайнер и frontend-разработчик премиальных конверсионных мобильных сайтов. "
    "Твоя задача — создать превосходный адаптивный посадочный сайт (mobile-first), адаптированный под нишу бизнеса. "
    "Используй Google Fonts, Tailwind CSS и стильную цветовую гамму ниши (светлую пастельную для бьюти/медицины, темную графитовую для авто, теплую для кафе, строгую сине-белую для юристов/B2B). "
    "Обязательно добавь в верстку плавающую плашку демо-концепта со ссылкой на Telegram разработчика (https://t.me/Murasaki_website). "
    "Отвечай ИСКЛЮЧИТЕЛЬНО готовым полным валидным HTML-кодом (начиная с <!DOCTYPE html> и заканчивая </html>), "
    "без markdown-разметки (без тройных бэктиков), без вступительных и заключительных комментариев."
)

LANDING_PROMPT = Template(
    """Создай премиальный конверсионный мобильный лендинг (mobile-first, max-w-md mx-auto) для бизнеса:

Данные компании в JSON:
$company

CTA-ссылки:
- WhatsApp: $whatsapp_link
- Telegram: $telegram_link
- Телефон: $phone_link

ТРЕБОВАНИЯ К ДИЗАЙНУ И СТРУКТУРЕ:
1. Тематическая палитра и шрифты под нишу «$category»:
   - Подбери шрифты через Google Fonts (например, Playfair Display/Cormorant для бьюти, Montserrat для авто, Lora/Plus Jakarta Sans для ресторанов, Inter для юристов).
   - Цветовая гамма строго соответствует нише бизнеса.
2. Вёрстка первого экрана (Hero):
   - Заголовок (результат + аудитория), подзаголовок, бейдж рейтинга, главный CTA, вторичные кнопки (Telegram/Телефон).
   - Вставь реальные фото компании или качественные тематические фото. Для всех тегов <img> ОБЯЗАТЕЛЬНО укажи защитный атрибут onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1200&q=80';".
3. Секции:
   - Tagline Reveal: ключевая ценность бизнеса крупным шрифтом.
   - Как мы работаем: 3 последовательных шага.
   - Услуги и цены: карточки с понятными описаниями и ценами.
   - Галерея: 3-4 фото с закругленными углами.
   - Преимущества и Выгоды: 4 карточки.
   - Отзывы: 3 реалистичных отзыва с именами и оценками 5★.
   - Контакты и адрес с кнопкой открытия Яндекс Карт.
4. Обязательная демо-плашка:
   - Закрепленная плавающая аккуратная плашка или футер с пометкой: «Персональный демо-концепт для $name • Связаться с разработчиком в Telegram (https://t.me/Murasaki_website)».
   - Фиксированная нижняя панель (sticky bottom bar) с кнопкой быстрой связи.

Верни ТОЛЬКО готовый валидный HTML код."""
)


def detect_template_id(category: str | None, style_id: str | None = None) -> str:
    """Select the best matching Jinja2 template based on business category or requested style."""
    if style_id:
        from app.services.design_systems import resolve_style_id
        return resolve_style_id(style_id, category)

    cat = (category or "").lower()
    if any(k in cat for k in ("бьюти", "красот", "маникюр", "педикюр", "волос", "парикмахер", "косметол", "цветы", "одежд", "спа", "ногти", "брови")):
        return "luxury_editorial"
    if any(k in cat for k in ("авто", "сервис", "шиномонтаж", "детейлинг", "мойка", "кузов", "сто", "барбер", "спорт", "стройк", "ремонт авто")):
        return "dark_cyber_neon"
    if any(k in cat for k in ("ресторан", "кафе", "кофейн", "пекарн", "доставка еды", "пицц", "суши", "бургер", "бар", "кухн", "кондитер")):
        return "warm_artisan_coffee"
    if any(k in cat for k in ("бабл-ти", "мороженое", "десерт", "торт", "детск", "груминг")):
        return "playful_pastel"
    if any(k in cat for k in ("дизайн", "digital", "агентств", "тату")):
        return "acid_neo_brutalism"
    return "clean_swiss_trust"


def build_seo_head_tags(
    business_dict: dict[str, Any],
    content_json: dict[str, Any],
    hero_image: str = "",
    public_url: str = "",
) -> str:
    """Build meta description, OpenGraph tags and Schema.org LocalBusiness JSON-LD."""
    name = str(business_dict.get("name") or "Компания").strip()
    category = str(business_dict.get("category") or "Услуги").strip()
    city = str(business_dict.get("city") or "").strip()
    address = str(business_dict.get("address") or city).strip()
    phone = str(business_dict.get("phone") or "").strip()
    city_in = _city_in(city) if city else ""

    title_str = f"{name} — {category} {city_in}".strip()
    desc_raw = str(content_json.get("hero_subtitle") or "").strip()
    if not desc_raw:
        desc_raw = f"{name}: {category.lower()} {city_in}. Запись онлайн, прайс-лист, отзывы и контакты.".strip()
    desc_str = desc_raw[:220]

    og_image = ""
    if public_url and public_url.strip().startswith(("http://", "https://")):
        og_image = f"{public_url.strip().rstrip('/')}/og.png"
    elif hero_image:
        og_image = hero_image.strip()
    else:
        photos = business_dict.get("photos") or []
        if photos:
            og_image = str(photos[0])

    schema_image = (hero_image or "").strip() or og_image

    tags = [
        f'<meta name="description" content="{html.escape(desc_str)}">',
        '<meta property="og:type" content="business.business">',
        '<meta property="og:locale" content="ru_RU">',
        f'<meta property="og:title" content="{html.escape(title_str)}">',
        f'<meta property="og:description" content="{html.escape(desc_str)}">',
    ]
    if og_image:
        tags.append(f'<meta property="og:image" content="{html.escape(og_image)}">')
        if og_image.endswith("/og.png"):
            tags.append('<meta property="og:image:width" content="1200">')
            tags.append('<meta property="og:image:height" content="630">')
    if public_url:
        tags.append(f'<meta property="og:url" content="{html.escape(public_url)}">')
    tags.append('<meta name="twitter:card" content="summary_large_image">')

    schema_obj: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "description": desc_str,
        "category": category,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address,
            "addressLocality": city or "Россия",
            "addressCountry": "RU",
        },
    }
    if schema_image:
        schema_obj["image"] = schema_image
    if phone:
        schema_obj["telephone"] = phone
    if public_url:
        schema_obj["url"] = public_url
    lat = business_dict.get("latitude")
    lon = business_dict.get("longitude")
    if lat is not None and lon is not None:
        schema_obj["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon}

    rating = business_dict.get("rating")
    reviews_count = business_dict.get("reviews_count") or 0
    if rating:
        try:
            schema_obj["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(float(rating), 1),
                "reviewCount": max(1, int(reviews_count)),
            }
        except (TypeError, ValueError):
            pass

    hours = business_dict.get("opening_hours") or []
    if hours:
        schema_obj["openingHours"] = hours[:7]

    json_ld = json.dumps(schema_obj, ensure_ascii=False).replace("</", "<\\/")
    tags.append(f'<script type="application/ld+json">{json_ld}</script>')
    return "\n".join(tags)


def inject_seo_and_head(
    html_text: str,
    business_dict: dict[str, Any],
    content_json: dict[str, Any],
    hero_image: str = "",
    public_url: str = "",
) -> str:
    """Ensure clean <title>, meta description, OpenGraph and LocalBusiness JSON-LD in <head>."""
    if not html_text:
        return html_text

    name = str(business_dict.get("name") or "Компания")
    category = str(business_dict.get("category") or "Услуги")
    city = str(business_dict.get("city") or "")
    city_in = _city_in(city) if city else ""

    # Clean up any stray single-brace template placeholders
    html_text = (
        html_text.replace("{ business.name }", html.escape(name))
        .replace("{business.name}", html.escape(name))
        .replace("{ business.category }", html.escape(category))
        .replace("{business.category}", html.escape(category))
        .replace("{ city_in }", html.escape(city_in))
        .replace("{city_in}", html.escape(city_in))
    )

    if 'property="og:title"' in html_text or 'application/ld+json' in html_text:
        return html_text

    seo_block = build_seo_head_tags(business_dict, content_json, hero_image, public_url)
    head_close = html_text.lower().find("</head>")
    if head_close != -1:
        return html_text[:head_close] + "\n" + seo_block + "\n" + html_text[head_close:]
    return seo_block + "\n" + html_text


def _is_light_hex(hex_color: str | None) -> bool:
    """Return True when a hex color has high perceived brightness (needs dark text)."""
    if not hex_color or not isinstance(hex_color, str):
        return False
    val = hex_color.strip().lstrip("#")
    if len(val) == 3:
        val = "".join(ch * 2 for ch in val)
    if len(val) != 6:
        return False
    try:
        r = int(val[0:2], 16)
        g = int(val[2:4], 16)
        b = int(val[4:6], 16)
    except ValueError:
        return False
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return luminance > 0.58


def render_jinja_demo(
    template_id: str,
    business_dict: dict[str, Any],
    content_json: dict[str, Any],
    hero_image: str,
    gallery_photos: list[str],
    public_url: str = "",
) -> str:
    """Renders the 9-section production landing page using style tokens from DESIGN.md."""
    from app.services.design_systems import get_style
    from app.services.media_collector import get_niche_fallback

    category = business_dict.get("category") or "Бизнес"
    style_meta = get_style(template_id, category)
    colors = style_meta.get("preview_colors") or {}
    tone = style_meta.get("tone") or "light"
    bg_color = colors.get("bg") or ("#0D0E12" if tone in ("dark", "vibrant", "graphite") else "#F8FAFC")
    is_dark = not _is_light_hex(bg_color)
    card_color = colors.get("card") or ("#161822" if is_dark else "#FFFFFF")
    card_is_dark = not _is_light_hex(card_color)

    text_color = colors.get("text") or ("#F8FAFC" if card_is_dark else "#0F172A")
    if card_is_dark and not _is_light_hex(text_color):
        text_color = "#F8FAFC"
    elif not card_is_dark and _is_light_hex(text_color):
        text_color = "#0F172A"

    from app.services.brand_color import build_brand_css_tokens

    accent = colors.get("accent") or "#2563EB"
    explicit_brand_color = (business_dict.get("brand_color") or "").strip()
    if explicit_brand_color:
        accent = explicit_brand_color

    brand_tokens = build_brand_css_tokens(accent)
    accent = brand_tokens["brand_accent"]
    accent_light = _is_light_hex(accent)
    accent_fg = "#09090B" if accent_light else "#FFFFFF"
    promo_btn_bg = "#09090B" if accent_light else "#FFFFFF"
    promo_btn_fg = "#FFFFFF" if accent_light else "#09090B"
    promo_badge_bg = "rgba(0,0,0,0.10)" if accent_light else "rgba(255,255,255,0.18)"

    style_ctx = {
        "colors": {
            "bg": bg_color,
            "card": card_color,
            "accent": accent,
            "brand_accent": brand_tokens["brand_accent"],
            "brand_accent_hover": brand_tokens["brand_accent_hover"],
            "brand_accent_soft": brand_tokens["brand_accent_soft"],
            "text": text_color,
            "subtext": colors.get("subtext") or ("#94A3B8" if card_is_dark else "#475569"),
            "badge_bg": colors.get("badge_bg") or ("#1F2433" if is_dark else "#F1F5F9"),
        },
        "font_css": style_meta.get("font_css") or "",
        "font_heading": style_meta.get("font_heading") or "'Inter', sans-serif",
        "font_body": style_meta.get("font_body") or "'Inter', sans-serif",
        "border": "rgba(255,255,255,0.10)" if is_dark else "rgba(15,23,42,0.10)",
        "alt_bg": "rgba(255,255,255,0.025)" if is_dark else "rgba(15,23,42,0.025)",
        "nav_bg": "rgba(13,14,18,0.86)" if is_dark else "rgba(255,255,255,0.88)",
        "accent_fg": accent_fg,
        "promo_btn_bg": promo_btn_bg,
        "promo_btn_fg": promo_btn_fg,
        "promo_badge_bg": promo_badge_bg,
    }

    phone_raw = business_dict.get("phone")
    tel_href = format_tel_href(phone_raw)
    socials = business_dict.get("social_links") or {}
    wa_digits = re.sub(r"\D", "", str(socials.get("whatsapp") or phone_raw or ""))
    if len(wa_digits) == 11 and wa_digits.startswith("8"):
        wa_digits = "7" + wa_digits[1:]
    elif len(wa_digits) == 10:
        wa_digits = "7" + wa_digits
    whatsapp_url = socials.get("whatsapp") or (f"https://wa.me/{wa_digits}" if len(wa_digits) >= 11 else "")
    telegram_url = socials.get("telegram") or ""
    primary_cta = whatsapp_url or telegram_url or tel_href or "#contacts"
    city = business_dict.get("city") or "Россия"
    city_in = _city_in(city)

    safe_business = dict(business_dict)
    if safe_business.get("rating") is not None:
        try:
            safe_business["rating"] = round(float(safe_business["rating"]), 1)
        except (TypeError, ValueError):
            pass

    safe_content = dict(content_json or {})
    price_categories: list[str] = []
    if isinstance(safe_content.get("services"), list):
        cleaned_services = []
        for srv in safe_content["services"]:
            if not isinstance(srv, dict):
                continue
            item = dict(srv)
            price = str(item.get("price") or "").strip()
            # Clean accidental double ruble signs
            price = re.sub(r"(?:₽\s*){2,}", "₽", price).strip()
            if price and re.fullmatch(r"[\d\s.,\-–]+", price):
                price = f"{price} ₽"
            item["price"] = price
            cat_label = str(item.get("category") or "Популярное").strip()
            item["category"] = cat_label
            if cat_label not in price_categories:
                price_categories.append(cat_label)
            cleaned_services.append(item)
        safe_content["services"] = cleaned_services

    safe_content.setdefault("usp_list", [])
    safe_content.setdefault("services", [])
    safe_content.setdefault("reviews", [])
    safe_content.setdefault("faq", [])
    safe_content.setdefault("promo", None)

    # Display only reviews collected from Yandex Maps; never present LLM text as a testimonial.
    safe_content["reviews"] = [
        review for review in (business_dict.get("yandex_reviews") or [])
        if isinstance(review, dict) and str(review.get("text") or "").strip()
    ][:6]
    phone_text = str(safe_business.get("phone") or "").strip()
    faq_items = [item for item in safe_content.get("faq", []) if isinstance(item, dict)]
    for item in faq_items:
        answer = re.sub(r"\b8-800(?:[- ]\d{2,4}){2,4}\b", "", str(item.get("answer") or ""))
        if phone_text and re.search(r"(?i)телефон|позвон|связаться", str(item.get("question") or "")):
            answer = f"Позвоните по номеру {phone_text}."
        item["answer"] = answer.strip()
    if phone_text and not any(
        re.search(r"(?i)телефон|позвон|связаться", str(item.get("question") or "")) for item in faq_items
    ):
        faq_items.append({"question": "Как связаться по телефону?", "answer": f"Позвоните по номеру {phone_text}."})
    safe_content["faq"] = faq_items

    is_food_business = bool(re.search(r"(?i)caf[eé]|restaurant|coffee|кафе|ресторан|кофейн|пекарн|столов", category))
    if not is_food_business and safe_content.get("hero_subtitle"):
        safe_content["hero_subtitle"] = re.sub(
            r"\s*(?:[|•,–—-]\s*)?(?:бесплатный\s+)?wi[\s-]?fi\b\.?",
            "",
            str(safe_content["hero_subtitle"]),
            flags=re.I,
        ).strip()

    if not safe_content.get("facts"):
        safe_content["facts"] = [
            {"value": f"{safe_business.get('rating') or 4.9} ★", "label": "Рейтинг на картах"},
            {"value": f"{safe_business.get('reviews_count') or 18}+", "label": "Отзывов клиентов"},
            {"value": "100%", "label": "Фиксированная смета"},
            {"value": "10 мин", "label": "Ответ в мессенджере"},
        ]

    niche_fb = get_niche_fallback(
        category,
        business_name=business_dict.get("name"),
        services=safe_content.get("services"),
        public_url=public_url,
    )
    fb_hero = niche_fb["hero"]
    fb_works = list(niche_fb.get("works") or niche_fb.get("gallery") or [])
    fb_interior = list(niche_fb.get("interior") or niche_fb.get("gallery") or [])

    has_explicit_split = "hero_product" in business_dict or "interior_photos" in business_dict
    rejected_set = set(business_dict.get("rejected_photos") or [])
    raw_hero_product = [
        u for u in (business_dict.get("hero_product") or [])
        if u and u not in rejected_set and "images.unsplash.com" not in u
    ]
    raw_interior = [
        u for u in (business_dict.get("interior_photos") or [])
        if u and u not in rejected_set and "images.unsplash.com" not in u
    ]

    all_photos = [
        u for u in ([hero_image] + list(gallery_photos or []) + list(business_dict.get("photos") or []) + raw_hero_product + raw_interior)
        if u and u not in rejected_set and "images.unsplash.com" not in u
    ]
    all_photos = list(dict.fromkeys(all_photos))
    business_photos = [url for url in all_photos if "/static/stock/" not in url]
    has_business_photos = bool(business_photos)
    if has_business_photos:
        fb_hero = ""
        fb_works = []
        fb_interior = []
    if has_explicit_split:
        work_urls = list(dict.fromkeys(raw_hero_product)) or (business_photos[:3] if has_business_photos else fb_works[:3])
        used_works = set(work_urls)
        interior_candidates = [u for u in dict.fromkeys(raw_interior) if u not in used_works]
        interior_urls = (
            interior_candidates
            or [u for u in business_photos if u not in used_works][:3]
            or [u for u in fb_interior if u not in used_works][:3]
            or fb_interior[:3]
        )
        effective_hero = (
            (raw_hero_product[0] if raw_hero_product else None)
            or (hero_image if has_business_photos else None)
            or (all_photos[0] if has_business_photos and all_photos else None)
            or fb_hero
            or (raw_interior[0] if raw_interior else None)
        )
    else:
        safe_hero_in = (
            hero_image
            if (hero_image and hero_image not in rejected_set and "images.unsplash.com" not in hero_image and "/static/stock/" not in hero_image)
            else None
        )
        non_stock_all = business_photos
        work_urls = (
            list(dict.fromkeys(([safe_hero_in] if safe_hero_in else []) + non_stock_all[:3]))
            or fb_works[:3]
        )
        used_works = set(work_urls)
        interior_candidates = [u for u in dict.fromkeys(non_stock_all[3:8]) if u not in used_works]
        interior_urls = (
            interior_candidates
            or [u for u in all_photos if u not in used_works][:3]
            or [u for u in fb_interior if u not in used_works][:3]
            or fb_interior[:3]
        )
        effective_hero = safe_hero_in or fb_hero or (work_urls[0] if work_urls else "")

    work_captions_map: dict[str, str] = dict(niche_fb.get("work_captions") or {})
    raw_captions = business_dict.get("work_captions")
    if isinstance(raw_captions, dict):
        for u, cap in raw_captions.items():
            if isinstance(u, str) and isinstance(cap, str) and cap.strip():
                work_captions_map[u] = cap.strip()

    work_cards = []
    for url in work_urls[:6]:
        caption = work_captions_map.get(url) or "Работа мастера"
        work_cards.append({"url": url, "caption": caption})

    tmpl = jinja_env.get_template("_master_9sections.html")
    rendered = tmpl.render(
        business=safe_business,
        content=safe_content,
        style=style_ctx,
        hero_image=effective_hero,
        fallback_hero_image=fb_hero,
        fallback_work_image=fb_works[0] if fb_works else fb_hero,
        fallback_interior_image=fb_interior[0] if fb_interior else fb_hero,
        gallery_photos=all_photos,
        work_cards=work_cards,
        interior_photos=interior_urls,
        price_categories=price_categories,
        tel_href=tel_href,
        whatsapp_url=whatsapp_url,
        telegram_url=telegram_url,
        primary_cta_href=primary_cta,
        map_url=business_dict.get("yandex_map_url") or f"https://yandex.ru/maps/?text={quote(business_dict.get('name', '') + ' ' + city)}",
        city_in=city_in,
    )
    rendered = inject_seo_and_head(rendered, safe_business, safe_content, effective_hero, public_url)
    return inject_murasaki_badge(rendered, business_dict.get("name") or "")


async def generate_landing_html(
    lead: dict,
    style_id: str | None = None,
    public_url: str = "",
) -> tuple[str, str]:
    """
    Generates an HTML landing page via structured AI JSON + dedicated Jinja2 templates
    powered by VoltAgent/awesome-design-md design systems:
      - dark_cyber_neon: Automotive, tech, AI, gaming, barbershops
      - warm_artisan_coffee: Cafes, bakeries, craft restaurants, specialty food
      - luxury_editorial: Beauty, aesthetic cosmetics, fashion, architecture
      - acid_neo_brutalism: Digital agencies, streetwear, tattoo, creative
      - clean_swiss_trust: Medicine, law, corporate B2B, real estate
      - playful_pastel: Bubble tea, desserts, kids centers, grooming
    """
    from app.services.design_systems import resolve_style_id
    from app.services.media_collector import get_niche_fallback

    category = lead.get("category") or "Бизнес"
    effective_style = resolve_style_id(style_id, category)
    niche_fallback = get_niche_fallback(
        category,
        business_name=lead.get("name"),
        services=lead.get("services"),
        public_url=public_url,
    )
    photos = [p for p in (lead.get("photos") or []) if isinstance(p, str) and "images.unsplash.com" not in p]
    hero_img = photos[0] if photos else niche_fallback.get("hero")
    gallery_imgs = photos[1:7] if photos else niche_fallback.get("gallery", [])

    # 1. Generate structured JSON from LLM
    try:
        from app.services.ai_router import generate_demo_json
        content_json = await asyncio.wait_for(
            generate_demo_json(
                lead_dict=lead,
                hero_photos=[hero_img] if hero_img else [],
                interior_photos=gallery_imgs,
                requested_style=effective_style,
            ),
            timeout=8.0,
        )
        template_id = content_json.get("template_id") or effective_style
        html_code = render_jinja_demo(
            template_id=template_id,
            business_dict=lead,
            content_json=content_json,
            hero_image=hero_img or "",
            gallery_photos=gallery_imgs,
            public_url=public_url,
        )
        return html_code, "jinja2_llm"
    except Exception as exc:
        logger.warning("LLM landing JSON failed: %s, falling back to deterministic Jinja2 render", exc)

    # 2. Deterministic Jinja2 render fallback
    template_id = effective_style
    from app.services.ai_router import generate_demo_json
    fallback_json = await generate_demo_json(
        lead,
        [hero_img] if hero_img else [],
        gallery_imgs,
        requested_style=effective_style,
    )
    html_code = render_jinja_demo(
        template_id=template_id,
        business_dict=lead,
        content_json=fallback_json,
        hero_image=hero_img or "",
        gallery_photos=gallery_imgs,
        public_url=public_url,
    )
    return html_code, "jinja2_template"


OUTREACH_SYSTEM = (
    "Ты профессиональный B2B-копирайтер для фрилансеров и веб-студий. "
    "Твоя задача — составить короткий, тактичный, уважительный и ненавязчивый текст первого отклика "
    "владельцу бизнеса в мессенджере (WhatsApp или Telegram). "
    "Отвечай ТОЛЬКО готовым текстом сообщения без кавычек в начале/конце и без вступительных пояснений."
)

OUTREACH_PROMPT = Template(
    """Составь короткое первое сообщение для владельца компании:
- Название компании: $name
- Сфера: $category
- Город: $city
- Наличие сайта: $has_site
- Ссылка на персональный демо-концепт: $demo_url

Правила:
1. Начни вежливо (например: «Добрый день! Подготовил персональный демо-концепт сайта для «$name» в ваших фирменных цветах:»).
2. НЕ критикуй клиента («у вас плохой сайт», «клиенты уходят к конкурентам»). Никакого давления и агрессивного спама.
3. Вынеси ссылку $demo_url на ОТДЕЛЬНУЮ строку и НИКОГДА не ставь точку, запятую или скобку сразу после ссылки.
4. Аккуратно в конце предложи формат: если концепт понравится — за 5 000 ₽ развернуть сайт под ключ на их домене и добавить свежий кейс в портфолио, завершив мягким вопросом на вовлечение (например: «Актуально?»).
5. Пиши грамотно («в портфолио»), живым естественным языком (до 75-110 слов)."""
)


def _format_clean_outreach_url(text: str, demo_url: str) -> str:
    """Ensure demo_url has no trailing punctuation glued to it."""
    if not demo_url or demo_url not in text:
        return text
    return re.sub(rf"({re.escape(demo_url)})[.,;:!?)\]]+", r"\1", text)


def build_outreach(lead: dict, demo_url: str) -> str:
    city = lead.get("city") or ""
    city_in = _city_in(city)
    name = lead.get("name") or "ваша компания"
    noun = _business_noun(lead.get("category"))
    plural_gen = BUSINESS_PLURAL_GENITIVE.get(lead.get("category") or "", "локального бизнеса")

    if lead.get("has_website"):
        lead_context = f"Подготовил персональный демо-концепт обновления сайта для «{name}» ({noun}, {city_in}) в ваших фирменных цветах:"
    else:
        lead_context = f"Подготовил персональный демо-концепт сайта для «{name}» ({noun}, {city_in}) в ваших фирменных цветах:"

    return (
        f"Добрый день! {lead_context}\n"
        f"{demo_url}\n\n"
        f"Собрал структуру под {plural_gen} с понятным прайсом и удобной записью клиентов с телефона.\n\n"
        f"Если концепт понравится — за 5 000 ₽ разверну сайт под ключ на вашем домене и добавлю свежий кейс в портфолио. Актуально?"
    )


async def generate_outreach_message(lead: dict, demo_url: str) -> str:
    if settings.llm_provider and settings.llm_provider.lower() not in ("mock", "template", "none"):
        name = lead.get("name") or "ваша компания"
        category = lead.get("category") or "Бизнес"
        city = lead.get("city") or "Россия"
        has_site = "Есть сайт" if lead.get("has_website") else "Нет отдельного сайта"
        prompt = OUTREACH_PROMPT.safe_substitute(
            name=name,
            category=category,
            city=city,
            has_site=has_site,
            demo_url=demo_url,
        )
        try:
            raw = await asyncio.wait_for(
                ask_ai(prompt, system_prompt=OUTREACH_SYSTEM, task_type="fast", max_tokens=300, temperature=0.7),
                timeout=4.0,
            )
            cleaned = _format_clean_outreach_url(raw.strip().strip('"').strip("'"), demo_url)
            if cleaned and demo_url in cleaned and len(cleaned) > 50:
                return cleaned
        except Exception:
            pass
    return build_outreach(lead, demo_url)
