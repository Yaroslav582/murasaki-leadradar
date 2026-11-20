"""
TGStat Database Collector (tgstat_collector.py)
-----------------------------------------------
Automatic discovery and enrichment of target Telegram chats & discussion channels
via the official TGStat API (api.tgstat.ru).

Features:
- Pagination handling (limit, offset) across keywords and categories.
- TGStat rate-limit handling with exponential backoff & jitter.
- Target filtration:
  * Discards dead channels (CI < 5.0, subscribers < 100, restrictions/scam flags).
  * Keeps public chats/supergroups (peer_type == 'chat').
  * Keeps channels having a linked discussion group or comment chat.
  * Deduplicates against existing entries in `join_queue` and `telegram_chat_targets`.
- Asynchronous batch inserting into Supabase PostgreSQL `join_queue`.
- CLI interface with rich logging and dry-run support.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Ensure backend root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.db import SessionLocal, init_db
from app.models import JoinQueue, TelegramChatTarget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TGStatCollector")

TGSTAT_API_URL = "https://api.tgstat.ru/channels/search"

# Curated defaults for freelance / lead generation
DEFAULT_CATEGORIES = [
    "freelance",
    "business",
    "design",
    "development",
    "marketing",
]

DEFAULT_KEYWORDS = [
    "фриланс заказы",
    "дизайн сайтов",
    "веб разработка",
    "маркетинг",
    "бизнес чат",
    "it вакансии заказы",
    "чат фрилансеров",
]

# Regex pattern to extract discussion chat links or handles from channel 'about'
DISCUSSION_REGEXES = [
    re.compile(
        r"(?:наш\s+чат|чат\s+проекта|чат\s+обсуждений|обсуждение|флуд|комментарии|чат|чат\s+заказов|order\s+chat)[\s\:\-]+(?:https?:\/\/)?(?:t\.me\/|@)([a-zA-Z0-9_]{4,32})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:наш\s+чат|чат\s+проекта|чат\s+обсуждений|обсуждение|флуд|комментарии|чат)[\s\:\-]+(?:https?:\/\/)?t\.me\/(\+[a-zA-Z0-9_-]{10,32})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:наш\s+чат|чат\s+проекта|чат\s+обсуждений|обсуждение|флуд|комментарии|чат)[\s\:\-]+(?:https?:\/\/)?t\.me\/joinchat\/([a-zA-Z0-9_-]{10,32})",
        re.IGNORECASE,
    ),
]


def clean_username_or_link(raw: str) -> str:
    """Normalize Telegram link or username to a standardized format."""
    raw = raw.strip()
    if raw.startswith("https://t.me/+") or raw.startswith("t.me/+"):
        if not raw.startswith("http"):
            raw = "https://" + raw
        return raw
    if raw.startswith("https://t.me/joinchat/") or raw.startswith("t.me/joinchat/"):
        if not raw.startswith("http"):
            raw = "https://" + raw
        return raw
    # Strip url prefix
    raw = re.sub(r"^(?:https?:\/\/)?t\.me\/", "", raw)
    raw = raw.lstrip("@").strip()
    return f"@{raw}" if raw else ""


def extract_discussion_from_about(about: str | None) -> str | None:
    """Scan channel 'about' text for mentions of discussion groups/chats."""
    if not about:
        return None
    for pattern in DISCUSSION_REGEXES:
        match = pattern.search(about)
        if match:
            extracted = match.group(1)
            if extracted.startswith("+") or "joinchat" in extracted:
                return f"https://t.me/{extracted}"
            return f"@{extracted.lstrip('@')}"
    return None


class TGStatCollector:
    """Collector for finding Telegram target chats & groups via TGStat API."""

    def __init__(
        self,
        token: str | None = None,
        min_ci: float = 5.0,
        min_members: int = 100,
        max_pages_per_query: int = 5,
        page_limit: int = 100,
    ) -> None:
        self.token = token or os.getenv("TGSTAT_TOKEN") or ""
        self.min_ci = min_ci
        self.min_members = min_members
        self.max_pages_per_query = max_pages_per_query
        self.page_limit = min(page_limit, 100)
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> TGStatCollector:
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "LeadRadar-TGStat-Collector/2.0"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.client:
            await self.client.aclose()

    async def _fetch_page(
        self,
        params: dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        """Fetch a single page with automatic rate limit exponential backoff."""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=15.0)

        url_params = {"token": self.token, **params}

        for attempt in range(1, max_retries + 1):
            try:
                resp = await self.client.get(TGSTAT_API_URL, params=url_params)

                # Rate limited HTTP 429
                if resp.status_code == 429:
                    wait_sec = (2 ** attempt) + 1.0
                    logger.warning(
                        f"TGStat rate limit (429). Retrying in {wait_sec:.1f}s (attempt {attempt}/{max_retries})..."
                    )
                    await asyncio.sleep(wait_sec)
                    continue

                if resp.status_code != 200:
                    logger.error(
                        f"TGStat API error HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    return None

                data = resp.json()
                if data.get("status") == "error":
                    err_msg = data.get("error", "Unknown error")
                    if "rate" in err_msg.lower() or "limit" in err_msg.lower():
                        wait_sec = (2 ** attempt) + 1.0
                        logger.warning(
                            f"TGStat API limit message: '{err_msg}'. Waiting {wait_sec:.1f}s..."
                        )
                        await asyncio.sleep(wait_sec)
                        continue
                    logger.error(f"TGStat API returned error: {err_msg}")
                    return None

                return data.get("response", {})

            except httpx.RequestError as exc:
                wait_sec = (2 ** attempt) + 0.5
                logger.warning(
                    f"Network error querying TGStat ({exc}). Retrying in {wait_sec:.1f}s..."
                )
                await asyncio.sleep(wait_sec)

        return None

    async def search_query(
        self,
        query: str | None = None,
        category: str | None = None,
        peer_type: str = "all",  # 'chat', 'channel', or 'all'
    ) -> list[dict[str, Any]]:
        """
        Query TGStat channels/search with pagination.
        Returns validated, raw item dictionaries.
        """
        if not self.token:
            logger.error("TGSTAT_TOKEN is not configured! Cannot query official TGStat API.")
            return []

        all_items: list[dict[str, Any]] = []
        offset = 0

        for page in range(self.max_pages_per_query):
            params: dict[str, Any] = {
                "limit": self.page_limit,
                "offset": offset,
                "country": "ru",
                "language": "russian",
                "search_by_description": 1,
            }
            if query:
                params["q"] = query
            if category:
                params["category"] = category
            if peer_type != "all":
                params["peer_type"] = peer_type

            logger.info(
                f"Fetching TGStat [q='{query or ''}', cat='{category or ''}', type='{peer_type}'] offset={offset}..."
            )
            data = await self._fetch_page(params)
            if not data:
                break

            items = data.get("items", [])
            total_count = data.get("count", 0)

            if not items:
                break

            all_items.extend(items)
            offset += len(items)

            if offset >= total_count or len(items) < self.page_limit:
                break

            # Polite pause to stay well under API rate limits (1-2 req/sec)
            await asyncio.sleep(0.7)

        return all_items

    async def filter_and_extract_targets(
        self,
        raw_items: list[dict[str, Any]],
        existing_targets: set[str],
        category_label: str = "general",
    ) -> list[dict[str, Any]]:
        """
        Filter candidate channels/chats according to strict criteria:
        1. Ignore if already in `existing_targets`.
        2. Keep if peer_type == 'chat' (public group).
        3. Keep if channel has linked discussion chat.
        4. Drop inactive / dead channels (CI < min_ci or members < min_members).
        """
        extracted_targets: list[dict[str, Any]] = []
        seen_in_batch: set[str] = set()

        for item in raw_items:
            tgstat_id = item.get("id")
            peer_type = item.get("peer_type", "channel")
            ci_index = float(item.get("ci_index") or 0.0)
            participants = int(item.get("participants_count") or 0)
            restrictions = item.get("tgstat_restrictions") or []

            # Filter dead or scam channels
            if restrictions:
                continue
            if ci_index < self.min_ci and peer_type != "chat":
                # For channels require minimal CI authority; chats may have lower CI
                continue
            if participants < self.min_members:
                continue

            target_link: str | None = None

            # Case A: Public chat / supergroup
            if peer_type == "chat":
                raw_handle = item.get("username") or item.get("link")
                if raw_handle:
                    target_link = clean_username_or_link(str(raw_handle))

            # Case B: Channel with linked discussion chat
            else:
                # 1. Check if TGStat provided linked_chat field
                linked_obj = item.get("linked_chat")
                if isinstance(linked_obj, dict):
                    raw_handle = linked_obj.get("username") or linked_obj.get("link")
                    if raw_handle:
                        target_link = clean_username_or_link(str(raw_handle))
                # 2. Extract from 'about' bio
                if not target_link:
                    about_text = item.get("about") or ""
                    target_link = extract_discussion_from_about(about_text)

            if not target_link:
                continue

            normalized = target_link.lower()
            if normalized in existing_targets or normalized in seen_in_batch:
                continue

            seen_in_batch.add(normalized)
            extracted_targets.append({
                "username_or_link": target_link,
                "tgstat_id": tgstat_id,
                "category": category_label,
                "members_count": participants,
                "status": "pending",
            })

        return extracted_targets

    async def get_existing_targets(self) -> set[str]:
        """Fetch all existing usernames and links from join_queue and telegram_chat_targets."""
        existing: set[str] = set()
        async with SessionLocal() as session:
            # 1. From join_queue
            res_q = await session.execute(select(JoinQueue.username_or_link))
            for val in res_q.scalars().all():
                if val:
                    existing.add(val.strip().lower())

            # 2. From telegram_chat_targets
            res_t = await session.execute(
                select(TelegramChatTarget.username, TelegramChatTarget.chat_id)
            )
            for uname, cid in res_t.all():
                if uname:
                    existing.add(clean_username_or_link(uname).lower())
                if cid and str(cid).startswith("@"):
                    existing.add(str(cid).strip().lower())

        return existing

    async def save_to_join_queue(self, targets: list[dict[str, Any]]) -> int:
        """Save unique targets into join_queue table in DB (PostgreSQL / SQLite)."""
        if not targets:
            return 0

        async with SessionLocal() as session:
            inserted_count = 0
            for item in targets:
                uname = item["username_or_link"]
                existing = await session.scalar(
                    select(JoinQueue).where(JoinQueue.username_or_link == uname)
                )
                if not existing:
                    entry = JoinQueue(
                        username_or_link=uname,
                        tgstat_id=item.get("tgstat_id"),
                        category=item.get("category"),
                        members_count=item.get("members_count", 0),
                        status="pending",
                    )
                    session.add(entry)
                    inserted_count += 1
            await session.commit()
            return inserted_count

    async def run(
        self,
        keywords: list[str] | None = None,
        categories: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """Execute full discovery and collection cycle."""
        keywords = keywords or DEFAULT_KEYWORDS
        categories = categories or DEFAULT_CATEGORIES

        logger.info(
            f"Starting TGStat collection: {len(keywords)} keywords, {len(categories)} categories"
        )
        logger.info(f"Filters: min_ci={self.min_ci}, min_members={self.min_members}")

        existing = await self.get_existing_targets()
        logger.info(f"Loaded {len(existing)} existing channels/chats from database.")

        total_raw_found = 0
        all_extracted_targets: list[dict[str, Any]] = []

        # 1. Search chats directly (peer_type='chat')
        for kw in keywords:
            items = await self.search_query(query=kw, peer_type="chat")
            total_raw_found += len(items)
            filtered = await self.filter_and_extract_targets(
                items, existing, category_label=kw
            )
            for f in filtered:
                existing.add(f["username_or_link"].lower())
                all_extracted_targets.append(f)

        # 2. Search categories (peer_type='all')
        for cat in categories:
            items = await self.search_query(category=cat, peer_type="all")
            total_raw_found += len(items)
            filtered = await self.filter_and_extract_targets(
                items, existing, category_label=cat
            )
            for f in filtered:
                existing.add(f["username_or_link"].lower())
                all_extracted_targets.append(f)

        logger.info(
            f"Collected {len(all_extracted_targets)} new eligible targets from {total_raw_found} raw results."
        )

        saved_count = 0
        if not dry_run:
            saved_count = await self.save_to_join_queue(all_extracted_targets)
            logger.info(
                f"Successfully committed {saved_count} new targets into Supabase join_queue!"
            )
        else:
            logger.info(
                f"[DRY-RUN] Skipped saving. Would have inserted {len(all_extracted_targets)} rows."
            )

        return {
            "total_raw": total_raw_found,
            "eligible_found": len(all_extracted_targets),
            "saved": saved_count,
        }


# Curated demo targets for immediate testing when TGSTAT_TOKEN is not yet set
CURATED_DEMO_CHATS = [
    {"username_or_link": "@freelancetavern", "category": "фриланс", "members_count": 54200},
    {"username_or_link": "@freelance_chat_ru", "category": "фриланс", "members_count": 31500},
    {"username_or_link": "@zakazy_freelance", "category": "фриланс заказы", "members_count": 19800},
    {"username_or_link": "@designer_jobs", "category": "дизайн", "members_count": 28400},
    {"username_or_link": "@web_freelance_jobs", "category": "веб разработка", "members_count": 22100},
    {"username_or_link": "@it_freelance_chat", "category": "разработка", "members_count": 14700},
    {"username_or_link": "@tabor_it", "category": "it вакансии", "members_count": 42000},
    {"username_or_link": "@tg_bots_orders", "category": "разработка ботов", "members_count": 16500},
]


async def seed_demo_targets():
    """Populates initial curated targets if TGStat token is not configured."""
    logger.info("Seeding initial curated targets into join_queue for testing...")
    collector = TGStatCollector()
    existing = await collector.get_existing_targets()
    to_insert = [
        item for item in CURATED_DEMO_CHATS
        if item["username_or_link"].lower() not in existing
    ]
    if to_insert:
        saved = await collector.save_to_join_queue(to_insert)
        logger.info(f"Seeded {saved} curated targets into join_queue.")
    else:
        logger.info("All curated demo targets already exist in join_queue.")


async def main():
    parser = argparse.ArgumentParser(
        description="Search & collect target Telegram chats via TGStat API"
    )
    parser.add_argument("--token", type=str, help="TGStat API token")
    parser.add_argument(
        "--keywords",
        type=str,
        help="Comma-separated search keywords (e.g. 'фриланс,дизайн,заказы')",
    )
    parser.add_argument(
        "--categories",
        type=str,
        help="Comma-separated categories (e.g. 'freelance,design,business')",
    )
    parser.add_argument(
        "--min-ci",
        type=float,
        default=5.0,
        help="Minimum Citation Index (ИЦ) for channels (default: 5.0)",
    )
    parser.add_argument(
        "--min-members",
        type=int,
        default=100,
        help="Minimum members count (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving to database",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Seed curated test targets if token is absent",
    )

    args = parser.parse_args()

    token = args.token or os.getenv("TGSTAT_TOKEN")

    if not token and not args.seed_demo:
        logger.warning(
            "\n" + "=" * 60 + "\n"
            "⚠️  TGSTAT_TOKEN is not set in .env!\n"
            "To use live TGStat search:\n"
            "  1. Register at https://api.tgstat.ru and obtain an API token.\n"
            "  2. Add 'TGSTAT_TOKEN=your_token' to backend/.env\n"
            "\nFor now, running with --seed-demo to populate initial target chats...\n"
            + "=" * 60
        )
        await seed_demo_targets()
        return

    if args.seed_demo:
        await seed_demo_targets()
        if not token:
            return

    keywords = (
        [k.strip() for k in args.keywords.split(",") if k.strip()]
        if args.keywords
        else DEFAULT_KEYWORDS
    )
    categories = (
        [c.strip() for c in args.categories.split(",") if c.strip()]
        if args.categories
        else DEFAULT_CATEGORIES
    )

    async with TGStatCollector(
        token=token,
        min_ci=args.min_ci,
        min_members=args.min_members,
    ) as collector:
        stats = await collector.run(
            keywords=keywords,
            categories=categories,
            dry_run=args.dry_run,
        )
        print("\n=== TGStat Collection Summary ===")
        print(f"Total raw items examined: {stats['total_raw']}")
        print(f"Eligible targets extracted: {stats['eligible_found']}")
        print(f"Saved into join_queue:    {stats['saved']}")
        print("==================================\n")


if __name__ == "__main__":
    asyncio.run(main())
