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


@pytest.mark.asyncio
async def test_autonomous_outreach_pipeline_dedup_limits_and_toggle(client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.config import settings
    from app.models import OutreachLead
    from app.providers.base import PlaceResult
    from app.services.outreach_worker import MSK_TZ, normalize_ru_phone, outreach_worker

    assert normalize_ru_phone("8 (918) 123-45-67") == "+79181234567"
    assert normalize_ru_phone("9181234567") == "+79181234567"

    # Work window check (11:00 - 18:00 MSK)
    assert outreach_worker.is_in_work_window(datetime(2026, 11, 26, 11, 30, tzinfo=MSK_TZ)) is True
    assert outreach_worker.is_in_work_window(datetime(2026, 11, 26, 18, 0, tzinfo=MSK_TZ)) is False
    assert outreach_worker.is_in_work_window(datetime(2026, 11, 26, 9, 0, tzinfo=MSK_TZ)) is False

    # Toggle API
    r_tog = await client.post("/api/outreach/toggle", json={"enabled": True})
    assert r_tog.status_code == 200
    assert r_tog.json()["enabled"] is True

    r_st = await client.get("/api/outreach/status")
    assert r_st.status_code == 200
    assert r_st.json()["autonomous"]["enabled"] is True

    # Replenish queue deduplication (skip with website + skip duplicate phone/org_id)
    async def fake_yandex_search(self, **kwargs):
        return [
            PlaceResult(
                name="Есть Сайт",
                category="Бьюти",
                city="Новороссийск",
                phone="+7 918 111-11-11",
                website_url="https://has-site.ru",
                source="yandex_web",
                source_id="org_has_site",
            ),
            PlaceResult(
                name="Салон Без Сайта",
                category="Бьюти",
                city="Новороссийск",
                phone="8 (918) 222-33-44",
                website_url=None,
                photos=["https://example.com/p1.jpg"],
                source="yandex_web",
                source_id="org_clean_1",
            ),
            PlaceResult(
                name="Дубль Телефона",
                category="Бьюти",
                city="Новороссийск",
                phone="+7 918 222-33-44",
                website_url=None,
                source="yandex_web",
                source_id="org_dup_phone",
            ),
        ]

    monkeypatch.setattr("app.providers.yandex_web.YandexMapsWebProvider.search", fake_yandex_search)

    async with SessionLocal() as session:
        added = await outreach_worker.replenish_queue(session)
        assert added == 1

    # Mock work window, client, resolve, media, pitch, notifier for full step run
    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    settings.outreach_enabled = True

    class FakeClient:
        async def send_message(self, peer, text, link_preview=False):
            return {"peer": peer, "text": text}

    async def fake_get_client():
        return FakeClient()

    async def fake_resolve(c, item):
        item.tg_user_id = 123456789
        item.tg_username = "salon_owner"
        return object()

    async def fake_collect(lead_dict, max_items=10):
        return {"photos": ["https://example.com/p1.jpg"], "logo_url": None}

    async def fake_landing(lead, style_id=None, public_url=""):
        return f"<!DOCTYPE html><html><head><title>{lead['name']}</title></head><body>{public_url}</body></html>", "mock"

    async def fake_pitch(item, demo_url):
        return f"Привет, {item.company_name}! Демо: {demo_url} (5 000 ₽)"

    admin_alerts = []

    async def fake_admin_text(text, reply_markup=None):
        admin_alerts.append(text)
        return 1

    monkeypatch.setattr(outreach_worker, "_get_userbot_client", fake_get_client)
    monkeypatch.setattr(outreach_worker, "resolve_outreach_contact", fake_resolve)
    monkeypatch.setattr("app.services.media_collector.collect_media", fake_collect)
    monkeypatch.setattr("app.services.landing.generate_landing_html", fake_landing)
    monkeypatch.setattr(outreach_worker, "generate_autonomous_pitch", fake_pitch)
    monkeypatch.setattr("app.services.lead_notifier.lead_notifier.send_admin_text", fake_admin_text)

    outcome = await outreach_worker.run_autonomous_step()
    assert outcome == "sent"
    assert len(admin_alerts) == 1
    assert "Салон Без Сайта" in admin_alerts[0]

    # Verify DB state
    async with SessionLocal() as session:
        from sqlalchemy import select
        row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "org_clean_1"))
        assert row is not None
        assert row.status == "sent"
        assert row.demo_url is not None
        assert row.sent_at is not None

        # Check skipped_no_tg when resolve returns None
        no_tg_item = OutreachLead(
            yandex_org_id="org_no_tg",
            company_name="Без Телеграма",
            category="Бьюти",
            city="Новороссийск",
            phone="+79180000001",
            status="queued",
        )
        session.add(no_tg_item)
        await session.commit()

    async def fake_resolve_none(c, item):
        return None

    monkeypatch.setattr(outreach_worker, "resolve_outreach_contact", fake_resolve_none)
    assert await outreach_worker.run_autonomous_step() == "skipped_no_tg"

    # Turn off back so other tests are unaffected
    await outreach_worker.set_autonomous_enabled(False)



