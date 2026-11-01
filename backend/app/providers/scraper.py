from __future__ import annotations

import asyncio
import random
import re
from urllib.parse import quote

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError, sample_user_agents


class ScraperProvider(BaseProvider):
    """Experimental Google Maps browser scraper.

    Requires `pip install -r requirements-scraper.txt` and `playwright install chromium`.
    Use a residential proxy via PROXY_URL for production volumes.
    """

    source = "scraper"

    async def search(
        self,
        *,
        city: str,
        categories: list[str],
        query: str | None,
        limit: int,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: int | None = None,
    ) -> list[PlaceResult]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "Playwright не установлен. Выполните: pip install -r requirements-scraper.txt "
                "и playwright install chromium"
            ) from exc

        category = (categories or [""])[0]
        text = query or f"{category} {city}".strip()
        search_url = f"https://www.google.com/maps/search/{quote(text)}?hl=ru"
        proxy_str = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None
        proxy = {"server": proxy_str} if proxy_str else None

        results: list[PlaceResult] = []
        seen: set[str] = set()

        async with async_playwright() as playwright:
            browser = None
            launch_args = {"headless": True}
            if proxy:
                launch_args["proxy"] = proxy

            for ch in ("chrome", "msedge", None):
                try:
                    kwargs = dict(launch_args)
                    if ch:
                        kwargs["channel"] = ch
                    browser = await playwright.chromium.launch(**kwargs)
                    break
                except Exception:
                    continue

            if not browser:
                raise ProviderError(
                    "Не удалось запустить браузер для Google Maps scraper. Установите Google Chrome "
                    "или выполните: playwright install chromium"
                )
            context = await browser.new_context(
                user_agent=sample_user_agents(settings.user_agent_list),
                locale="ru-RU",
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                await self._accept_consent(page)
                try:
                    await page.wait_for_selector('div[role="feed"]', timeout=15000)
                except Exception:
                    pass

                hrefs = await self._collect_place_links(page, limit * 2)
                for href in hrefs:
                    if len(results) >= limit:
                        break
                    place = await self._parse_place(page, href, city, category)
                    if place and place.source_id not in seen:
                        seen.add(place.source_id or "")
                        results.append(place)
                        await asyncio.sleep(random.uniform(0.4, 1.1))
            finally:
                await context.close()
                await browser.close()
        return results

    async def _accept_consent(self, page) -> None:
        for label in ("Принять все", "Accept all", "Согласен"):
            try:
                button = page.get_by_role("button", name=label)
                if await button.count():
                    await button.first.click(timeout=3000)
                    await page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

    async def _collect_place_links(self, page, wanted: int) -> list[str]:
        links: set[str] = set()
        for _ in range(10):
            anchors = await page.query_selector_all('a[href*="/maps/place/"]')
            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if href:
                    links.add(href.split("?")[0])
            if len(links) >= wanted:
                break
            try:
                await page.eval_on_selector('div[role="feed"]', "el => el.scrollBy(0, 1200)")
            except Exception:
                await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(900)
        return list(links)

    async def _parse_place(self, page, href: str, city: str, category: str) -> PlaceResult | None:
        try:
            await page.goto(href, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)
        except Exception:
            return None

        async def text_of(selector: str) -> str | None:
            element = await page.query_selector(selector)
            return (await element.inner_text()).strip() if element else None

        name = await text_of("h1")
        if not name:
            return None

        address = await text_of('button[data-item-id="address"]')
        if address:
            address = re.sub(r"^(Адрес|Address):\s*", "", address)

        phone_button = await page.query_selector('button[data-item-id^="phone:tel:"]')
        phone = None
        if phone_button:
            phone = (await phone_button.get_attribute("data-item-id") or "").replace("phone:tel:", "") or None
            if not phone:
                phone = await phone_button.inner_text()

        website_el = await page.query_selector('a[data-item-id="authority"]')
        website = await website_el.get_attribute("href") if website_el else None

        rating = None
        rating_el = await page.query_selector('div.F7nice span[aria-hidden="true"]')
        if rating_el:
            try:
                rating = float((await rating_el.inner_text()).replace(",", "."))
            except ValueError:
                rating = None

        reviews_count = 0
        reviews_el = await page.query_selector('button[aria-label*="отзыв"]')
        if reviews_el:
            label = await reviews_el.get_attribute("aria-label") or ""
            digits = re.sub(r"\D", "", label)
            reviews_count = int(digits) if digits else 0

        type_el = await page.query_selector("button[jsaction*='category']")
        place_category = (await type_el.inner_text()).strip() if type_el else category

        coords = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", page.url)
        latitude = float(coords.group(1)) if coords else None
        longitude = float(coords.group(2)) if coords else None

        hours: list[str] = []
        hours_table = await page.query_selector('table[class*="eK4R0e"]')
        if hours_table:
            rows = await hours_table.query_selector_all("tr")
            for row in rows:
                hours.append((await row.inner_text()).replace("\t", " ").strip())

        return PlaceResult(
            name=name,
            category=place_category or category,
            city=city,
            address=address or "",
            phone=phone,
            website_url=website,
            rating=rating,
            reviews_count=reviews_count,
            latitude=latitude,
            longitude=longitude,
            opening_hours=hours,
            source=self.source,
            source_id=href,
        )
