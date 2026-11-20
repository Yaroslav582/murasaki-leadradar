from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db import SessionLocal, init_db
from app.models import Lead
from app.schemas import LeadOut


@pytest.mark.asyncio
async def test_leadout_schema_coerces_none_and_legacy_values():
    """LeadOut schema must never fail with ValidationError on legacy rows with None or empty fields."""
    legacy_data = {
        "id": "leg-001",
        "name": "Старый автосервис",
        "category": "Автосервис",
        "city": "Москва",
        "address": "ул. Ленина, 1",
        "phone": "+7 999 000-00-00",
        "website_url": None,
        "has_website": None,
        "rating": None,
        "reviews_count": None,
        "social_links": None,
        "emails": None,
        "opening_hours": None,
        "photos": None,
        "logo_url": None,
        "demo_id": "demo-uuid-456",
        "demo_url": None,
        "status": None,
        "source": None,
        "created_at": None,
        "updated_at": None,
    }

    lead_out = LeadOut.model_validate(legacy_data)
    assert lead_out.photos == []
    assert lead_out.logo_url is None
    assert lead_out.social_links == {}
    assert lead_out.emails == []
    assert lead_out.opening_hours == []
    assert lead_out.has_website is False
    assert lead_out.reviews_count == 0
    assert lead_out.status == "new"
    assert lead_out.status_label == "Новый"
    assert lead_out.demo_url is not None
    assert "/demo/demo-uuid-456" in lead_out.demo_url


@pytest.mark.asyncio
async def test_get_leads_api_with_legacy_null_columns(client: AsyncClient):
    """GET /api/leads must succeed with HTTP 200 when DB rows have photos=None and logo_url=None."""
    # Insert legacy leads directly with NULLs
    async with SessionLocal() as session:
        legacy_lead_1 = Lead(
            id="legacy-lead-1",
            name="Автотехцентр Формула",
            category="Автосервис",
            city="Казань",
            address="ул. Баумана, 5",
            phone="+78431234567",
            has_website=False,
            photos=None,
            logo_url=None,
            social_links=None,
            emails=None,
            opening_hours=None,
            demo_id="demo-form-1",
            status="new",
        )
        legacy_lead_2 = Lead(
            id="legacy-lead-2",
            name="Стоматология Улыбка",
            category="Стоматология",
            city="Москва",
            address="Ленинградский пр-т, 12",
            phone="+74950001122",
            has_website=False,
            photos=None,
            logo_url=None,
            social_links={"telegram": "https://t.me/ulybka"},
            status="database",
        )
        session.add(legacy_lead_1)
        session.add(legacy_lead_2)
        await session.commit()

    # GET /api/leads
    res = await client.get("/api/leads")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    data = res.json()
    assert data["total"] >= 2
    items = data["items"]
    assert len(items) >= 2

    # Check lead 1
    item_1 = next((i for i in items if i["id"] == "legacy-lead-1"), None)
    assert item_1 is not None
    assert item_1["photos"] == []
    assert item_1["logo_url"] is None
    assert item_1["demo_url"] is not None
    assert "/demo/demo-form-1" in item_1["demo_url"]

    # Check lead 2
    item_2 = next((i for i in items if i["id"] == "legacy-lead-2"), None)
    assert item_2 is not None
    assert item_2["photos"] == []
    assert item_2["logo_url"] is None

    # Check single lead detail route GET /api/leads/{id}
    res_single = await client.get("/api/leads/legacy-lead-1")
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert single_data["id"] == "legacy-lead-1"
    assert single_data["photos"] == []
    assert single_data["logo_url"] is None


@pytest.mark.asyncio
async def test_init_db_auto_migration_idempotent():
    """Ensure init_db can be called multiple times without error, ensuring migration is safe."""
    await init_db()
    await init_db()

