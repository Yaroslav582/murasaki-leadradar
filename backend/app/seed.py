from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from app.db import SessionLocal, init_db
from app.models import Lead
from app.providers.demo import CATEGORIES, CITIES, DemoProvider
from app.services.demos import create_demo
from app.services.jobs import save_places

logger = logging.getLogger(__name__)

SEED_CITIES = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Сочи", "Краснодар"]


async def seed_demo_data() -> int:
    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count(Lead.id))) or 0
        if existing:
            return 0

        provider = DemoProvider()
        created_leads: list[Lead] = []
        for city in SEED_CITIES:
            places = await provider.search(
                city=city,
                categories=CATEGORIES,
                query=None,
                limit=9,
            )
            _created, _updated, leads = await save_places(session, places, city)
            created_leads.extend(leads)

        for index, lead in enumerate(created_leads):
            if index % 23 == 7:
                lead.status = "deal"
            elif index % 17 == 5:
                lead.status = "sent"
            elif index % 11 == 3:
                lead.status = "database"
            elif index % 29 == 19:
                lead.status = "rejected"
            if lead.status == "deal":
                lead.notes = "Созвонились, ждём подтверждение. Демо понравилось."
            session.add(lead)

        await session.commit()

        demo_targets = [lead for lead in created_leads if not lead.has_website][:2]
        for lead in demo_targets:
            await create_demo(session, lead)

        logger.info("Seeded %s demo leads", len(created_leads))
        return len(created_leads)


async def _main() -> None:
    await init_db()
    count = await seed_demo_data()
    print(f"Seeded {count} leads")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
