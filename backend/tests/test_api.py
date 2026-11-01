from __future__ import annotations

import asyncio

from app.models import Lead


async def test_lead_crud_and_demo_flow(client, lead: Lead) -> None:
    response = await client.get("/api/leads")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == lead.name
    assert data["items"][0]["status_label"] == "Новый"

    response = await client.patch(f"/api/leads/{lead.id}", json={"status": "database", "notes": "Позвонить завтра"})
    assert response.status_code == 200
    assert response.json()["status_label"] == "В базе"

    response = await client.get("/api/meta")
    meta = response.json()
    assert meta["total"] == 1
    assert meta["cities"][0]["value"] == "Москва"
    assert meta["no_website"] == 1

    response = await client.post(f"/api/leads/{lead.id}/demo")
    assert response.status_code == 200
    demo = response.json()
    assert demo["id"]
    assert "Aurora" in demo["html"]
    assert demo["public_url"].endswith(f"/demo/{demo['id']}")
    assert "demo" in demo["message"].lower() or "концепт" in demo["message"].lower()

    raw = await client.get(f"/api/demos/{demo['id']}/raw")
    assert raw.status_code == 200
    assert raw.headers["content-type"].startswith("text/html")
    assert "Aurora" in raw.text

    public = await client.get(f"/demo/{demo['id']}")
    assert public.status_code == 200

    response = await client.patch(f"/api/demos/{demo['id']}", json={"published": False, "message": "Новый текст"})
    assert response.status_code == 200
    assert response.json()["published"] is False
    assert (await client.get(f"/demo/{demo['id']}")).status_code == 404

    response = await client.post(f"/api/leads/{lead.id}/message")
    assert response.status_code == 200
    assert response.json()["demo_url"].endswith(f"/demo/{demo['id']}")

    response = await client.get("/api/stats")
    stats = response.json()
    assert stats["total"] == 1
    assert stats["demos"] == 1
    assert stats["by_status"]["database"] == 1


async def test_export_csv_and_xlsx(client, lead: Lead) -> None:
    csv_response = await client.get("/api/export", params={"fmt": "csv"})
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "Aurora" in csv_response.text
    assert csv_response.text.startswith("\ufeff")

    xlsx_response = await client.get("/api/export", params={"fmt": "xlsx"})
    assert xlsx_response.status_code == 200
    assert xlsx_response.content[:2] == b"PK"
    assert "attachment" in xlsx_response.headers["content-disposition"]


async def test_parse_job_runs_in_background(client) -> None:
    response = await client.post(
        "/api/parse",
        json={
            "source": "demo",
            "city": "Казань",
            "categories": ["Бьюти"],
            "limit": 5,
            "only_no_website": True,
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    job = None
    for _ in range(40):
        await asyncio.sleep(0.25)
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            break

    assert job is not None
    assert job["status"] == "done"
    assert job["total_saved"] >= 1
    assert job["total_found"] == job["total_saved"]

    leads = (await client.get("/api/leads", params={"city": "Казань"})).json()
    assert leads["total"] >= 1
    assert all(item["has_website"] is False for item in leads["items"])


async def test_google_source_without_key_fails_fast(client) -> None:
    response = await client.post(
        "/api/parse", json={"source": "google", "city": "Москва", "limit": 5}
    )
    assert response.status_code == 400
    assert "GOOGLE_PLACES_API_KEY" in response.json()["detail"]
