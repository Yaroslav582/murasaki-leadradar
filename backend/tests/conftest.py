from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

TEST_DB = Path(tempfile.gettempdir()) / f"leadradar_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["SEED_ON_START"] = "false"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["USE_CELERY"] = "false"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DemoSite, Lead, ParseJob  # noqa: E402


@pytest.fixture(autouse=True)
async def prepared_db():
    await init_db()
    async with SessionLocal() as session:
        await session.execute(delete(DemoSite))
        await session.execute(delete(Lead))
        await session.execute(delete(ParseJob))
        await session.commit()
    yield
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
async def lead() -> Lead:
    async with SessionLocal() as session:
        item = Lead(
            name="Студия красоты Aurora",
            category="Бьюти",
            city="Москва",
            address="Москва, ул. Тверская, 10",
            phone="+7 (999) 123-45-67",
            rating=4.8,
            reviews_count=124,
            has_website=False,
            social_links={"telegram": "https://t.me/aurora", "whatsapp": "https://wa.me/79991234567"},
            opening_hours=["Ежедневно 10:00–21:00"],
            latitude=55.7558,
            longitude=37.6173,
            source="test",
            source_id="test-1",
            status="new",
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item
