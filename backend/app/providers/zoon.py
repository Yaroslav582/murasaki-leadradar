from __future__ import annotations

import asyncio
import random
import re
from urllib.parse import quote

import httpx

from app.config import settings
from app.providers.base import BaseProvider, PlaceResult, ProviderError, sample_user_agents
from app.providers.demo import CITIES, get_city_coords

ZOON_CITIES = {
    "москва": "msk",
    "санкт-петербург": "spb",
    "казань": "kzn",
    "екатеринбург": "ekb",
    "новосибирск": "nsk",
    "нижний новгород": "nn",
    "самара": "smr",
    "сочи": "sochi",
    "краснодар": "krd",
    "ростов-на-дону": "rnd",
    "уфа": "ufa",
    "пермь": "perm",
    "воронеж": "vrn",
    "волгоград": "vlg",
    "челябинск": "chel",
    "омск": "omsk",
    "красноярск": "krsk",
    "тюмень": "tmn",
    "саратов": "srt",
    "тольятти": "tlt",
    "ижевск": "izhevsk",
    "барнаул": "brn",
    "ульяновск": "uln",
    "иркутск": "irkutsk",
    "хабаровск": "khv",
    "ярославль": "yar",
    "владивосток": "vld",
    "томск": "tsk",
    "оренбург": "orb",
    "рязань": "rzn",
    "астрахань": "astrakhan",
    "пенза": "pnz",
    "липецк": "lpk",
    "тула": "tula",
    "киров": "kirov",
    "чебоксары": "chb",
    "калининград": "klgd",
    "курск": "kursk",
    "тверь": "tver",
    "ставрополь": "stv",
    "сургут": "surgut",
    "иваново": "ivanovo",
    "брянск": "bryansk",
    "белгород": "belgorod",
    "владимир": "vladimir",
    "калуга": "kaluga",
    "смоленск": "smolensk",
    "вологда": "vologda",
    "мурманск": "murmansk",
    "кострома": "kostroma",
    "новороссийск": "nvrsk",
    "таганрог": "tgn",
    "севастополь": "sevastopol",
    "йошкар-ола": "yo",
    "чита": "chita",
}

ZOON_CATEGORIES = {
    "Бьюти": "beauty",
    "Рестораны": "restaurants",
    "Автосервисы": "autoservice",
    "Медицина": "medical",
    "Фитнес": "fitness",
    "Отели": "hotels",
    "Услуги": "service",
    "Магазины": "shops",
    "Обучение": "education",
}

PHONE_RE = re.compile(r"(?:\+7|8)[\s(]*\d{3}[)\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")


class ZoonProvider(BaseProvider):
    """Free Zoon.ru business and service directory scraper."""

    source = "zoon"
    base_url = "https://zoon.ru"

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
        city_clean = city.strip()
        city_slug = ZOON_CITIES.get(city_clean.lower())
        category_name = (categories or [""])[0]
        cat_slug = ZOON_CATEGORIES.get(category_name, "service")

        proxy = settings.proxy_url.strip() if settings.proxy_url and settings.proxy_url.strip() else None
        headers = {
            "User-Agent": sample_user_agents(settings.user_agent_list),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://zoon.ru/",
        }

        results: list[PlaceResult] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=settings.http_timeout,
            proxy=proxy,
        ) as client:
            page = 1
            max_pages = min(5, (limit // 20) + 2)

            while len(results) < limit and page <= max_pages:
                if query:
                    if city_slug:
                        search_url = f"{self.base_url}/search/?city={city_slug}&query[]={quote(query)}&page={page}"
                    else:
                        search_url = f"{self.base_url}/search/?query[]={quote(f'{query} {city_clean}')}&page={page}"
                elif city_slug:
                    search_url = f"{self.base_url}/{city_slug}/{cat_slug}/?page={page}"
                else:
                    search_term = category_name or "услуги"
                    search_url = f"{self.base_url}/search/?query[]={quote(f'{search_term} {city_clean}')}&page={page}"

                resp = await client.get(search_url)
                if resp.status_code == 429:
                    if results:
                        return results
                    raise ProviderError(
                        "Zoon временно ограничил запросы (429). Попробуйте через пару минут или "
                        "укажите прокси в PROXY_URL."
                    )
                if resp.status_code != 200:
                    break

                raw_cards = re.findall(
                    r'<li[^>]*class="[^"]*minicard-item[^"]*"[^>]*>([\s\S]*?)</li>',
                    resp.text,
                )
                if not raw_cards:
                    break

                cards_to_process = []
                for card_html in raw_cards:
                    link_match = re.search(r'href="([^"]+)"[^>]+class="title-link', card_html)
                    if not link_match:
                        continue
                    item_url = link_match.group(1)
                    if item_url in seen:
                        continue
                    seen.add(item_url)

                    title_match = re.search(r'<a[^>]+class="title-link[^"]*"[^>]*>([\s\S]*?)</a>', card_html)
                    title = re.sub(r"<[^>]+>|\s+", " ", title_match.group(1)).strip() if title_match else ""
                    if not title:
                        continue

                    rating_match = re.search(r"--rating:\s*([\d\.]+)", card_html)
                    rating = float(rating_match.group(1)) if rating_match else None

                    reviews_match = re.search(r"(\d+)\s+(?:отзыв|оцен)", card_html)
                    reviews = int(reviews_match.group(1)) if reviews_match else 0

                    addr_match = re.search(r'class="[^"]*address[^"]*"[^>]*>([\s\S]*?)<', card_html)
                    address = addr_match.group(1).strip() if addr_match else ""
                    if city and address and city.lower() not in address.lower():
                        address = f"{city}, {address}"

                    cards_to_process.append({
                        "name": title,
                        "url": item_url,
                        "rating": rating,
                        "reviews_count": reviews,
                        "address": address,
                    })

                for item in cards_to_process:
                    if len(results) >= limit:
                        break

                    phone: str | None = None
                    website: str | None = None

                    try:
                        detail_resp = await client.get(item["url"])
                        if detail_resp.status_code == 200:
                            phones = re.findall(r"tel:([^\"'\s>]+)", detail_resp.text)
                            if phones:
                                phone = phones[0]
                            site_match = re.search(
                                r'data-type="site"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*data-uitest="website"',
                                detail_resp.text,
                            )
                            if site_match:
                                website = site_match.group(1) or site_match.group(2)
                    except Exception:
                        pass

                    city_coords = get_city_coords(city)
                    results.append(
                        PlaceResult(
                            name=item["name"],
                            category=category_name or "Услуги",
                            city=city,
                            address=item["address"],
                            phone=phone,
                            website_url=website,
                            rating=item["rating"],
                            reviews_count=item["reviews_count"],
                            latitude=city_coords[0] if city_coords else None,
                            longitude=city_coords[1] if city_coords else None,
                            source=self.source,
                            source_id=item["url"],
                        )
                    )
                    await asyncio.sleep(random.uniform(0.3, 0.6))

                page += 1

        return results
