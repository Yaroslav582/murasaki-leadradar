from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import DemoSite, Lead
from app.services.ai_router import sort_business_photos
from app.services.landing import (
    detect_template_id,
    format_tel_href,
    generate_landing_html,
    inject_murasaki_badge,
    render_jinja_demo,
)
from app.services.media_collector import collect_media, is_trash_or_screenshot


def test_trash_or_screenshot_detection():
    assert is_trash_or_screenshot("https://example.com/screenshot_123.jpg") is True
    assert is_trash_or_screenshot("https://example.com/receipt_chek.png") is True
    assert is_trash_or_screenshot("https://avatars.mds.yandex.net/get-altay/1200x3600/normal") is True
    assert is_trash_or_screenshot("https://images.unsplash.com/photo-12345.jpg") is False


@pytest.mark.asyncio
async def test_collect_media_niche_fallback():
    lead_dict = {
        "name": "Студия Красоты Элеганс",
        "category": "Бьюти",
        "city": "Москва",
        "photos": [],
    }
    media = await collect_media(lead_dict, max_items=8)
    assert media["count"] >= 2
    assert len(media["photos"]) >= 2
    assert any("unsplash" in p for p in media["photos"])


@pytest.mark.asyncio
async def test_sort_business_photos_categories():
    sample_photos = [
        "https://images.unsplash.com/photo-1",
        "https://images.unsplash.com/photo-2",
        "https://images.unsplash.com/photo-3",
        "https://example.com/chat_screenshot.jpg",
    ]
    res = await sort_business_photos(sample_photos, business_category="Автосервис", business_name="Турбо Гараж")
    assert "hero_product" in res
    assert "interior" in res
    assert "trash" in res
    assert res["hero"] is not None
    assert isinstance(res["gallery"], list)


def test_format_tel_href_strict():
    assert format_tel_href("+7 (999) 123-45-67") == "tel:+79991234567"
    assert format_tel_href("89991234567") == "tel:+79991234567"
    assert format_tel_href("9991234567") == "tel:+79991234567"
    assert format_tel_href("") == ""
    assert format_tel_href(None) == ""


def test_murasaki_badge_injection():
    raw_html = "<!DOCTYPE html><html><body><div id='app'>Hello</div></body></html>"
    injected = inject_murasaki_badge(raw_html, "Автосервис Премиум")
    assert "Murasaki_website" in injected
    assert "Автосервис Премиум" in injected
    assert "</body>" in injected


@pytest.mark.parametrize("template_id", ["editorial_light", "dark_industrial", "warm_appetite", "clean_trust"])
def test_render_all_four_jinja_templates(template_id):
    business_dict = {
        "name": "Тестовый Бизнес",
        "category": "Услуги",
        "city": "Москва",
        "address": "ул. Тверская, 10",
        "phone": "+7 999 000-11-22",
        "rating": 4.9,
        "reviews_count": 28,
        "social_links": {"whatsapp": "https://wa.me/79990001122"},
    }
    content_json = {
        "template_id": template_id,
        "hero_title": "Заголовок первого экрана",
        "hero_subtitle": "Подзаголовок с конкретной ценностью",
        "usp_list": [
            {"title": "Преимущество 1", "desc": "Описание 1"},
            {"title": "Преимущество 2", "desc": "Описание 2"},
        ],
        "services": [
            {"name": "Услуга 1", "price": "от 2 000 ₽", "desc": "Описание услуги 1"},
            {"name": "Услуга 2", "price": "от 4 000 ₽", "desc": "Описание услуги 2"},
        ],
        "faq": [
            {"question": "Частый вопрос?", "answer": "Понятный ответ."},
        ],
    }

    html = render_jinja_demo(
        template_id=template_id,
        business_dict=business_dict,
        content_json=content_json,
        hero_image="https://images.unsplash.com/photo-hero",
        gallery_photos=["https://images.unsplash.com/photo-1", "https://images.unsplash.com/photo-2"],
    )

    assert "<!DOCTYPE html>" in html
    assert "Тестовый Бизнес" in html
    assert "tel:+79990001122" in html
    assert "Murasaki_website" in html


@pytest.mark.asyncio
async def test_custom_demo_auto_clean_and_badge(prepared_db):
    from app.db import SessionLocal
    from app.models import Lead, new_id

    lead_id = new_id()
    async with SessionLocal() as db:
        lead = Lead(id=lead_id, name="Барбершоп Борода", category="Бьюти", city="Москва")
        db.add(lead)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User pastes markdown-wrapped html with chat preamble
        dirty_input = """Конечно! Вот готовый код для вашего сайта:
```html
<!DOCTYPE html>
<html>
<head><title>Барбершоп</title></head>
<body>
<h1>Стрижки для мужчин</h1>
</body>
</html>
```
Надеюсь, вам понравилось!"""

        custom_res = await client.post(
            f"/api/leads/{lead_id}/custom-demo",
            json={"html": dirty_input, "title": "Кастомное Демо"},
        )
        assert custom_res.status_code == 200
        saved_html = custom_res.json()["html"]

        # Ensure markdown wrappers and chat chatter were stripped
        assert "```" not in saved_html
        assert "Конечно! Вот готовый код" not in saved_html
        assert "<!DOCTYPE html>" in saved_html
        assert "</html>" in saved_html

        # Ensure Murasaki badge was injected
        assert "Murasaki_website" in saved_html


@pytest.mark.asyncio
async def test_transactional_credits_demo_generation(prepared_db):
    from app.db import SessionLocal
    from app.models import Lead, User, new_id

    lead_id = new_id()
    async with SessionLocal() as db:
        lead = Lead(id=lead_id, name="Автомастерская СТО", category="Автосервисы", city="Москва")
        db.add(lead)
        # Create user with 50 credits
        user = User(id="default_user", telegram_id=999999, username="testuser", credits_balance=50)
        db.add(user)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger demo generation
        demo_res = await client.post(f"/api/leads/{lead_id}/demo")
        assert demo_res.status_code == 200
        data = demo_res.json()
        assert data["id"] is not None
        assert "html" in data
        assert "<!DOCTYPE html>" in data["html"]

        # Verify credits were deducted (50 - 5 = 45)
        billing_res = await client.get("/api/billing/balance")
        assert billing_res.status_code == 200
        assert billing_res.json()["credits_balance"] == 45
