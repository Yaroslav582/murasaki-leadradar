from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from urllib.parse import parse_qs, parse_qsl, quote, unquote_plus, urlencode, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError, sample_user_agents
from app.providers.demo import CITIES, get_city_coords

logger = logging.getLogger(__name__)

CATEGORY_TERMS = {
    "Бьюти": "салон красоты",
    "Рестораны": "ресторан",
    "Автосервисы": "автосервис",
    "Медицина": "клиника",
    "Фитнес": "фитнес клуб",
    "Отели": "отель",
    "Услуги": "услуги",
    "Магазины": "магазин",
}

PHONE_RE = re.compile(r"(?:\+7|8)[\s(]*\d{3}[)\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
ORG_ID_RE = re.compile(r"/maps/org/[^/]+/(\d+)")
ORG_URL_RE = re.compile(r"(https://yandex\.ru/maps/org/[^/]+/\d+/)")
RATING_RE = re.compile(r"Рейтинг\s*\n?\s*(\d+[.,]\d+)")
REVIEWS_RE = re.compile(r"([\d\s]{1,8})\s+(?:оценк|отзыв)")
HOURS_RE = re.compile(r"(Открыто до \d{1,2}:\d{2}|Закрыто до \d{1,2}:\d{2}|Круглосуточно)")
ADDRESS_RE = re.compile(r"Адрес\s*\n\s*([^\n]+)")
CATEGORY_RE = re.compile(r"Карты\s*·\s*[^·\n]+\s*·\s*([^\n]+)")

SKIP_DOMAINS = (
    "yandex.",
    "ya.ru",
    "yastatic.",
    "youtube.",
    "vk.com",
    "vk.ru",
    "ok.ru",
    "yandexcloud.",
)


def _clean_yandex_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return None
    try:
        parsed = urlparse(url)
        clean_query = [
            (k, v)
            for k, v in parse_qsl(parsed.query)
            if not k.startswith("utm_")
            and k not in ("yclid", "erid", "ysclid", "_openstat")
        ]
        return urlunparse(parsed._replace(query=urlencode(clean_query)))
    except Exception:
        return url.split("?")[0]


def _format_yandex_photo_url(raw: Any) -> str | None:
    """Normalizes and expands Yandex photo URL template to high quality."""
    if not raw:
        return None
    url: str | None = None
    if isinstance(raw, str):
        url = raw
    elif isinstance(raw, dict):
        url = (
            raw.get("urlTemplate")
            or raw.get("url")
            or raw.get("src")
            or raw.get("preview")
        )
        if url and "%s" in url:
            url = url.replace("%s", "orig")
        elif url and "{size}" in url:
            url = url.replace("{size}", "orig")
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        url = f"https:{url}"
    if not url.startswith("http"):
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host not in {"avatars.mds.yandex.net", "avatars.yandex.net"}:
        return None
    path = re.sub(r"/(?:XXS|XS|S|M|L)(?=/?$)", "/XXL", parsed.path, flags=re.I)
    path = re.sub(r"/(?:\d{2,4}x\d{2,4})(?=/?$)", "/XXL", path, flags=re.I)
    return urlunparse(parsed._replace(path=path, query="", fragment=""))


def _extract_item_photos(item: dict) -> tuple[str | None, list[str]]:
    """Extracts logo and up to 6 gallery photos from Yandex organization item."""
    logo_raw = (
        item.get("logotype")
        or item.get("logo")
        or item.get("icon")
        or item.get("avatar")
    )
    logo_url = _format_yandex_photo_url(logo_raw)

    photos: list[str] = []
    seen: set[str] = set()
    raw_photos = (
        item.get("photos")
        or item.get("gallery")
        or item.get("photo")
        or item.get("images")
        or []
    )
    if isinstance(raw_photos, dict):
        raw_photos = raw_photos.get("items") or raw_photos.get("photos") or [raw_photos]

    if isinstance(raw_photos, list):
        for p in raw_photos:
            p_url = _format_yandex_photo_url(p)
            if p_url and p_url not in seen and not _is_yandex_photo_junk(p_url):
                seen.add(p_url)
                photos.append(p_url)
            if len(photos) >= 6:
                break

    return logo_url, photos


def _extract_item_reviews(item: dict) -> list[dict[str, Any]]:
    raw_reviews = item.get("reviews") or item.get("reviewItems") or item.get("reviewsPreview") or []
    if isinstance(raw_reviews, dict):
        raw_reviews = raw_reviews.get("items") or raw_reviews.get("reviews") or []
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw_reviews if isinstance(raw_reviews, list) else []:
        if not isinstance(row, dict):
            continue
        user = row.get("user") if isinstance(row.get("user"), dict) else {}
        author = str(row.get("author") or row.get("userName") or user.get("name") or "").strip()
        text = str(row.get("text") or row.get("body") or row.get("description") or "").strip()
        key = (author.casefold(), text.casefold())
        if not text or key in seen:
            continue
        seen.add(key)
        result.append({
            "author": author or "Пользователь Яндекс Карт",
            "text": text,
            "date": str(row.get("date") or row.get("updatedTime") or "").strip(),
            "rating": row.get("rating") or row.get("stars") or None,
        })
        if len(result) >= 6:
            break
    return result


def _extract_reviews_from_state(value: Any, limit: int = 6) -> list[dict[str, Any]]:
    """Find review-shaped records in the JSON state embedded in Yandex Maps HTML."""
    pending = [value]
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    visited = 0
    while pending and len(found) < limit and visited < 50000:
        current = pending.pop()
        visited += 1
        if isinstance(current, dict):
            text = current.get("text") or current.get("body") or current.get("reviewText") or current.get("description")
            user = current.get("user") if isinstance(current.get("user"), dict) else {}
            author = current.get("author") or current.get("userName") or user.get("name")
            if isinstance(text, str) and len(text.strip()) >= 12 and author:
                author_text = author.get("name") if isinstance(author, dict) else str(author)
                key = (author_text.casefold(), text.strip().casefold())
                if key not in seen:
                    seen.add(key)
                    found.append({
                        "author": author_text.strip(),
                        "text": text.strip(),
                        "date": str(current.get("date") or current.get("updatedTime") or "").strip(),
                        "rating": current.get("rating") or current.get("stars"),
                    })
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return found


def _is_yandex_photo_junk(url: str) -> bool:
    low = url.lower()
    return any(marker in low for marker in (
        "get-user", "get-yapic", "logo", "yandex_logo", "map_", "scheme", "favicon", "icon"
    ))


async def _extract_yandex_reviews(page, limit: int = 6) -> list[dict[str, Any]]:
    """Read public review cards visible on a Yandex Maps organization page."""
    try:
        raw = await page.evaluate("""(limit) => {
          const selectors = [
            '.business-review-view', '[class*="business-review-view"]',
            '[data-review-id]', '[class*="review-view"]'
          ];
          const cards = [...new Set(selectors.flatMap(s => [...document.querySelectorAll(s)]))];
          const pick = (root, selectors) => {
            for (const selector of selectors) {
              const node = root.querySelector(selector);
              const text = node?.innerText?.trim();
              if (text) return text;
            }
            return '';
          };
          return cards.map(card => ({
            author: pick(card, ['.business-review-view__author-name', '[class*="author-name"]', '[class*="author"]']),
            text: pick(card, ['.business-review-view__body-text', '[class*="body-text"]', '[class*="review-text"]', '[class*="comment"]']),
            date: pick(card, ['.business-review-view__date', '[class*="review-date"]', 'time']),
            rating: Number(card.querySelector('[aria-label*="5"], [class*="rating"]')?.getAttribute('aria-label')?.match(/[1-5]/)?.[0] || 0)
          })).filter(r => r.text && r.text.length >= 12).slice(0, limit);
        }""", limit)
    except Exception:
        return []
    clean: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw or []:
        author = re.sub(r"\s+", " ", str(row.get("author") or "")).strip()
        text = re.sub(r"\s+", " ", str(row.get("text") or "")).strip()
        date = re.sub(r"\s+", " ", str(row.get("date") or "")).strip()
        key = (author.casefold(), text.casefold())
        if not text or key in seen:
            continue
        seen.add(key)
        clean.append({"author": author or "Пользователь Яндекс Карт", "text": text, "date": date, "rating": row.get("rating") or None})
    return clean


def _parse_rating(body: str) -> tuple[float | None, int]:
    rating_match = RATING_RE.search(body)
    reviews_match = REVIEWS_RE.search(body)
    rating = None
    reviews = 0
    if rating_match:
        try:
            rating = float(rating_match.group(1).replace(",", "."))
        except ValueError:
            rating = None
    if reviews_match:
        digits = re.sub(r"\D", "", reviews_match.group(1))
        reviews = int(digits) if digits else 0
    return rating, reviews


def _parse_links(external_links: list[str]) -> tuple[str | None, dict[str, str]]:
    website: str | None = None
    socials: dict[str, str] = {}
    for raw in external_links:
        value = (raw or "").strip()
        if not value.startswith(("http://", "https://")):
            continue
        lowered = value.lower()
        decoded = unquote_plus(value).lower()
        host = urlparse(value).netloc.lower()
        if any(skip in host for skip in SKIP_DOMAINS):
            continue
        if "erid=" in lowered:
            continue
        if "t.me/mapsyandex" in lowered or "t.me/yandexmaps" in lowered:
            continue
        if "обращение из яндекс" in decoded:
            continue
        if "t.me/" in lowered or "telegram.me/" in lowered:
            socials["telegram"] = value.split("?")[0]
        elif "wa.me/" in lowered or "whatsapp" in lowered:
            socials["whatsapp"] = value
        elif "instagram.com/" in lowered:
            socials["instagram"] = value.split("?")[0]
        elif "vk.com/" in lowered or "vk.ru/" in lowered:
            socials["vk"] = value.split("?")[0]
        elif website is None:
            website = value.split("?erid=")[0]
    return website, socials


def _item_to_place(item: dict, city: str, fallback_category: str) -> PlaceResult | None:
    item_id = str(item.get("id") or "")
    name = item.get("title") or item.get("shortTitle") or ""
    if not name or not item_id:
        return None

    address = item.get("fullAddress") or item.get("address") or ""
    if city and address and city.lower() not in address.lower():
        address = f"{city}, {address}"

    coords = item.get("coordinates")
    latitude = coords[1] if coords and len(coords) >= 2 else None
    longitude = coords[0] if coords and len(coords) >= 2 else None

    fallback_coords = get_city_coords(city)
    if fallback_coords and latitude is not None and longitude is not None:
        # Filter out results from wrong cities (e.g. Yandex showing Moscow ads/fallbacks)
        if abs(latitude - fallback_coords[0]) > 1.2 or abs(longitude - fallback_coords[1]) > 1.8:
            return None
    elif latitude is None and fallback_coords:
        latitude, longitude = fallback_coords[0], fallback_coords[1]

    phone = None
    for p in item.get("phones") or []:
        val = p.get("number") or p.get("value")
        if val:
            phone = val
            break

    urls = [_clean_yandex_url(u) for u in (item.get("urls") or []) if _clean_yandex_url(u)]
    website = urls[0] if urls else None

    socials: dict[str, str] = {}
    for s in item.get("socialLinks") or []:
        stype = (s.get("type") or "").lower()
        shref = s.get("href") or ""
        if "wa.me" in shref or "whatsapp" in stype:
            socials["whatsapp"] = shref
        elif "t.me" in shref or "telegram" in stype:
            socials["telegram"] = shref.split("?")[0]
        elif "vk.com" in shref or "vk.ru" in shref or "vkontakte" in stype:
            socials["vk"] = shref.split("?")[0]
        elif "instagram.com" in shref or "instagram" in stype:
            socials["instagram"] = shref.split("?")[0]

    rating_data = item.get("ratingData") or {}
    rating = rating_data.get("ratingValue")
    reviews_count = int(rating_data.get("reviewCount") or rating_data.get("ratingCount") or 0)

    hours_text = item.get("workingTimeText")
    hours = [hours_text] if hours_text else []

    cats = item.get("categories") or []
    cat_name = cats[0].get("name") if cats and isinstance(cats[0], dict) else fallback_category

    logo_url, photos = _extract_item_photos(item)
    yandex_reviews = _extract_item_reviews(item)

    return PlaceResult(
        name=name,
        category=cat_name or fallback_category or "Организация",
        city=city,
        address=address,
        phone=phone,
        website_url=website,
        social_links=socials,
        rating=rating,
        reviews_count=reviews_count,
        latitude=latitude,
        longitude=longitude,
        opening_hours=hours,
        source="yandex_web",
        source_id=item_id,
        photos=photos,
        yandex_reviews=yandex_reviews,
        logo_url=logo_url,
    )


def org_page_to_place(
    *,
    name: str,
    title: str,
    url: str,
    body: str,
    external_links: list[str],
    city: str,
    fallback_category: str,
    photos: list[str] | None = None,
    yandex_reviews: list[dict[str, Any]] | None = None,
    logo_url: str | None = None,
) -> PlaceResult | None:
    name = (name or "").strip()
    org_id_match = ORG_ID_RE.search(url)
    if not name or not org_id_match:
        return None

    title_main = title.split(" — Яндекс")[0]
    title_parts = [part.strip() for part in title_main.split(", ")]
    category = fallback_category
    if not category:
        if len(title_parts) >= 3 and title_parts[1]:
            category = title_parts[1]
        else:
            category_match = CATEGORY_RE.search(body)
            if category_match:
                category = category_match.group(1).strip()

    phone_match = PHONE_RE.search(body)
    phone = phone_match.group(0).strip() if phone_match else None

    address_match = ADDRESS_RE.search(body)
    address = address_match.group(1).strip() if address_match else ""
    if city and address and city.lower() not in address.lower():
        address = f"{city}, {address}"

    rating, reviews_count = _parse_rating(body)
    hours_match = HOURS_RE.search(body)
    hours = [hours_match.group(1)] if hours_match else []

    website, socials = _parse_links(external_links)

    query = parse_qs(urlparse(url).query)
    ll_value = query.get("ll", [None])[0]
    latitude = longitude = None
    if ll_value:
        try:
            longitude, latitude = [float(value) for value in ll_value.split(",")]
        except (TypeError, ValueError):
            latitude = longitude = None

    fallback_coords = get_city_coords(city)
    if fallback_coords and latitude is not None and longitude is not None:
        if abs(latitude - fallback_coords[0]) > 1.2 or abs(longitude - fallback_coords[1]) > 1.8:
            return None
    elif latitude is None and fallback_coords:
        latitude, longitude = fallback_coords[0], fallback_coords[1]

    return PlaceResult(
        name=name,
        category=category,
        city=city,
        address=address,
        phone=phone,
        website_url=website,
        social_links=socials,
        rating=rating,
        reviews_count=reviews_count,
        latitude=latitude,
        longitude=longitude,
        opening_hours=hours,
        source="yandex_web",
        source_id=org_id_match.group(1),
        photos=photos or [],
        yandex_reviews=yandex_reviews or [],
        logo_url=logo_url,
    )


class YandexMapsWebProvider(BaseProvider):
    """Free Yandex Maps scraper.

    Uses high-speed direct JSON state extraction via HTTP first (~1s per query,
    no browser overhead). Automatically falls back to Playwright browser automation
    if anti-bot detection occurs.
    """

    source = "yandex_web"

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
        terms = (
            [(categories[0] if categories else "", query)]
            if query
            else [
                (category, CATEGORY_TERMS.get(category, category))
                for category in (categories or [""])
            ]
        )

        # 1. Fast HTTP search (no browser, 100x faster)
        try:
            http_results = await self._search_http(
                city=city,
                terms=terms,
                limit=limit,
                latitude=latitude,
                longitude=longitude,
            )
            if http_results:
                return http_results[:limit]
        except Exception:
            pass

        # 2. Browser fallback via Playwright
        return await self._search_browser(
            city=city,
            terms=terms,
            limit=limit,
            latitude=latitude,
            longitude=longitude,
        )

    async def _search_http(
        self,
        *,
        city: str,
        terms: list[tuple[str, str]],
        limit: int,
        latitude: float | None,
        longitude: float | None,
    ) -> list[PlaceResult]:
        results: list[PlaceResult] = []
        seen: set[str] = set()

        headers = {
            "User-Agent": sample_user_agents(settings.user_agent_list),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://yandex.ru/maps/",
        }

        city_coords = get_city_coords(city)
        if latitude is not None and longitude is not None:
            center = (longitude, latitude)
        elif city_coords:
            center = (city_coords[1], city_coords[0])
        else:
            center = None

        proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None
        timeout = httpx.Timeout(settings.http_timeout)
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=timeout,
            proxy=proxy,
        ) as client:
            for category, term in terms:
                if len(results) >= limit:
                    break

                search_query = f"{term} {city}".strip()
                page = 1
                max_pages = min(10, (limit // 20) + 2)

                while len(results) < limit and page <= max_pages:
                    url = f"https://yandex.ru/maps/?text={quote(search_query)}&page={page}"
                    if center:
                        url += f"&ll={center[0]}%2C{center[1]}&z=12"

                    resp = await client.get(url)
                    if resp.status_code != 200:
                        break

                    matches = re.findall(
                        r'<script[^>]*class="[^"]*state[^"]*"[^>]*>([\s\S]*?)</script>',
                        resp.text,
                    )
                    if not matches:
                        break

                    try:
                        data = json.loads(matches[0])
                    except Exception:
                        break

                    stack = data.get("stack") or []
                    if not stack:
                        break

                    items = stack[0].get("results", {}).get("items") or []
                    if not items:
                        break

                    for item in items:
                        place = _item_to_place(item, city, category)
                        if place and place.source_id and place.source_id not in seen:
                            seen.add(place.source_id)
                            results.append(place)
                            if len(results) >= limit:
                                return results

                    page += 1
                    await asyncio.sleep(random.uniform(0.3, 0.7))

        return results

    async def _search_browser(
        self,
        *,
        city: str,
        terms: list[tuple[str, str]],
        limit: int,
        latitude: float | None,
        longitude: float | None,
    ) -> list[PlaceResult]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ProviderError(
                "Парсинг через браузер требует Playwright. Установите: pip install -r requirements-scraper.txt"
            ) from exc

        city_coords = get_city_coords(city)
        if latitude is not None and longitude is not None:
            center = (longitude, latitude)
        elif city_coords:
            center = (city_coords[1], city_coords[0])
        else:
            center = None

        results: list[PlaceResult] = []
        seen: set[str] = set()
        proxy = {"server": settings.proxy_url} if settings.proxy_url else None

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
                    "Не удалось запустить браузер для парсинга. Установите Chrome/Edge или "
                    "выполните: playwright install chromium"
                )

            context = await browser.new_context(
                locale="ru-RU",
                user_agent=sample_user_agents(settings.user_agent_list),
                viewport={"width": 1440, "height": 950},
            )

            try:
                for category, term in terms:
                    if len(results) >= limit:
                        break

                    search_page = await context.new_page()
                    try:
                        search_url = f"https://yandex.ru/maps/?text={quote(f'{term} {city}'.strip())}&z=12"
                        if center:
                            search_url += f"&ll={center[0]}%2C{center[1]}"
                        await search_page.goto(
                            search_url, wait_until="domcontentloaded", timeout=60000
                        )
                        await search_page.wait_for_timeout(5000)
                        await self._raise_if_captcha(search_page)

                        links: list[str] = []
                        for _ in range(4):
                            found = await search_page.eval_on_selector_all(
                                'a[href*="/maps/org/"]',
                                "nodes => [...new Set(nodes.map(node => node.href))]",
                            )
                            for href in found:
                                clean = ORG_URL_RE.search(href)
                                if not clean:
                                    continue
                                normalized = clean.group(1)
                                if normalized not in links:
                                    links.append(normalized)
                            if len(links) >= limit * 2 or len(results) >= limit:
                                break
                            try:
                                await search_page.mouse.move(320, 600)
                                await search_page.mouse.wheel(0, 2500)
                            except Exception:
                                pass
                            await search_page.wait_for_timeout(1400)
                    finally:
                        await search_page.close()

                    for link in links:
                        if len(results) >= limit:
                            break
                        place = await self._parse_org_page(context, link, city, category)
                        if place is None or place.source_id in seen:
                            continue
                        seen.add(place.source_id or "")
                        results.append(place)
                        await asyncio.sleep(random.uniform(0.6, 1.2))
            finally:
                await context.close()
                await browser.close()

        return results

    async def _raise_if_captcha(self, page) -> None:
        try:
            body = await page.locator("body").inner_text()
        except Exception:
            return
        if "Подтвердите, что вы не робот" in body or "SmartCaptcha" in body:
            raise ProviderError(
                "Яндекс показал капчу. Повторите позже или укажите резидентский прокси в PROXY_URL."
            )

    async def _parse_org_page(self, context, link: str, city: str, category: str):
        page = await context.new_page()
        try:
            await page.goto(link, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2500)
            await self._raise_if_captcha(page)

            try:
                phone_button = page.get_by_text("Показать телефон", exact=True)
                if await phone_button.count():
                    await phone_button.first.click(timeout=1500)
                    await page.wait_for_timeout(400)
            except Exception:
                pass

            try:
                name = (await page.locator("h1").first.inner_text(timeout=3000)).strip()
            except Exception:
                name = ""
            title = await page.title()
            body = await page.locator("body").inner_text()
            external_links = await page.eval_on_selector_all(
                'a[href^="http"]', "nodes => [...new Set(nodes.map(node => node.href))]"
            )
            raw_photos = await page.evaluate(r"""() => {
              const values = [];
              for (const node of document.querySelectorAll('img, [style*="get-altay"], [style*="get-tycoon"]')) {
                if (node.tagName === 'IMG' && node.naturalWidth > 0 && (node.naturalWidth < 240 || node.naturalHeight < 160)) continue;
                for (const value of [node.currentSrc, node.src, node.getAttribute('data-src'), node.getAttribute('srcset'), node.getAttribute('style')]) {
                  if (value) values.push(...value.match(/(?:https?:)?\/\/avatars\.mds\.yandex\.net\/[^\s,'\"()]+/g) || []);
                }
              }
              return [...new Set(values)];
            }""")
            extracted_photos: list[str] = []
            extracted_logo: str | None = None
            for p_raw in raw_photos:
                fmt = _format_yandex_photo_url(p_raw)
                if fmt and fmt not in extracted_photos and not _is_yandex_photo_junk(fmt):
                    if not extracted_logo and ("logo" in fmt.lower() or "avatar" in fmt.lower() or "icon" in fmt.lower()):
                        extracted_logo = fmt
                    else:
                        extracted_photos.append(fmt)
                if len(extracted_photos) >= 12:
                    break

            current_url = page.url
            yandex_reviews = await _extract_yandex_reviews(page)
            if not yandex_reviews:
                try:
                    await page.goto(current_url.rstrip("/") + "/reviews/", wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(900)
                    yandex_reviews = await _extract_yandex_reviews(page)
                except Exception:
                    pass
            # The organization page often lazy-loads only its first carousel item.
            # Opening the public gallery route exposes the remaining CDN image URLs.
            if len(extracted_photos) < 6:
                try:
                    await page.goto(current_url.rstrip("/") + "/gallery/", wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(900)
                    gallery_urls = await page.evaluate(r"""() => {
                      const text = document.documentElement.innerHTML;
                      return [...new Set(text.match(/(?:https?:)?\/\/avatars\.mds\.yandex\.net\/[^\s,'\"<>]+/g) || [])];
                    }""")
                    for p_raw in gallery_urls:
                        fmt = _format_yandex_photo_url(p_raw)
                        if fmt and fmt not in extracted_photos and not _is_yandex_photo_junk(fmt):
                            extracted_photos.append(fmt)
                        if len(extracted_photos) >= 12:
                            break
                except Exception:
                    pass

            return org_page_to_place(
                name=name,
                title=title,
                url=link,
                body=body,
                external_links=external_links,
                city=city,
                fallback_category=category,
                photos=extracted_photos,
                yandex_reviews=yandex_reviews,
                logo_url=extracted_logo,
            )
        except Exception:
            return None
        finally:
            await page.close()


async def fetch_yandex_org_details(source_id: str, city: str = "", category: str = "") -> PlaceResult | None:
    """Best-effort browser refresh for a Yandex org's real photos and public reviews."""
    org_id = str(source_id or "").strip()
    if not org_id.isdigit():
        return None
    http_details = PlaceResult(name="", source="yandex_web", source_id=org_id)
    headers = {
        "User-Agent": sample_user_agents(settings.user_agent_list),
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Referer": "https://yandex.ru/maps/",
    }
    proxy_url = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None
    try:
        async with httpx.AsyncClient(
            headers=headers, timeout=httpx.Timeout(8.0), follow_redirects=True, proxy=proxy_url
        ) as client:
            for suffix in ("gallery/", "reviews/"):
                response = await client.get(f"https://yandex.ru/maps/org/org/{org_id}/{suffix}")
                if response.status_code != 200 or "captcha" in response.text.lower()[:2000]:
                    continue
                body = response.text
                for raw_url in re.findall(
                    r"(?:https?:)?//avatars\.mds\.yandex\.net/(?:get-altay|get-tycoon|get-zen_doc|get-sprav-products)/[^\s\"'<>]+",
                    body,
                ):
                    photo = _format_yandex_photo_url(raw_url.rstrip("),;\\"))
                    if photo and not _is_yandex_photo_junk(photo) and photo not in http_details.photos:
                        http_details.photos.append(photo)
                soup = BeautifulSoup(body, "html.parser")
                cards = soup.select(".business-review-view, [class*=business-review-view], [data-review-id]")
                for card in cards:
                    author_node = card.select_one("[class*=author-name], [class*=author]")
                    text_node = card.select_one("[class*=body-text], [class*=review-text], [class*=comment]")
                    if text_node:
                        http_details.yandex_reviews.append({
                            "author": author_node.get_text(" ", strip=True) if author_node else "Пользователь Яндекс Карт",
                            "text": text_node.get_text(" ", strip=True),
                            "date": (card.select_one("time, [class*=review-date]").get_text(" ", strip=True)
                                     if card.select_one("time, [class*=review-date]") else ""),
                            "rating": None,
                        })
                for state in soup.select('script.state, script[class*="state"]'):
                    try:
                        http_details.yandex_reviews.extend(_extract_reviews_from_state(json.loads(state.string or state.get_text())))
                    except (TypeError, ValueError):
                        continue
                if http_details.photos and http_details.yandex_reviews:
                    break
    except Exception as exc:
        logger.debug("Static Yandex details fetch failed for %s: %s", org_id, exc)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return http_details if (http_details.photos or http_details.yandex_reviews) else None
    proxy = {"server": settings.proxy_url.strip()} if settings.proxy_url and settings.proxy_url.strip() else None
    async with async_playwright() as playwright:
        browser = None
        for channel in ("chrome", "msedge", None):
            try:
                kwargs = {"headless": True}
                if proxy:
                    kwargs["proxy"] = proxy
                if channel:
                    kwargs["channel"] = channel
                browser = await playwright.chromium.launch(**kwargs)
                break
            except Exception:
                continue
        if browser is None:
            return http_details if (http_details.photos or http_details.yandex_reviews) else None
        try:
            context = await browser.new_context(
                locale="ru-RU",
                user_agent=sample_user_agents(settings.user_agent_list),
                viewport={"width": 1440, "height": 950},
            )
            try:
                browser_details = await YandexMapsWebProvider()._parse_org_page(
                    context, f"https://yandex.ru/maps/org/org/{org_id}/", city, category
                )
                if browser_details is None:
                    return http_details if (http_details.photos or http_details.yandex_reviews) else None
                browser_details.photos = list(dict.fromkeys((browser_details.photos or []) + http_details.photos))[:12]
                reviews = list((browser_details.yandex_reviews or []) + http_details.yandex_reviews)
                deduped_reviews: list[dict[str, Any]] = []
                seen_reviews: set[tuple[str, str]] = set()
                for review in reviews:
                    key = (str(review.get("author") or "").casefold(), str(review.get("text") or "").casefold())
                    if key not in seen_reviews:
                        deduped_reviews.append(review)
                        seen_reviews.add(key)
                browser_details.yandex_reviews = deduped_reviews[:12]
                return browser_details
            finally:
                await context.close()
        finally:
            await browser.close()
