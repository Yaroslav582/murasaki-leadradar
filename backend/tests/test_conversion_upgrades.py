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

    # SEO / OpenGraph / JSON-LD LocalBusiness
    assert 'property="og:title"' in html_out
    assert 'property="og:description"' in html_out
    assert '"@type": "LocalBusiness"' in html_out

    # 9-section interactive blocks
    assert 'id="works"' in html_out
    assert 'id="services"' in html_out
    assert 'id="reviews"' in html_out
    assert 'id="contacts"' in html_out
    assert 'id="booking-modal"' in html_out
    assert "IntersectionObserver" in html_out


@pytest.mark.asyncio
async def test_slug_routing_refine_and_direct_url_parse(client, lead, monkeypatch):
    from app.services.demos import generate_unique_slug, transliterate_slug

    assert transliterate_slug("Монреаль", "Краснодар") == "monreal-krasnodar"

    async with SessionLocal() as session:
        s1 = await generate_unique_slug(session, "Монреаль", "Краснодар")
        demo = DemoSite(
            lead_id=lead.id,
            slug=s1,
            title="Демо Монреаль",
            html="<!DOCTYPE html><html><head><title>Монреаль</title></head><body><h1>Старый заголовок</h1></body></html>",
            message="hi",
            published=True,
        )
        session.add(demo)
        await session.commit()
        await session.refresh(demo)
        demo_id = demo.id
        demo_slug = demo.slug

        # Collision check produces -2 suffix
        s2 = await generate_unique_slug(session, "Монреаль", "Краснодар")
        assert s2 == f"{s1}-2"

    # Both UUID and slug resolve /demo/{identifier}
    r_uuid = await client.get(f"/demo/{demo_id}?preview=1")
    r_slug = await client.get(f"/demo/{demo_slug}?preview=1")
    assert r_uuid.status_code == 200
    assert r_slug.status_code == 200

    # Test /api/demo/{id}/refine endpoint
    async def fake_refine(current_html: str, user_instruction: str, style_id=None, category=None) -> str:
        return current_html.replace("Старый заголовок", f"Обновлено: {user_instruction}")

    monkeypatch.setattr("app.services.ai_router.refine_demo_html", fake_refine)
    r_ref = await client.post(f"/api/demo/{demo_slug}/refine", json={"prompt": "Акция 20%"})
    assert r_ref.status_code == 200
    assert "Обновлено: Акция 20%" in r_ref.json()["html"]
    assert r_ref.json()["slug"] == demo_slug

    # Test direct org URL parsing endpoint
    from app.providers.base import PlaceResult
    from app.providers.direct_url import is_direct_org_url

    assert is_direct_org_url("https://yandex.ru/maps/org/monreal/123456/") is True
    assert is_direct_org_url("https://2gis.ru/krasnodar/firm/70000001012345") is True
    assert is_direct_org_url("стоматология москва") is False

    async def fake_parse_direct(url: str, fallback_city: str = "") -> PlaceResult:
        return PlaceResult(
            name="Бомонд",
            category="Бьюти",
            city="Новороссийск",
            address="Новороссийск, ул. Советов, 12",
            phone="+7 918 000-11-22",
            source="yandex_web",
            source_id="998877",
        )

    monkeypatch.setattr("app.providers.direct_url.parse_direct_org_url", fake_parse_direct)
    r_parse = await client.post(
        "/api/parse/url",
        json={"url": "https://yandex.ru/maps/org/bomond/998877/", "create_demo": False},
    )
    assert r_parse.status_code == 200
    assert r_parse.json()["lead"]["name"] == "Бомонд"
    assert r_parse.json()["lead"]["city"] == "Новороссийск"


