from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

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
    # Reviews are shown only when real Yandex Maps reviews were collected.
    assert 'id="reviews"' not in html_out
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


@pytest.mark.asyncio
async def test_outreach_peer_flood_parks_account_and_reuses_demo(monkeypatch):
    """PEER_FLOOD must park the account, keep the lead queued and not rebuild the demo."""
    from sqlalchemy import delete, func, select
    from telethon.errors import PeerFloodError

    from app.models import DemoSite, OutreachLead, TgAccount
    from app.config import settings
    from app.services.outreach_worker import outreach_worker

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        acc = TgAccount(
            phone="+79990000001",
            username="limited_acc",
            session_string="fake-session",
            status="active",
        )
        session.add(acc)
        session.add(
            OutreachLead(
                yandex_org_id="org_flood_1",
                company_name="Кофейня Флуд",
                category="Кофейня",
                city="Новороссийск",
                phone="+79180000123",
                status="queued",
            )
        )
        await session.commit()
        acc_id = acc.id

    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    monkeypatch.setattr(outreach_worker, "replenish_queue", _noop_replenish)
    settings.outreach_enabled = True
    outreach_worker._paused_until = None
    outreach_worker._userbot_account_id = acc_id
    outreach_worker._userbot_account_label = "@limited_acc"
    outreach_worker._userbot_uses_env_session = False
    outreach_worker._last_limit_alert.clear()
    outreach_worker._last_recovery_probe.clear()

    class FloodClient:
        async def send_message(self, peer, text, link_preview=False):
            raise PeerFloodError(None)

    async def fake_get_client():
        return FloodClient()

    async def fake_resolve(c, item):
        item.tg_user_id = 123456789
        item.tg_username = "coffee_owner"
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

    # @SpamBot confirms a real block -> account must be parked for a long time.
    async def verdict_limited(account_id):
        return "limited"

    monkeypatch.setattr(outreach_worker, "_spambot_verdict", verdict_limited)

    outcome = await outreach_worker.run_autonomous_step()
    assert outcome == "peer_flood"

    async with SessionLocal() as session:
        acc = await session.get(TgAccount, acc_id)
        assert acc is not None
        assert acc.status == "spamblock"
        assert acc.flood_until is not None

        lead = await session.scalar(
            select(OutreachLead).where(OutreachLead.yandex_org_id == "org_flood_1")
        )
        assert lead is not None
        assert lead.status == "queued"  # not lost, will be retried by a healthy account
        assert lead.demo_url
        demo_id = lead.demo_id
        demos_before = int(await session.scalar(select(func.count(DemoSite.id))) or 0)

    assert any("PEER_FLOOD" in text or "ограничил" in text for text in admin_alerts)

    # Second iteration: no healthy account left -> no processing, no duplicate demo.
    async def no_client():
        return None

    monkeypatch.setattr(outreach_worker, "_get_userbot_client", no_client)
    outreach_worker._paused_until = None
    outcome2 = await outreach_worker.run_autonomous_step()
    assert outcome2 == "no_client"

    async with SessionLocal() as session:
        lead = await session.scalar(
            select(OutreachLead).where(OutreachLead.yandex_org_id == "org_flood_1")
        )
        assert lead.demo_id == demo_id
        demos_after = int(await session.scalar(select(func.count(DemoSite.id))) or 0)
        assert demos_after == demos_before

    await outreach_worker.set_autonomous_enabled(False)
    outreach_worker._userbot_account_id = None
    outreach_worker._userbot_account_label = None


@pytest.mark.asyncio
async def test_outreach_peer_flood_temporary_when_spambot_clean(monkeypatch):
    """If @SpamBot says "clean", PEER_FLOOD is a temporary new-chat limit, not a block."""
    from datetime import timezone

    from sqlalchemy import delete, select
    from telethon.errors import PeerFloodError

    from app.config import settings
    from app.models import OutreachLead, TgAccount, utcnow
    from app.services.outreach_worker import outreach_worker
    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        acc = TgAccount(
            phone="+79990000004",
            username="clean_acc",
            session_string="fake-session",
            status="active",
        )
        session.add(acc)
        session.add(
            OutreachLead(
                yandex_org_id="org_flood_2",
                company_name="Кофейня Вторая",
                category="Кофейня",
                city="Краснодар",
                phone="+79180000456",
                status="queued",
            )
        )
        await session.commit()
        acc_id = acc.id

    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    monkeypatch.setattr(outreach_worker, "replenish_queue", _noop_replenish)
    settings.outreach_enabled = True
    outreach_worker._paused_until = None
    outreach_worker._userbot_account_id = acc_id
    outreach_worker._userbot_account_label = "@clean_acc"
    outreach_worker._userbot_uses_env_session = False
    outreach_worker._peer_flood_streak = 0
    outreach_worker._last_limit_alert.clear()
    outreach_worker._last_recovery_probe.clear()

    class FloodClient:
        async def send_message(self, peer, text, link_preview=False):
            raise PeerFloodError(None)

    async def fake_get_client():
        return FloodClient()

    async def fake_resolve(c, item):
        item.tg_user_id = 123456789
        item.tg_username = "coffee_owner2"
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

    async def verdict_clean(account_id):
        return "clean"

    monkeypatch.setattr(outreach_worker, "_get_userbot_client", fake_get_client)
    monkeypatch.setattr(outreach_worker, "resolve_outreach_contact", fake_resolve)
    monkeypatch.setattr("app.services.media_collector.collect_media", fake_collect)
    monkeypatch.setattr("app.services.landing.generate_landing_html", fake_landing)
    monkeypatch.setattr(outreach_worker, "generate_autonomous_pitch", fake_pitch)
    monkeypatch.setattr("app.services.lead_notifier.lead_notifier.send_admin_text", fake_admin_text)
    monkeypatch.setattr(outreach_worker, "_spambot_verdict", verdict_clean)

    outcome = await outreach_worker.run_autonomous_step()
    assert outcome == "peer_flood"

    async with SessionLocal() as session:
        acc = await session.get(TgAccount, acc_id)
        assert acc is not None
        # Not parked: the account is only cooling down after a new-chat flood.
        assert acc.status == "active"
        assert acc.flood_until is not None
        flood_until = acc.flood_until
        if flood_until.tzinfo is None:
            flood_until = flood_until.replace(tzinfo=timezone.utc)
        assert flood_until > utcnow()

        lead = await session.scalar(
            select(OutreachLead).where(OutreachLead.yandex_org_id == "org_flood_2")
        )
        assert lead is not None
        assert lead.status == "queued"

    # Temporary floods must not spam the admin with "PeerFloodError" DMs.
    assert admin_alerts == []
    assert "временно" in str(outreach_worker._last_error).lower()

    settings.outreach_enabled = False
    outreach_worker._userbot_account_id = None
    outreach_worker._userbot_account_label = None
    outreach_worker._paused_until = None


async def _noop_replenish(session) -> int:
    return 0


@pytest.mark.asyncio
async def test_requeue_peer_flood_error_leads():
    """Leads marked as `error` by older versions on PEER_FLOOD are retried again."""
    from sqlalchemy import delete, select

    from app.models import OutreachLead
    from app.services.outreach_worker import outreach_worker

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        session.add(
            OutreachLead(
                yandex_org_id="org_requeue_1",
                company_name="Старый Флуд",
                category="Кофейня",
                city="Краснодар",
                phone="+79180000789",
                status="error",
                error_detail="PeerFloodError: The account is limited (spam-reported)",
            )
        )
        await session.commit()

    count = await outreach_worker.requeue_peer_flood_leads()
    assert count == 1

    async with SessionLocal() as session:
        lead = await session.scalar(
            select(OutreachLead).where(OutreachLead.yandex_org_id == "org_requeue_1")
        )
        assert lead is not None
        assert lead.status == "queued"
        assert lead.error_detail is None
        await session.execute(delete(OutreachLead))
        await session.commit()


@pytest.mark.asyncio
async def test_monochrome_contrast_and_vision_photo_index_sorting(monkeypatch):
    from app.services.ai_router import sort_business_photos
    from app.services.landing import render_jinja_demo

    # 1. Monochrome Slate Studio has accent #F8FAFC (light) -> text on accent & promo button must be dark (#09090B)
    html_mono = render_jinja_demo(
        template_id="monochrome_slate_studio",
        business_dict={
            "name": "Студия Кадр",
            "category": "Фотостудии",
            "city": "Москва",
            "hero_product": ["https://example.com/work1.jpg"],
            "interior_photos": [],
        },
        content_json={
            "hero_title": "Фотостудия",
            "hero_subtitle": "Съёмки в центре",
            "services": [{"category": "Съёмка", "name": "Портрет", "price": "5 000 ₽"}],
            "promo": {"badge": "Акция", "title": "Скидка 10%", "desc": "На первую съёмку", "cta": "Забрать"},
        },
        hero_image="https://example.com/work1.jpg",
        gallery_photos=[],
    )
    assert "--accent-fg: #09090B;" in html_mono
    assert "background-color: #09090B; color: #FFFFFF;" in html_mono
    # A real business photo means the renderer must not fill empty sections with stock images.
    assert "/static/stock/" not in html_mono
    assert "images.unsplash.com" not in html_mono

    # 1b. Hair salon with rejected facade photo must use hair sub-niche stock without duplicates
    html_hair = render_jinja_demo(
        template_id="dark_cyber_neon",
        business_dict={
            "name": "Парикмахерская Dolce Vita",
            "category": "Парикмахерская",
            "city": "Сочи",
            "hero_product": [],
            "interior_photos": [],
            "rejected_photos": ["https://avatars.mds.yandex.net/get-altay/123/facade/orig"],
        },
        content_json={
            "hero_title": "Парикмахерская Dolce Vita",
            "hero_subtitle": "Стрижки и окрашивание",
            "services": [
                {"category": "Стрижки", "name": "Женская стрижка", "price": "1 200 ₽"},
                {"category": "Стрижки", "name": "Мужская стрижка", "price": "900 ₽"},
                {"category": "Окрашивание", "name": "Окрашивание корней", "price": "2 500 ₽"},
            ],
        },
        hero_image="https://avatars.mds.yandex.net/get-altay/123/facade/orig",
        gallery_photos=[],
        public_url="https://murasaki-leadradar-1.onrender.com/demo/dolce-vita-sochi",
    )
    assert "https://murasaki-leadradar-1.onrender.com/static/stock/hair/hero.jpg" in html_hair
    assert "https://murasaki-leadradar-1.onrender.com/static/stock/hair/works_1.jpg" in html_hair
    assert "https://murasaki-leadradar-1.onrender.com/static/stock/hair/interior_1.jpg" in html_hair
    assert "facade/orig" not in html_hair
    assert "images.unsplash.com" not in html_hair

    # 2. Index-based Vision sorting must discard trash completely AND bind exact photo captions
    async def fake_vision(**kwargs):
        return (
            '{"hero_product": [{"index": 1, "caption": "Нюдовый маникюр"}, '
            '{"index": 3, "caption": "Работа мастера"}], '
            '"interior": [0], "trash": [2, 4]}'
        )

    monkeypatch.setattr("app.services.ai_router.ask_ai_vision", fake_vision)
    sorted_res = await sort_business_photos(
        [
            "https://cdn.site/interior.jpg",
            "https://cdn.site/nails.jpg",
            "https://cdn.site/grandma_face.jpg",
            "https://cdn.site/portrait_unclear.jpg",
            "https://cdn.site/gloves.jpg",
        ],
        business_category="Бьюти",
        business_name="Салон",
    )
    assert sorted_res["hero_product"] == ["https://cdn.site/nails.jpg", "https://cdn.site/portrait_unclear.jpg"]
    assert sorted_res["work_captions"] == {
        "https://cdn.site/nails.jpg": "Нюдовый маникюр",
        "https://cdn.site/portrait_unclear.jpg": "Работа мастера",
    }
    assert sorted_res["interior"] == ["https://cdn.site/interior.jpg"]
    assert "https://cdn.site/grandma_face.jpg" not in sorted_res["hero_product"] + sorted_res["interior"]
    assert "https://cdn.site/gloves.jpg" not in sorted_res["hero_product"] + sorted_res["interior"]

    # 3. Carousel cards MUST bind strictly to Vision/stock photo captions, never random text services
    html_captions = render_jinja_demo(
        template_id="luxury_editorial",
        business_dict={
            "name": "Салон Образ",
            "category": "Парикмахерская",
            "city": "Москва",
            "hero_product": ["https://cdn.site/nails.jpg"],
            "work_captions": {"https://cdn.site/nails.jpg": "Нюдовый маникюр"},
            "interior_photos": [],
        },
        content_json={
            "hero_title": "Салон Образ",
            "hero_subtitle": "Мастерство и уход",
            "services": [{"category": "Волосы", "name": "Стрижка женская", "price": "2 000 ₽"}],
        },
        hero_image="https://cdn.site/nails.jpg",
        gallery_photos=[],
    )
    assert 'alt="Нюдовый маникюр"' in html_captions
    assert 'alt="Стрижка женская"' not in html_captions

    # 4. Auto style detection must avoid substring traps ('сто', 'дизайн', 'фото')
    from app.services.design_systems import detect_style_by_category
    assert detect_style_by_category("Стоматология") == "clean_swiss_trust"
    assert detect_style_by_category("Ресторан") == "warm_artisan_coffee"
    assert detect_style_by_category("Ногтевая студия · дизайн ногтей") == "luxury_editorial"
    assert detect_style_by_category("Фотоэпиляция и косметология") == "luxury_editorial"
    assert detect_style_by_category("Барбершоп") == "vintage_barber_leather"
    assert detect_style_by_category("СТО и шиномонтаж") == "dark_cyber_neon"


@pytest.mark.asyncio
async def test_channel_admin_extraction_and_outreach_filtering(monkeypatch):
    from bs4 import BeautifulSoup
    from telethon.tl.types import User
    from app.models import OutreachLead
    from app.services.outreach_worker import OutreachWorker
    from app.services.telegram_channel_scraper import _extract_admin_username

    # 1. Extract admin from bio, skipping self, emails, and bots
    bio_html = """
    <div class="tgme_channel_info_description">
      Канал @beauty_channel. Бот: @booking_bot. Почта: info@salon.ru.
      Запись к менеджеру: @anna_manager
    </div>
    """
    soup = BeautifulSoup(bio_html, "html.parser")
    assert _extract_admin_username(soup, "beauty_channel") == "anna_manager"

    # 2. Fallback to post links when bio has no personal handle
    post_html = """
    <div class="tgme_channel_info_description">Только новости @beauty_channel</div>
    <div class="tgme_widget_message_text">Запись через <a href="https://t.me/owner_kate">менеджера</a></div>
    """
    assert _extract_admin_username(BeautifulSoup(post_html, "html.parser"), "beauty_channel") == "owner_kate"

    # 3. Channel without personal admin returns None
    no_admin_html = """
    <div class="tgme_channel_info_description">Наш канал @beauty_channel и бот @salon_helper_bot</div>
    """
    assert _extract_admin_username(BeautifulSoup(no_admin_html, "html.parser"), "beauty_channel") is None

    # 4. resolve_outreach_contact redirects channel -> admin User without calling ImportContactsRequest
    class FakeChannel:
        id = 999

    class FakeClient:
        def __init__(self, entities):
            self.entities = entities
            self.called_requests = []

        async def get_entity(self, handle):
            return self.entities[handle]

        async def __call__(self, req):
            self.called_requests.append(req)
            raise AssertionError("ImportContactsRequest must not be called for channels")

    from telethon.tl.types import UserStatusRecently
    admin_user = User(id=777111, username="anna_manager", bot=False, status=UserStatusRecently())

    async def fake_scrape_with_admin(username, limit_photos=0):
        return {"avatar_url": None, "photos": [], "admin_username": "anna_manager"}

    monkeypatch.setattr("app.services.telegram_channel_scraper.scrape_telegram_channel", fake_scrape_with_admin)
    worker = OutreachWorker()

    lead_with_admin = OutreachLead(
        id=1,
        company_name="Studio",
        tg_username="beauty_channel",
        phone="+79991112233",
        message_text="hi",
    )
    client_ok = FakeClient({"beauty_channel": FakeChannel(), "anna_manager": admin_user})
    entity, temp_imported = await worker.resolve_outreach_contact(client_ok, lead_with_admin)
    assert entity is admin_user
    assert temp_imported is False
    assert lead_with_admin.tg_username == "anna_manager"
    assert lead_with_admin.tg_user_id == 777111
    assert client_ok.called_requests == []

    # 5. Channel without admin is filtered out immediately (no ImportContacts fallback)
    async def fake_scrape_no_admin(username, limit_photos=0):
        return {"avatar_url": None, "photos": [], "admin_username": None}

    monkeypatch.setattr("app.services.telegram_channel_scraper.scrape_telegram_channel", fake_scrape_no_admin)
    lead_no_admin = OutreachLead(
        id=2,
        company_name="ChannelOnly",
        tg_username="beauty_channel",
        phone="+79991112233",
        message_text="hi",
    )
    client_skip = FakeClient({"beauty_channel": FakeChannel()})
    entity2, temp2 = await worker.resolve_outreach_contact(client_skip, lead_no_admin)
    assert entity2 is None
    assert temp2 is False
    assert lead_no_admin.error_detail
    assert client_skip.called_requests == []







@pytest.mark.asyncio
async def test_outreach_account_daily_budget_and_reset():
    """Cold-DM budget is tracked separately per account and rolls over daily."""
    from datetime import timedelta

    from sqlalchemy import delete

    from app.config import settings
    from app.models import TgAccount, utcnow
    from app.services.account_pool import account_pool

    async with SessionLocal() as session:
        await session.execute(delete(TgAccount))
        full = TgAccount(
            phone="+79990000002",
            session_string="s1",
            status="active",
            daily_actions_count=1,
            daily_actions_reset_at=utcnow(),
            daily_outreach_count=int(settings.outreach_account_daily_limit),
            daily_outreach_reset_at=utcnow(),
        )
        fresh = TgAccount(
            phone="+79990000003",
            session_string="s2",
            status="active",
            daily_actions_count=1,
            daily_actions_reset_at=utcnow(),
        )
        session.add_all([full, fresh])
        await session.commit()
        full_id = full.id

        cap = int(settings.outreach_account_daily_limit)
        picked = await account_pool.get_available_account(session, max_daily_outreach=cap)
        assert picked is not None and picked.phone == "+79990000003"

        # Only the fully-used account remains -> nothing available for outreach.
        await session.delete(fresh)
        await session.commit()
        assert await account_pool.get_available_account(session, max_daily_outreach=cap) is None

        # A stale reset marker rolls the counter over and makes it available again.
        acc = await session.get(TgAccount, full_id)
        acc.daily_outreach_reset_at = utcnow() - timedelta(days=1)
        acc.daily_actions_reset_at = utcnow() - timedelta(days=1)
        await session.commit()
        picked2 = await account_pool.get_available_account(session, max_daily_outreach=cap)
        assert picked2 is not None
        assert picked2.id == full_id
        assert picked2.daily_outreach_count == 0

        # Expired floodwait should auto-recover to active cleanly
        acc.status = "floodwait"
        acc.flood_until = utcnow() - timedelta(minutes=5)
        await session.commit()
        picked3 = await account_pool.get_available_account(session, max_daily_outreach=cap)
        assert picked3 is not None
        assert picked3.id == full_id
        assert picked3.status == "active"
        assert picked3.flood_until is None

        await session.execute(delete(TgAccount))
        await session.commit()


@pytest.mark.asyncio
async def test_brand_color_extraction_pitch_and_activity_filter(monkeypatch):
    import io
    from datetime import timedelta
    from PIL import Image
    from telethon.tl.types import (
        User,
        UserStatusLastMonth,
        UserStatusOffline,
        UserStatusOnline,
        UserStatusRecently,
    )

    from app.models import OutreachLead, utcnow
    from app.services.brand_color import (
        extract_brand_color_from_bytes,
        fallback_brand_color,
        relative_luminance,
        resolve_lead_brand_color,
    )
    from app.services.landing import build_outreach, render_jinja_demo
    from app.services.outreach_worker import OutreachWorker

    # 1. Image with white background + vivid yellow accent -> ignores white & darkens for contrast
    img = Image.new("RGB", (80, 80), (255, 255, 255))
    for x in range(20, 60):
        for y in range(20, 60):
            img.putpixel((x, y), (250, 220, 40))  # bright yellow
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    extracted = extract_brand_color_from_bytes(buf.getvalue())
    assert extracted is not None
    assert extracted.startswith("#")
    assert relative_luminance(extracted) <= 0.28  # darkened cleanly for white button text

    # Monochrome grayscale image returns None -> niche fallback kicks in
    gray_img = Image.new("RGB", (60, 60), (140, 140, 140))
    gray_buf = io.BytesIO()
    gray_img.save(gray_buf, format="PNG")
    assert extract_brand_color_from_bytes(gray_buf.getvalue()) is None

    assert fallback_brand_color("Кофейня") == "#8B3A2B"
    assert fallback_brand_color("Автосервис") == "#D32F2F"
    assert fallback_brand_color("Салон красоты") == "#2E6F65"
    assert fallback_brand_color("Стоматология") == "#1976D2"
    assert fallback_brand_color("Консалтинг") == "#2563EB"

    # Telethon profile photo BytesIO resolution
    class FakeTgClient:
        async def download_profile_photo(self, entity, file=None):
            file.write(buf.getvalue())
            return file

    ext_col, final_col = await resolve_lead_brand_color(
        client=FakeTgClient(),
        peer_entity=object(),
        category="Кофейня",
    )
    assert ext_col == extracted
    assert final_col == extracted

    # 2. Landing template receives --brand-accent, --brand-accent-hover, --brand-accent-soft
    html_code = render_jinja_demo(
        template_id="clean_swiss_trust",
        business_dict={
            "name": "Кофе Ботаника",
            "category": "Кофейня",
            "city": "Краснодар",
            "brand_color": "#8B3A2B",
            "hero_product": [],
            "interior_photos": [],
        },
        content_json={
            "hero_title": "Кофе Ботаника",
            "hero_subtitle": "Свежая обжарка",
            "services": [{"category": "Кофе", "name": "Капучино", "price": "250 ₽"}],
        },
        hero_image="",
        gallery_photos=[],
    )
    assert "--brand-accent: #8B3A2B;" in html_code
    assert "--brand-accent-hover:" in html_code
    assert "--brand-accent-soft: rgba(139, 58, 43, 0.12);" in html_code

    # 3. Pitch & outreach messages: no 'портфоли' typo, URL on separate line without trailing dot/paren
    demo_url = "https://murasaki-leadradar-1.onrender.com/demo/kofe-botanika"
    msg = build_outreach(
        {"name": "Кофе Ботаника", "category": "Кофейня", "city": "Краснодар", "has_website": False},
        demo_url,
    )
    assert "в портфолио" in msg
    assert "в портфоли " not in msg and "в портфоли." not in msg
    assert "в ваших фирменных цветах" in msg
    assert f"\n{demo_url}\n" in msg
    assert f"{demo_url}." not in msg and f"{demo_url})" not in msg

    worker = OutreachWorker()
    item = OutreachLead(company_name="Кофе Ботаника", category="Кофейня", city="Краснодар")

    async def fake_ask_ai(*args, **kwargs):
        return f"Добрый день! Концепт в ваших фирменных цветах:\n{demo_url}.\nЕсли понравится — за 5 000 ₽ запустим и добавлю в портфолио. Актуально?"

    monkeypatch.setattr("app.services.outreach_worker.ask_ai", fake_ask_ai)
    pitch = await worker.generate_autonomous_pitch(item, demo_url)
    assert f"{demo_url}." not in pitch
    assert f"{demo_url}\n" in pitch
    assert "в портфолио" in pitch

    # 4. Activity filter: online / recently / <= 5d offline OK; > 5d offline & last_month skipped
    u_online = User(id=1, username="u_on", bot=False, status=UserStatusOnline(expires=utcnow() + timedelta(minutes=5)))
    u_recent = User(id=2, username="u_rec", bot=False, status=UserStatusRecently())
    u_off_ok = User(id=3, username="u_off3", bot=False, status=UserStatusOffline(was_online=utcnow() - timedelta(days=3)))
    u_off_old = User(id=4, username="u_off12", bot=False, status=UserStatusOffline(was_online=utcnow() - timedelta(days=12)))
    u_month = User(id=5, username="u_mon", bot=False, status=UserStatusLastMonth())

    assert worker.is_telegram_user_active(u_online)[0] is True
    assert worker.is_telegram_user_active(u_recent)[0] is True
    assert worker.is_telegram_user_active(u_off_ok)[0] is True
    assert worker.is_telegram_user_active(u_off_old)[0] is False
    assert worker.is_telegram_user_active(u_month)[0] is False

    class ActivityClient:
        async def get_entity(self, handle):
            return {"u_off12": u_off_old, "u_rec": u_recent}[handle]

    lead_inactive = OutreachLead(id="l1", company_name="Old", tg_username="u_off12")
    ent_dead, _ = await worker.resolve_outreach_contact(ActivityClient(), lead_inactive)
    assert ent_dead is None
    assert "Неактивный" in (lead_inactive.error_detail or "")

    lead_active = OutreachLead(id="l2", company_name="Fresh", tg_username="u_rec")
    ent_ok, _ = await worker.resolve_outreach_contact(ActivityClient(), lead_active)
    assert ent_ok is u_recent


@pytest.mark.asyncio
async def test_og_image_view_tracking_smart_followup_and_priority(monkeypatch):
    import io
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from httpx import ASGITransport, AsyncClient
    from PIL import Image
    from sqlalchemy import delete, select

    from app.config import settings
    from app.main import app
    from app.models import DemoSite, Lead, OutreachLead, TgAccount, utcnow
    from app.services.landing import render_jinja_demo
    from app.services.og_image import generate_demo_og_png
    from app.services.outreach_worker import outreach_worker
    from app.services.telegram_channel_scraper import classify_external_links

    # 1. Dynamic 1200x630 OG image + long Cyrillic title wrapping + /demo/{slug}/og.png + view tracking
    png_bytes = generate_demo_og_png(
        business_name="Семейная Студия Красоты и Косметологии Империя Стиля",
        city="Новороссийск",
        brand_color="#8B3A2B",
    )
    with Image.open(io.BytesIO(png_bytes)) as im:
        assert im.size == (1200, 630)
        assert im.format == "PNG"

    html_og = render_jinja_demo(
        template_id="clean_swiss_trust",
        business_dict={"name": "Кофе Ботаника", "category": "Кофейня", "city": "Сочи", "brand_color": "#8B3A2B"},
        content_json={"hero_title": "Кофе Ботаника", "hero_subtitle": "Свежий кофе", "services": []},
        hero_image="",
        gallery_photos=[],
        public_url="https://murasaki-leadradar-1.onrender.com/demo/kofe-botanika",
    )
    assert '<meta property="og:image" content="https://murasaki-leadradar-1.onrender.com/demo/kofe-botanika/og.png">' in html_og
    assert '<meta property="og:title"' in html_og
    assert '<meta property="og:description"' in html_og
    assert '<meta name="twitter:card" content="summary_large_image">' in html_og

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(DemoSite))
        await session.execute(delete(Lead))
        lead = Lead(name="Кофейня Луна", category="Кофейня", city="Сочи", has_website=False)
        session.add(lead)
        await session.flush()
        demo = DemoSite(
            lead_id=lead.id,
            slug="kofejnya-luna-sochi",
            title="Демо для Кофейня Луна",
            html="<html><body>Demo</body></html>",
            published=True,
            brand_color="#8B3A2B",
        )
        session.add(demo)
        await session.flush()
        ol_view = OutreachLead(
            yandex_org_id="org_og_view",
            company_name="Кофейня Луна",
            category="Кофейня",
            city="Сочи",
            tg_username="luna_coffee",
            demo_id=demo.id,
            status="sent",
            sent_at=utcnow() - timedelta(hours=30),
        )
        session.add(ol_view)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_og = await client.get("/demo/kofejnya-luna-sochi/og.png")
        assert r_og.status_code == 200
        assert r_og.headers["content-type"] == "image/png"
        with Image.open(io.BytesIO(r_og.content)) as im2:
            assert im2.size == (1200, 630)

        # Real visitor (Chrome UA) sets is_opened=True & opened_at
        r_visit = await client.get(
            "/demo/kofejnya-luna-sochi",
            headers={"User-Agent": "Mozilla/5.0 Chrome/131.0"},
        )
        assert r_visit.status_code == 200

    async with SessionLocal() as session:
        refreshed = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "org_og_view"))
        assert refreshed is not None
        assert refreshed.is_opened is True
        assert refreshed.opened_at is not None

    # 2. Priority classification from TG profile / links
    assert classify_external_links(text_chunks=["Запись: https://taplink.cc/salon_rose и https://vk.com/rose"])["priority"] == "high"
    assert classify_external_links(text_chunks=["Мы на картах https://yandex.ru/maps/org/123 и https://2gis.ru/sochi"])["priority"] == "high"
    assert classify_external_links(text_chunks=["Наш сайт: https://imperial-clinic.ru/services"])["priority"] == "low"

    # 3. Queue selects high priority BEFORE older low priority
    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        session.add_all([
            OutreachLead(
                yandex_org_id="org_low",
                company_name="Клиника с сайтом",
                category="Клиника",
                city="Сочи",
                tg_username="low_prio",
                priority="low",
                status="queued",
                created_at=utcnow() - timedelta(hours=2),
            ),
            OutreachLead(
                yandex_org_id="org_high",
                company_name="Кофейня без сайта",
                category="Кофейня",
                city="Сочи",
                tg_username="high_prio",
                priority="high",
                status="queued",
                created_at=utcnow(),
            ),
        ])
        await session.commit()

    picked_names = []
    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    monkeypatch.setattr(outreach_worker, "replenish_queue", AsyncMock(return_value=0))
    settings.outreach_enabled = True
    outreach_worker._paused_until = None

    class QueueCheckClient:
        async def send_message(self, peer, text, link_preview=False):
            return SimpleNamespace(id=1)

    async def fake_resolve_q(c, item):
        picked_names.append(item.company_name)
        return None, False

    monkeypatch.setattr(outreach_worker, "_get_userbot_client", AsyncMock(return_value=QueueCheckClient()))
    monkeypatch.setattr(outreach_worker, "resolve_outreach_contact", fake_resolve_q)
    await outreach_worker.run_autonomous_step()
    assert picked_names == ["Кофейня без сайта"]

    # 4. Smart two-step follow-up: Scenario A (opened >=24h), Scenario B (unopened >=72h), replied guard, daily cap 12
    sent_followups = []

    class FollowupClient:
        def __init__(self, incoming_handles):
            self.incoming_handles = incoming_handles

        async def get_entity(self, ref):
            return SimpleNamespace(id=ref, username=str(ref))

        async def get_messages(self, peer, limit=5):
            if peer.username in self.incoming_handles:
                return [SimpleNamespace(out=False, date=utcnow())]
            return [SimpleNamespace(out=True, date=utcnow() - timedelta(hours=40))]

        async def send_message(self, peer, text, link_preview=False):
            sent_followups.append((peer.username, text))
            return SimpleNamespace(id=77)

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        session.add_all([
            OutreachLead(
                yandex_org_id="fu_a",
                company_name="Барбер Альфа",
                tg_username="alpha_user",
                status="sent",
                is_opened=True,
                opened_at=utcnow() - timedelta(hours=26),
                sent_at=utcnow() - timedelta(hours=30),
                followup_step=0,
            ),
            OutreachLead(
                yandex_org_id="fu_b",
                company_name="Студия Бета",
                tg_username="beta_user",
                status="sent",
                is_opened=False,
                sent_at=utcnow() - timedelta(hours=75),
                followup_step=0,
            ),
            OutreachLead(
                yandex_org_id="fu_replied",
                company_name="Салон Гамма",
                tg_username="gamma_user",
                status="sent",
                is_opened=True,
                opened_at=utcnow() - timedelta(hours=30),
                sent_at=utcnow() - timedelta(hours=32),
                followup_step=0,
            ),
            OutreachLead(
                yandex_org_id="fu_ignored",
                company_name="Детейлинг Дельта",
                tg_username="delta_user",
                status="followed_up",
                last_followup_at=utcnow() - timedelta(days=8),
                has_reply=False,
            ),
        ])
        await session.commit()

    fu_client = FollowupClient(incoming_handles={"gamma_user"})
    monkeypatch.setattr(outreach_worker, "_get_userbot_client", AsyncMock(return_value=fu_client))
    count_fu = await outreach_worker.process_outreach_followups(max_sends=5, delay_range=(0.0, 0.0))
    assert count_fu == 2

    sent_map = dict(sent_followups)
    assert "заглянули на демо-концепт" in sent_map["alpha_user"]
    assert "освобождаю поддомен" in sent_map["beta_user"]
    assert "gamma_user" not in sent_map

    async with SessionLocal() as session:
        a_row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "fu_a"))
        b_row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "fu_b"))
        g_row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "fu_replied"))
        d_row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "fu_ignored"))
        assert a_row.status == "followed_up" and a_row.followup_step == 1
        assert b_row.status == "followed_up" and b_row.followup_step == 1
        assert g_row.status == "replied" and g_row.has_reply is True
        assert d_row.status == "ignored"

        # 5. Shared daily limit (15/day total across sent + followups) blocks further sends
        for idx in range(int(settings.outreach_daily_limit) - 2):
            session.add(
                OutreachLead(
                    yandex_org_id=f"cap_{idx}",
                    company_name=f"Biz {idx}",
                    status="sent",
                    sent_at=utcnow(),
                )
            )
        session.add(
            OutreachLead(
                yandex_org_id="cap_pending_fu",
                company_name="Pending Followup",
                tg_username="pending_u",
                status="sent",
                is_opened=True,
                opened_at=utcnow() - timedelta(hours=30),
                sent_at=utcnow() - timedelta(hours=35),
                followup_step=0,
            )
        )
        await session.commit()

    assert await outreach_worker.process_outreach_followups(max_sends=5, delay_range=(0.0, 0.0)) == 0

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(DemoSite))
        await session.execute(delete(Lead))
        await session.commit()
    await outreach_worker.set_autonomous_enabled(False)


@pytest.mark.asyncio
async def test_outreach_queue_rotation_uses_next_attempt_at_and_caps_retries(monkeypatch):
    """PEER_FLOOD rotates via next_attempt_at (preserving created_at) and stops after max_attempts."""
    from datetime import timedelta, timezone
    from sqlalchemy import delete, select
    from telethon.errors import PeerFloodError

    from app.config import settings
    from app.models import DemoSite, OutreachLead, TgAccount, utcnow
    from app.services.account_pool import account_pool
    from app.services.outreach_worker import outreach_worker

    orig_t1 = utcnow() - timedelta(hours=3)
    orig_t2 = utcnow() - timedelta(hours=2)

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        acc1 = TgAccount(phone="+79990000101", username="rot_acc1", session_string="fake-1", status="active")
        acc2 = TgAccount(phone="+79990000102", username="rot_acc2", session_string="fake-2", status="active")
        l1 = OutreachLead(
            yandex_org_id="rot_1",
            company_name="Кафе Первое",
            category="Кофейня",
            city="Москва",
            tg_username="cafe_first",
            status="queued",
            created_at=orig_t1,
        )
        l2 = OutreachLead(
            yandex_org_id="rot_2",
            company_name="Кафе Второе",
            category="Кофейня",
            city="Москва",
            tg_username="cafe_second",
            status="queued",
            created_at=orig_t2,
        )
        session.add_all([acc1, acc2, l1, l2])
        await session.commit()
        acc1_id = acc1.id

    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    monkeypatch.setattr(outreach_worker, "replenish_queue", _noop_replenish)
    monkeypatch.setattr(outreach_worker, "_spambot_verdict", AsyncMock(return_value="clean"))
    monkeypatch.setattr("app.services.media_collector.collect_media", AsyncMock(return_value={"photos": ["https://example.com/p1.jpg"], "logo_url": None}))
    monkeypatch.setattr("app.services.landing.generate_landing_html", AsyncMock(return_value=("<html></html>", "mock")))
    monkeypatch.setattr(outreach_worker, "generate_autonomous_pitch", AsyncMock(return_value="Hi!"))
    monkeypatch.setattr("app.services.lead_notifier.lead_notifier.send_admin_text", AsyncMock(return_value=1))
    monkeypatch.setattr(outreach_worker, "resolve_outreach_contact", AsyncMock(return_value=(object(), False)))

    sent_targets: list[str] = []

    class SwitchClient:
        def __init__(self, fail: bool):
            self.fail = fail

        async def send_message(self, peer, text, link_preview=False):
            if self.fail:
                raise PeerFloodError(None)
            sent_targets.append("ok")
            return SimpleNamespace(id=1)

    settings.outreach_enabled = True
    outreach_worker._paused_until = None
    outreach_worker._userbot_account_id = acc1_id
    outreach_worker._userbot_account_label = "@rot_acc1"
    outreach_worker._userbot_uses_env_session = False

    monkeypatch.setattr(outreach_worker, "_get_userbot_client", AsyncMock(return_value=SwitchClient(fail=True)))
    assert await outreach_worker.run_autonomous_step() == "peer_flood"

    async with SessionLocal() as session:
        row1 = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "rot_1"))
        assert row1 is not None
        assert row1.status == "queued"
        assert row1.attempt_count == 1
        assert row1.next_attempt_at is not None
        saved_created = row1.created_at.replace(tzinfo=timezone.utc) if row1.created_at.tzinfo is None else row1.created_at
        assert abs((saved_created - orig_t1).total_seconds()) < 2

    # Next step runs on acc2 while rot_1 is deferred: rot_2 must be selected next!
    outreach_worker._paused_until = None
    monkeypatch.setattr(outreach_worker, "_get_userbot_client", AsyncMock(return_value=SwitchClient(fail=False)))
    assert await outreach_worker.run_autonomous_step() == "sent"
    assert sent_targets == ["ok"]

    async with SessionLocal() as session:
        row2 = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "rot_2"))
        assert row2 is not None and row2.status == "sent"
        # Push rot_1 to max_attempts - 1 and reset next_attempt_at -> next PeerFloodError marks it `error`
        row1 = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "rot_1"))
        row1.attempt_count = int(settings.outreach_lead_max_attempts) - 1
        row1.next_attempt_at = utcnow() - timedelta(minutes=1)
        session.add(row1)
        await session.commit()

    monkeypatch.setattr(outreach_worker, "_get_userbot_client", AsyncMock(return_value=SwitchClient(fail=True)))
    assert await outreach_worker.run_autonomous_step() == "peer_flood"

    async with SessionLocal() as session:
        row1 = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "rot_1"))
        assert row1 is not None and row1.status == "error"
        assert row1.next_attempt_at is None
        await session.execute(delete(OutreachLead))
        await session.execute(delete(DemoSite))
        await session.execute(delete(TgAccount))
        await session.commit()
    await outreach_worker.set_autonomous_enabled(False)


@pytest.mark.asyncio
async def test_outreach_cooldown_resume_and_single_budget_charge(monkeypatch):
    """Failed temp-import send must not burn daily_outreach_count, and step resumes cleanly after cooldown."""
    from datetime import timedelta
    from sqlalchemy import delete, select
    from telethon.errors import PeerFloodError

    from app.config import settings
    from app.models import DemoSite, OutreachLead, TgAccount, utcnow
    from app.services.account_pool import account_pool
    from app.services.outreach_worker import outreach_worker

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        acc = TgAccount(
            phone="+79990000103",
            username="resume_acc",
            session_string="valid-session-string",
            status="active",
        )
        lead = OutreachLead(
            yandex_org_id="resume_1",
            company_name="Студия Возобновления",
            category="Бьюти",
            city="Казань",
            phone="+79170001122",
            status="queued",
        )
        session.add_all([acc, lead])
        await session.commit()
        acc_id = acc.id

    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    monkeypatch.setattr(outreach_worker, "replenish_queue", _noop_replenish)
    monkeypatch.setattr(outreach_worker, "_spambot_verdict", AsyncMock(return_value="clean"))
    monkeypatch.setattr(outreach_worker, "_try_recover_accounts", AsyncMock(return_value=False))
    monkeypatch.setattr("app.services.media_collector.collect_media", AsyncMock(return_value={"photos": ["https://example.com/p1.jpg"], "logo_url": None}))
    monkeypatch.setattr("app.services.landing.generate_landing_html", AsyncMock(return_value=("<html></html>", "mock")))
    monkeypatch.setattr(outreach_worker, "generate_autonomous_pitch", AsyncMock(return_value="Hi!"))
    monkeypatch.setattr("app.services.lead_notifier.lead_notifier.send_admin_text", AsyncMock(return_value=1))
    monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))

    async def resolve_temp(client, item):
        item.tg_user_id = 987654321
        return SimpleNamespace(id=987654321), True

    monkeypatch.setattr(outreach_worker, "resolve_outreach_contact", resolve_temp)

    class TempClient:
        def __init__(self, fail: bool):
            self.fail = fail

        def is_connected(self):
            return True

        async def connect(self):
            return None

        async def is_user_authorized(self):
            return True

        def on(self, event):
            return lambda fn: fn

        async def send_message(self, peer, text, link_preview=False):
            if self.fail:
                raise PeerFloodError(None)
            return SimpleNamespace(id=9)

        async def __call__(self, req):
            return None

    settings.outreach_enabled = True
    monkeypatch.setattr(settings, "outreach_session_string", None)
    outreach_worker._paused_until = None
    outreach_worker._userbot_account_id = acc_id
    outreach_worker._userbot_account_label = "@resume_acc"
    outreach_worker._userbot_uses_env_session = False

    monkeypatch.setattr(account_pool, "get_client_for_account", AsyncMock(return_value=TempClient(fail=True)))
    assert await outreach_worker.run_autonomous_step() == "peer_flood"

    # Failed send incremented daily_actions_count (ImportContacts=1), NOT daily_outreach_count (still 0!)
    async with SessionLocal() as session:
        acc_row = await session.get(TgAccount, acc_id)
        assert acc_row.daily_actions_count == 1
        assert acc_row.daily_outreach_count == 0
        assert acc_row.flood_until is not None

    # During cooldown: step returns paused, status still shows saved session + flood_until
    assert await outreach_worker.run_autonomous_step() == "paused"
    st = await outreach_worker.get_autonomous_status()
    assert st["session_configured"] is True
    assert st["account_status"] == "active"
    assert st["account_flood_until"] is not None
    assert st["available_accounts"] == 0

    # Expire flood_until while _paused_until is still set -> auto-sync wakes up and succeeds!
    async with SessionLocal() as session:
        acc_row = await session.get(TgAccount, acc_id)
        acc_row.flood_until = utcnow() - timedelta(minutes=1)
        lead_row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "resume_1"))
        lead_row.next_attempt_at = utcnow() - timedelta(minutes=1)
        session.add_all([acc_row, lead_row])
        await session.commit()

    monkeypatch.setattr(account_pool, "get_client_for_account", AsyncMock(return_value=TempClient(fail=False)))
    assert await outreach_worker.run_autonomous_step() == "sent"

    async with SessionLocal() as session:
        acc_row = await session.get(TgAccount, acc_id)
        lead_row = await session.scalar(select(OutreachLead).where(OutreachLead.yandex_org_id == "resume_1"))
        assert acc_row.daily_outreach_count == 1  # charged ONCE on send success, NOT twice!
        assert lead_row.status == "sent"
        assert lead_row.error_detail is None  # stale PeerFlood error cleared!
        await session.execute(delete(OutreachLead))
        await session.execute(delete(DemoSite))
        await session.execute(delete(TgAccount))
        await session.commit()
    await outreach_worker.set_autonomous_enabled(False)


@pytest.mark.asyncio
async def test_outreach_no_client_status_logs_and_db_error(client, monkeypatch):
    """Checks session_configured with parked accounts, /api/logs?module=outreach, and DB exception handling."""
    from sqlalchemy import delete

    from app.config import settings
    from app.models import OutreachLead, SystemLog, TgAccount
    from app.services.outreach_worker import outreach_worker

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        await session.execute(delete(SystemLog))
        acc = TgAccount(phone="+79990000104", username="parked_only", session_string="saved-sess", status="spamblock")
        lead = OutreachLead(
            yandex_org_id="no_client_1",
            company_name="Ателье Тест",
            category="Ателье",
            city="Москва",
            tg_username="atelier_test",
            status="queued",
        )
        log_row = SystemLog(level="INFO", module="outreach_worker", message="Отправлен оффер: Тест", details={"ok": True})
        session.add_all([acc, lead, log_row])
        await session.commit()

    # /api/logs?module=outreach must return outreach_worker entries
    resp = await client.get("/api/logs?module=outreach&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1 and data[0]["module"] == "outreach_worker"

    settings.outreach_enabled = True
    monkeypatch.setattr(settings, "outreach_session_string", None)
    outreach_worker._paused_until = None
    outreach_worker._userbot_account_id = None
    outreach_worker._last_error = None
    monkeypatch.setattr(outreach_worker, "is_in_work_window", lambda now=None: True)
    monkeypatch.setattr(outreach_worker, "replenish_queue", _noop_replenish)
    monkeypatch.setattr(outreach_worker, "_probe_limited_account", AsyncMock(return_value=None))

    assert await outreach_worker.run_autonomous_step() == "no_client"
    assert "spamblock" in str(outreach_worker._last_error).lower()

    st = await outreach_worker.get_autonomous_status()
    assert st["session_configured"] is True
    assert st["available_accounts"] == 0
    assert st["account_status"] == "spamblock"

    # Simulated DB exception during queue selection returns "error" cleanly with diagnostic _last_error
    async def broken_replenish(session):
        raise RuntimeError("simulated supabase timeout")

    monkeypatch.setattr(outreach_worker, "replenish_queue", broken_replenish)
    assert await outreach_worker.run_autonomous_step() == "error"
    assert "simulated supabase timeout" in str(outreach_worker._last_error)

    async with SessionLocal() as session:
        await session.execute(delete(OutreachLead))
        await session.execute(delete(TgAccount))
        await session.execute(delete(SystemLog))
        await session.commit()
    await outreach_worker.set_autonomous_enabled(False)


@pytest.mark.asyncio
async def test_warmup_skips_busy_account_and_transient_error(monkeypatch):
    """Warmup skips accounts held by outreach and does not falsely park on transient errors."""
    from sqlalchemy import delete

    from app.models import TgAccount
    from app.services.account_pool import account_pool
    from app.services.warmup_worker import warmup_worker

    async with SessionLocal() as session:
        await session.execute(delete(TgAccount))
        acc = TgAccount(
            phone="+79990000105",
            username="warmup_test",
            session_string="sess-w",
            status="active",
            auto_warmup=True,
            warmup_preset="active",
        )
        session.add(acc)
        await session.commit()
        acc_id = acc.id

    warmup_worker._last_session_time.clear()
    warmup_worker._last_billing_day.clear()

    warmup_calls = []

    async def fake_run(session, account):
        warmup_calls.append(account.id)

    original_run = warmup_worker._run_warmup_session
    monkeypatch.setattr(warmup_worker, "_run_warmup_session", fake_run)

    # While outreach holds the lock, warmup_worker.tick() must skip this account completely
    async with account_pool.acquire_account(acc_id, owner="outreach"):
        assert account_pool.is_account_busy(acc_id) is True
        await warmup_worker.tick()
        assert warmup_calls == []

    # Transient non-Telegram exception during real warmup must NOT flip status to floodwait
    monkeypatch.setattr(warmup_worker, "_run_warmup_session", original_run)

    class BrokenWarmupClient:
        async def connect(self):
            return None

        async def is_user_authorized(self):
            return True

        async def get_entity(self, ch):
            raise RuntimeError("transient connection reset")

    monkeypatch.setattr(account_pool, "get_client_for_account", AsyncMock(return_value=BrokenWarmupClient()))
    async with SessionLocal() as session:
        acc_row = await session.get(TgAccount, acc_id)
        await warmup_worker._run_warmup_session(session, acc_row)

    async with SessionLocal() as session:
        acc_row = await session.get(TgAccount, acc_id)
        assert acc_row.status == "active"
        assert acc_row.flood_until is None
        await session.execute(delete(TgAccount))
        await session.commit()
