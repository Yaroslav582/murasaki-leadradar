from __future__ import annotations

import pytest

from app.db import SessionLocal
from app.models import DemoSite, Lead
from app.schemas import LeadOut
from app.services.enrichment import audit_website


def test_audit_website_detects_stub_viewport_and_broken():
    broken = audit_website("https://dead-site.ru", html=None, status_code=502, ssl_valid=True, response_ms=4200)
    assert broken["is_alive"] is False
    assert broken["status_code"] == 502
    assert any("не открывается" in i for i in broken["issues"])
    assert any("Медленная загрузка" in i for i in broken["issues"])

    stub = audit_website(
        "https://taplink.cc/beauty_studio",
        html="<html><head></head><body>Hi</body></html>",
        final_url="https://taplink.cc/beauty_studio",
        status_code=200,
        ssl_valid=True,
        response_ms=300,
    )
    assert stub["is_alive"] is True
    assert stub["is_stub"] is True
    assert stub["stub_domain"] == "taplink.cc"
    assert stub["has_viewport"] is False
    assert any("заглушка" in i for i in stub["issues"])
    assert any("viewport" in i for i in stub["issues"])


def test_lead_out_uses_site_audit_for_scoring():
    lead_obj = Lead(
        id="test-lead-1",
        name="Барбершоп Стрижка",
        category="Барбершоп",
        city="Москва",
        phone="+7 999 000-11-22",
        website_url="https://old-barber.ru",
        has_website=True,
        rating=4.7,
        reviews_count=35,
        site_audit={
            "is_alive": False,
            "status_code": 502,
            "issues": ["Сайт не открывается (код 502) — клиенты видят ошибку."],
        },
    )
    out = LeadOut.model_validate(lead_obj)
    assert out.website_status == "broken_website"
    assert out.lead_score >= 4.5
    assert "Сайт не открывается (код 502)" in out.growth_points[0]


@pytest.mark.asyncio
async def test_demo_view_tracking_and_weak_filter(client, lead):
    # Create a demo for the fixture lead
    async with SessionLocal() as session:
        demo = DemoSite(
            lead_id=lead.id,
            title=f"Демо {lead.name}",
            html="<html><body><h1>Hello</h1></body></html>",
            message="Hi",
            published=True,
        )
        session.add(demo)
        await session.commit()
        await session.refresh(demo)
        demo_id = demo.id

    # Preview request should NOT increment views_count
    r_preview = await client.get(f"/demo/{demo_id}?preview=1")
    assert r_preview.status_code == 200

    # Real user request (non-bot UA) SHOULD increment views_count
    r_real = await client.get(
        f"/demo/{demo_id}",
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"},
    )
    assert r_real.status_code == 200

    r_api = await client.get(f"/api/demos/{demo_id}")
    assert r_api.status_code == 200
    data = r_api.json()
    assert data["views_count"] == 1
    assert data["last_viewed_at"] is not None

    # Test only_weak_or_broken filter
    async with SessionLocal() as session:
        session.add(
            Lead(
                name="Taplink Studio",
                category="Бьюти",
                city="Москва",
                website_url="https://taplink.cc/studio",
                has_website=True,
                source="test",
                source_id="tap-1",
            )
        )
        session.add(
            Lead(
                name="Good Site LLC",
                category="Бьюти",
                city="Москва",
                website_url="https://goodsite.ru",
                has_website=True,
                source="test",
                source_id="good-1",
            )
        )
        await session.commit()

    resp = await client.get("/api/leads?only_weak_or_broken=true")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["items"]}
    assert "Taplink Studio" in names
    assert lead.name in names
    assert "Good Site LLC" not in names


def test_render_jinja_demo_fixes_title_rating_and_ruble():
    from app.services.landing import render_jinja_demo

    html_out = render_jinja_demo(
        template_id="cool_grey_concrete",
        business_dict={
            "name": "Тест Студия",
            "category": "Бьюти",
            "city": "Москва",
            "rating": 4.800000190734863,
            "reviews_count": 12,
        },
        content_json={
            "hero_title": "Заголовок",
            "hero_subtitle": "Подзаголовок",
            "usp_list": [{"title": "Факт", "desc": "Описание"}],
            "services": [
                {"name": "Услуга 1", "price": "от 2 000 ₽", "desc": "Описание"},
                {"name": "Услуга 2", "price": "по запросу", "desc": "Описание"},
                {"name": "Услуга 3", "price": "1 500", "desc": "Описание"},
            ],
            "faq": [],
        },
        hero_image="",
        gallery_photos=[],
    )
    assert "<title>Тест Студия — Бьюти в Москве</title>" in html_out
    assert "{ business.name }" not in html_out
    assert "4.800000" not in html_out
    assert "4.8" in html_out
    assert "₽ ₽" not in html_out
    assert "по запросу ₽" not in html_out
    assert "1 500 ₽" in html_out

