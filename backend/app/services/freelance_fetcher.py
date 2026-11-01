from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import timedelta
from typing import Any

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TelegramOrder, utcnow
from app.services.telegram_service import generate_ai_response, match_keywords

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}


def _clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


async def fetch_kwork_orders(limit: int = 25) -> list[dict[str, Any]]:
    """Fetch live freelance orders from Kwork exchange."""
    results: list[dict[str, Any]] = []
    # Categories: 37 = Сайты под ключ, 41 = Лендинги, 11 = Разработка и IT
    categories = [37, 41, 11]

    async with httpx.AsyncClient(headers=HEADERS, timeout=12) as client:
        for cat in categories:
            try:
                resp = await client.post(
                    f"https://kwork.ru/projects?c={cat}&page=1",
                    data={"page": 1},
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data.get("data", {}).get("pagination", {}).get("data", [])
                for item in items:
                    raw_desc = item.get("description", "")
                    clean_desc = _clean_html(raw_desc)
                    if len(clean_desc) < 20:
                        continue

                    # Check keywords relevance
                    matched, reason = match_keywords(clean_desc)
                    if not matched and not match_keywords(item.get("title", ""))[0]:
                        # If category is 37 or 41 (websites/landings), keep it even if generic
                        if cat not in (37, 41):
                            continue

                    project_id = str(item.get("id"))
                    title = item.get("title") or (clean_desc[:70] + "..." if len(clean_desc) > 70 else clean_desc)
                    
                    price = item.get("possiblePriceLimit") or item.get("priceLimit") or 0
                    if price:
                        price_num = int(float(price))
                        budget_str = f"{price_num:,} ₽".replace(",", " ")
                    else:
                        budget_str = "По договоренности"

                    username = item.get("username") or "Заказчик Kwork"

                    results.append({
                        "source": "kwork",
                        "source_url": f"https://kwork.ru/projects/{project_id}",
                        "message_id": int(project_id) if project_id.isdigit() else random.randint(100000, 999999),
                        "chat_id": "kwork.ru",
                        "chat_title": "Kwork — Биржа проектов",
                        "author_username": username,
                        "author_name": f"{username} (Kwork)",
                        "raw_text": clean_desc,
                        "summary": title,
                        "category": "Сайт под ключ" if cat == 37 else ("Лендинг" if cat == 41 else "Веб-разработка"),
                        "budget": budget_str,
                    })
                    if len(results) >= limit:
                        return results
            except Exception as exc:
                logger.warning("Error fetching Kwork category %s: %s", cat, exc)

    return results


async def fetch_fl_orders(limit: int = 15) -> list[dict[str, Any]]:
    """Fetch live freelance orders from FL.ru projects exchange."""
    results: list[dict[str, Any]] = []
    url = "https://www.fl.ru/projects/?kind=1"

    async with httpx.AsyncClient(
        headers={"User-Agent": HEADERS["User-Agent"], "Accept": "text/html,application/xhtml+xml"},
        timeout=12,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select('div[class*="b-post"]') or soup.select("div.project")
            for c in cards:
                h2 = c.find("h2")
                if not h2:
                    continue
                a_tag = h2.find("a")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                proj_url = f"https://www.fl.ru{href}" if href.startswith("/") else href

                # Keywords filter
                matched, _ = match_keywords(title)
                price_el = c.find(class_=re.compile(r"price|cost"))
                budget_str = price_el.get_text(strip=True) if price_el else "По договоренности"

                desc_el = c.find(class_=re.compile(r"text|body|descr"))
                desc = desc_el.get_text(separator=" ", strip=True) if desc_el else title

                if not matched and not match_keywords(desc)[0]:
                    continue

                # Extract digits from href for message_id
                num_match = re.search(r"\d+", href)
                msg_id = int(num_match.group(0)) if num_match else random.randint(100000, 999999)

                results.append({
                    "source": "fl",
                    "source_url": proj_url,
                    "message_id": msg_id,
                    "chat_id": "fl.ru",
                    "chat_title": "FL.ru — Биржа фриланса",
                    "author_username": "fl_client",
                    "author_name": "Заказчик на FL.ru",
                    "raw_text": desc,
                    "summary": title,
                    "category": "Веб-сайт",
                    "budget": budget_str,
                })
                if len(results) >= limit:
                    break
        except Exception as exc:
            logger.warning("Error fetching FL.ru orders: %s", exc)

    return results


async def sync_external_freelance_orders(session: AsyncSession) -> int:
    """Fetch external orders from Kwork & FL.ru, generate responses and save to DB."""
    all_external: list[dict[str, Any]] = []

    kwork_items, fl_items = await asyncio.gather(
        fetch_kwork_orders(limit=20),
        fetch_fl_orders(limit=10),
        return_exceptions=True,
    )

    if isinstance(kwork_items, list):
        all_external.extend(kwork_items)
    if isinstance(fl_items, list):
        all_external.extend(fl_items)

    new_count = 0
    now = utcnow()

    for item in all_external:
        source_url = item.get("source_url")
        if not source_url:
            continue

        # Check existing by source_url
        existing = await session.scalar(
            select(TelegramOrder.id).where(TelegramOrder.source_url == source_url)
        )
        if existing:
            continue

        # Generate tailored AI response
        ai_resp = await generate_ai_response(item["raw_text"], category=item["category"])
        delay_sec = random.randint(
            settings.telegram_auto_response_delay_min,
            settings.telegram_auto_response_delay_max,
        )

        order = TelegramOrder(
            chat_id=item["chat_id"],
            chat_title=item["chat_title"],
            source=item["source"],
            source_url=item["source_url"],
            message_id=item["message_id"],
            author_username=item.get("author_username"),
            author_name=item.get("author_name"),
            raw_text=item["raw_text"],
            summary=item["summary"],
            category=item["category"],
            budget=item.get("budget"),
            response_text=ai_resp,
            scheduled_for=now + timedelta(seconds=delay_sec),
            status="pending",
        )
        session.add(order)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Successfully synced %s new freelance orders (Kwork & FL.ru)", new_count)

    return new_count
