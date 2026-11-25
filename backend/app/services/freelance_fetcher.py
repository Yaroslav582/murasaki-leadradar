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


async def fetch_habr_freelance_orders(limit: int = 15) -> list[dict[str, Any]]:
    """Fetch live tasks from Habr Freelance RSS/HTML."""
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=12, follow_redirects=True) as client:
        try:
            resp = await client.get(
                "https://freelance.habr.com/tasks?categories=development_sites,development_all_inclusive,design_sites"
            )
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            tasks = soup.select("li.content-list__item")
            for item in tasks:
                title_el = item.select_one(".task__title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                proj_url = f"https://freelance.habr.com{href}" if href.startswith("/") else href
                price_el = item.select_one(".task__price")
                budget_str = price_el.get_text(" ", strip=True) if price_el else "По договоренности"

                matched, _ = match_keywords(title)
                if not matched:
                    continue

                num_match = re.search(r"\d+", href)
                msg_id = int(num_match.group(0)) if num_match else random.randint(100000, 999999)
                results.append({
                    "source": "habr",
                    "source_url": proj_url,
                    "message_id": msg_id,
                    "chat_id": "freelance.habr.com",
                    "chat_title": "Habr Freelance",
                    "author_username": "habr_client",
                    "author_name": "Заказчик на Habr Freelance",
                    "raw_text": title,
                    "summary": title,
                    "category": "Веб-сайт",
                    "budget": budget_str,
                })
                if len(results) >= limit:
                    break
        except Exception as exc:
            logger.warning("Error fetching Habr Freelance orders: %s", exc)
    return results


async def fetch_hh_project_leads(limit: int = 15) -> list[dict[str, Any]]:
    """Fetch small-business vacancies on HH.ru looking for website/landing creation."""
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": "LeadRadar/1.0 (https://leadradar.app)"},
        timeout=12,
    ) as client:
        try:
            resp = await client.get(
                "https://api.hh.ru/vacancies",
                params={
                    "text": "создать сайт OR нужен лендинг OR сайт под ключ",
                    "area": 113,
                    "per_page": min(limit, 20),
                    "order_by": "publication_time",
                },
            )
            if resp.status_code != 200:
                return results
            items = resp.json().get("items") or []
            for v in items:
                title = v.get("name") or ""
                emp = (v.get("employer") or {}).get("name") or "Компания"
                area = (v.get("area") or {}).get("name") or ""
                url = v.get("alternate_url") or ""
                vid = v.get("id")
                salary = v.get("salary")
                budget_str = "По договорённости"
                if isinstance(salary, dict):
                    s_from = salary.get("from")
                    s_to = salary.get("to")
                    cur = salary.get("currency", "RUB")
                    if s_from or s_to:
                        budget_str = f"{s_from or ''}–{s_to or ''} {cur}".strip("– ")

                snippet = ((v.get("snippet") or {}).get("requirement") or "") + " " + (
                    (v.get("snippet") or {}).get("responsibility") or ""
                )
                clean_snippet = _clean_html(snippet)
                raw_text = f"{title} ({emp}, {area}). {clean_snippet}".strip()

                results.append({
                    "source": "hh",
                    "source_url": url,
                    "message_id": int(vid) if str(vid).isdigit() else random.randint(100000, 999999),
                    "chat_id": "hh.ru",
                    "chat_title": f"HH.ru ({area or 'РФ'})",
                    "author_username": "hh_employer",
                    "author_name": emp,
                    "raw_text": raw_text,
                    "summary": f"{title} — {emp}",
                    "category": "Веб-сайт",
                    "budget": budget_str,
                })
                if len(results) >= limit:
                    break
        except Exception as exc:
            logger.warning("Error fetching HH.ru leads: %s", exc)
    return results


async def sync_external_freelance_orders(session: AsyncSession) -> int:
    """Fetch external orders from Kwork, FL.ru, Habr Freelance & HH.ru, generate responses and save to DB."""
    all_external: list[dict[str, Any]] = []

    kwork_items, fl_items, habr_items, hh_items = await asyncio.gather(
        fetch_kwork_orders(limit=20),
        fetch_fl_orders(limit=10),
        fetch_habr_freelance_orders(limit=10),
        fetch_hh_project_leads(limit=10),
        return_exceptions=True,
    )

    for batch in (kwork_items, fl_items, habr_items, hh_items):
        if isinstance(batch, list):
            all_external.extend(batch)

    new_count = 0
    created_orders: list[TelegramOrder] = []
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
        created_orders.append(order)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Successfully synced %s new freelance orders (Kwork & FL.ru)", new_count)
        try:
            from app.services.lead_notifier import lead_notifier
            for ord_item in created_orders:
                await lead_notifier.notify_new_order(ord_item)
        except Exception as n_err:
            logger.warning("Could not dispatch lead notification: %s", n_err)

    return new_count
