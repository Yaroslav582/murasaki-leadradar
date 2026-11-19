"""
Safe Joiner Background Worker (safe_joiner.py)
-----------------------------------------------
Smooth, stealthy, human-like Telegram channel/group joiner with anti-flood protection,
multi-account pooling, multi-stage warmup schedules, and night mode.

Features:
- Multi-account worker pool (`worker_accounts` table):
  * Selects active workers with total_chats < 450, no active flood_wait, and remaining daily joins.
  * Auto-resets daily join counters at calendar midnight.
  * Auto-advances warmup stages based on account age (1-7 days: Stage 1, 8-21: Stage 2, 21+: Stage 3).
- Strict Warmup & Rate Limiting:
  * Stage 1: max 4 joins/day, pause 7200 - 14400s (2 - 4 hours).
  * Stage 2: max 10 joins/day, pause 2700 - 5400s (45 - 90 mins).
  * Stage 3: max 18 joins/day, pause 1800 - 3600s (30 - 60 mins).
- Moscow Night Mode (01:00 - 08:00 MSK):
  * Automatically pauses all join activity during sleeping hours.
- Human Simulation:
  * Pre-join jitter delay: 5 - 15 seconds.
  * Post-join pause: 2 - 5 seconds.
  * Marks last 3 - 5 messages as read via send_read_acknowledge.
- Telegram Exception Handling:
  * FloodWaitError: sets `flood_wait_until = now + e.seconds + (300..900s)` in DB and rotates account.
  * ChannelsTooMuchError: sets `total_chats = 500` for account and rotates account.
  * ChannelPrivateError, InviteHashExpiredError, UsernameInvalidError: marks item `failed`, continues.
  * UserAlreadyParticipantError: marks item `skipped`, increments total_chats.
  * InviteRequestSentError: marks item `joined` (admin approval pending).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import re
import signal
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select, update
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChannelsTooMuchError,
    FloodWaitError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    InviteRequestSentError,
    UserAlreadyParticipantError,
    UserBannedInChannelError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

# Ensure backend root on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.db import SessionLocal, init_db
from app.models import JoinQueue, TgAccount, WorkerAccount, utcnow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SafeJoiner")

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID") or 2040)
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH") or "b18441a1ff607e10a989891a5462e627"

# Stage limits: (max_daily_joins, min_pause_sec, max_pause_sec)
STAGE_CONFIGS = {
    1: {"max_daily": 4, "pause_range": (7200.0, 14400.0)},   # 2 - 4 hours
    2: {"max_daily": 10, "pause_range": (2700.0, 5400.0)},   # 45 - 90 mins
    3: {"max_daily": 18, "pause_range": (1800.0, 3600.0)},   # 30 - 60 mins
}


def clean_handle(raw: str) -> str:
    """Normalize handle or link."""
    raw = raw.strip()
    raw = re.sub(r"^https?:\/\/t\.me\/", "", raw)
    return raw.lstrip("@").strip()


def is_msk_night_mode() -> tuple[bool, float]:
    """
    Checks if current time is within Moscow night window (01:00 to 08:00 MSK).
    Returns (is_night, seconds_until_08_00_msk).
    """
    msk_tz = timezone(timedelta(hours=3))
    now_msk = datetime.now(msk_tz)
    hour = now_msk.hour

    if 1 <= hour < 8:
        target = now_msk.replace(hour=8, minute=0, second=0, microsecond=0)
        seconds_left = (target - now_msk).total_seconds() + random.uniform(30.0, 180.0)
        return True, max(seconds_left, 30.0)

    return False, 0.0


class SafeJoiner:
    """Async background worker orchestrating smooth Telegram joins."""

    def __init__(
        self,
        api_id: int = TELEGRAM_API_ID,
        api_hash: str = TELEGRAM_API_HASH,
        check_interval_seconds: int = 30,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._active_clients: dict[str, TelegramClient] = {}
        # In-memory cooldown tracking per worker id: worker_id -> datetime (UTC)
        self._worker_cooldowns: dict[str, datetime] = {}

    async def _get_client_for_worker(self, worker: WorkerAccount) -> TelegramClient | None:
        """Get or initialize cached TelegramClient for worker session."""
        worker_id_str = str(worker.id)
        if worker_id_str in self._active_clients:
            client = self._active_clients[worker_id_str]
            if client.is_connected():
                return client

        if not worker.session_string:
            logger.error(f"Worker {worker.phone} has empty session string!")
            return None

        try:
            client = TelegramClient(
                StringSession(worker.session_string.strip()),
                self.api_id,
                self.api_hash,
                connection_retries=5,
                retry_delay=3,
                timeout=25,
            )
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(
                    f"Worker {worker.phone}: Session is not authorized or revoked by Telegram."
                )
                await client.disconnect()
                return None

            self._active_clients[worker_id_str] = client
            return client
        except Exception as exc:
            logger.error(f"Worker {worker.phone}: Failed to initialize MTProto client: {exc}")
            return None

    async def _close_all_clients(self) -> None:
        """Gracefully disconnect all cached Telethon clients."""
        for w_id, client in list(self._active_clients.items()):
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                pass
        self._active_clients.clear()

    async def _auto_advance_warmup_stage(
        self, worker: WorkerAccount, session
    ) -> int:
        """Auto-upgrade warmup_stage based on account age if not manually overridden."""
        now = utcnow()
        age_days = (now - worker.created_at).days if worker.created_at else 0
        current_stage = worker.warmup_stage or 1

        new_stage = current_stage
        if age_days > 21 and current_stage < 3:
            new_stage = 3
        elif age_days > 7 and current_stage < 2:
            new_stage = 2

        if new_stage != current_stage:
            logger.info(
                f"Worker {worker.phone}: Account age is {age_days} days. "
                f"Advancing warmup stage {current_stage} -> {new_stage}!"
            )
            worker.warmup_stage = new_stage
            await session.commit()

        return new_stage

    async def _reset_daily_counters_if_needed(
        self, worker: WorkerAccount, session
    ) -> None:
        """Reset daily joins if calendar day has changed."""
        today = datetime.now(timezone.utc).date()
        if worker.last_reset_date is None or worker.last_reset_date < today:
            logger.info(
                f"Worker {worker.phone}: New calendar day ({today}). Resetting joins_today from {worker.joins_today} to 0."
            )
            worker.joins_today = 0
            worker.last_reset_date = today
            await session.commit()

    async def get_next_available_worker(self) -> tuple[WorkerAccount | None, float]:
        """
        Selects a worker from worker_accounts according to specifications:
        - is_active is True
        - total_chats < 450
        - flood_wait_until is None or has passed
        - joins_today < max_daily_joins
        - cooldown has elapsed
        Returns (worker, sleep_seconds_if_none).
        """
        now = utcnow()
        today = datetime.now(timezone.utc).date()

        async with SessionLocal() as session:
            # Query active workers
            stmt = (
                select(WorkerAccount)
                .where(
                    WorkerAccount.is_active == True,
                    WorkerAccount.total_chats < 450,
                )
                .order_by(WorkerAccount.joins_today.asc())
            )
            res = await session.execute(stmt)
            workers = list(res.scalars().all())

            if not workers:
                logger.warning(
                    "No active workers found in worker_accounts with total_chats < 450!"
                )
                return None, 60.0

            soonest_available_wait: float = 300.0

            for worker in workers:
                # 1. Reset daily counter if day changed
                await self._reset_daily_counters_if_needed(worker, session)

                # 2. Check flood_wait
                if worker.flood_wait_until and worker.flood_wait_until > now:
                    wait_sec = (worker.flood_wait_until - now).total_seconds()
                    soonest_available_wait = min(soonest_available_wait, wait_sec)
                    continue

                # 3. Check warmup stage & limits
                stage = await self._auto_advance_warmup_stage(worker, session)
                stage_cfg = STAGE_CONFIGS.get(stage, STAGE_CONFIGS[1])
                max_daily = stage_cfg["max_daily"]

                if worker.joins_today >= max_daily:
                    # Limit reached for today, will be ready tomorrow midnight
                    tomorrow_midnight = datetime.combine(
                        today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
                    )
                    wait_sec = (tomorrow_midnight - now).total_seconds()
                    soonest_available_wait = min(soonest_available_wait, wait_sec)
                    continue

                # 4. Check in-memory pause / cooldown between joins
                w_id = str(worker.id)
                cooldown_until = self._worker_cooldowns.get(w_id)
                if cooldown_until and cooldown_until > now:
                    wait_sec = (cooldown_until - now).total_seconds()
                    soonest_available_wait = min(soonest_available_wait, wait_sec)
                    continue

                # All checks passed! This worker is ready to join
                return worker, 0.0

            return None, max(soonest_available_wait, 15.0)

    async def get_next_queue_item(self) -> JoinQueue | None:
        """Fetch next pending item from join_queue."""
        async with SessionLocal() as session:
            stmt = (
                select(JoinQueue)
                .where(JoinQueue.status == "pending")
                .order_by(JoinQueue.created_at.asc())
                .limit(1)
            )
            res = await session.execute(stmt)
            return res.scalars().first()

    async def execute_join_cycle(
        self, worker: WorkerAccount, queue_item: JoinQueue
    ) -> bool:
        """
        Executes stealth join into channel/group:
        1. Pre-join human delay (5-15s).
        2. Resolve entity & request JoinChannelRequest / ImportChatInviteRequest.
        3. Post-join human delay (2-5s) & read last 3-5 messages via send_read_acknowledge.
        4. Handles all Telegram exceptions precisely.
        5. Sets worker post-join cooldown according to warmup stage.
        """
        client = await self._get_client_for_worker(worker)
        if not client:
            return False

        target_str = queue_item.username_or_link.strip()
        logger.info(
            f"Worker {worker.phone} (Stage {worker.warmup_stage}, joins today: {worker.joins_today}): "
            f"Preparing to join '{target_str}'..."
        )

        # Step 1: Human behavior simulation - pre-join pause 5-15s
        pre_delay = random.uniform(5.0, 15.0)
        logger.info(f"Worker {worker.phone}: Human pause before action ({pre_delay:.1f}s)...")
        await asyncio.sleep(pre_delay)

        now = utcnow()
        entity: Any = None
        join_successful = False

        async with SessionLocal() as session:
            # Re-fetch objects within current session to update
            db_worker = await session.get(WorkerAccount, worker.id)
            db_queue = await session.get(JoinQueue, queue_item.id)
            if not db_worker or not db_queue:
                return False

            try:
                # Step 2: Handle private invite links vs public username handles
                if "+" in target_str or "joinchat" in target_str:
                    match = re.search(r"(?:\+|\/joinchat\/)([a-zA-Z0-9_-]+)", target_str)
                    if not match:
                        raise UsernameInvalidError("Cannot parse invite hash from URL")
                    invite_hash = match.group(1)
                    updates = await client(ImportChatInviteRequest(invite_hash))
                    chats = getattr(updates, "chats", [])
                    entity = chats[0] if chats else updates
                    logger.info(f"Worker {worker.phone}: Successfully joined private invite {target_str}")
                else:
                    uname = clean_handle(target_str)
                    entity = await client.get_entity(uname)
                    await client(JoinChannelRequest(entity))
                    logger.info(
                        f"Worker {worker.phone}: Successfully joined @{uname} "
                        f"('{getattr(entity, 'title', uname)}')"
                    )

                join_successful = True
                db_queue.status = "joined"
                db_queue.assigned_worker_id = db_worker.id
                db_queue.processed_at = now
                db_worker.joins_today += 1
                db_worker.total_chats += 1

                # Step 3: Human simulation - post-join pause & read last 3-5 messages
                await asyncio.sleep(random.uniform(2.0, 5.0))
                try:
                    read_limit = random.randint(3, 5)
                    messages = await client.get_messages(entity, limit=read_limit)
                    if messages:
                        max_id = max(m.id for m in messages)
                        await client.send_read_acknowledge(entity, max_id=max_id)
                        logger.info(
                            f"Worker {worker.phone}: Read and acknowledged {len(messages)} latest messages in {target_str}."
                        )
                except Exception as read_exc:
                    logger.warning(
                        f"Worker {worker.phone}: Could not acknowledge read history: {read_exc}"
                    )

            # Exception Handling: FloodWaitError
            except FloodWaitError as exc:
                penalty_extra = random.randint(300, 900)
                flood_until = now + timedelta(seconds=exc.seconds + penalty_extra)
                logger.warning(
                    f"⚠️ Worker {worker.phone} hit Telegram FloodWait: {exc.seconds}s! "
                    f"Marking flood_wait_until={flood_until.isoformat()} (+{penalty_extra}s jitter). "
                    f"Rotating worker..."
                )
                db_worker.flood_wait_until = flood_until
                self._worker_cooldowns[str(db_worker.id)] = flood_until
                await session.commit()
                return False

            # Exception Handling: ChannelsTooMuchError (500 chats limit)
            except ChannelsTooMuchError:
                logger.error(
                    f"⛔ Worker {worker.phone} reached maximum 500 Telegram chats limit! "
                    f"Setting total_chats = 500 and disabling from joining."
                )
                db_worker.total_chats = 500
                await session.commit()
                return False

            # Exception Handling: Already a participant
            except UserAlreadyParticipantError:
                logger.info(
                    f"ℹ️ Worker {worker.phone} is already a member of {target_str}. Marking skipped."
                )
                db_queue.status = "skipped"
                db_queue.assigned_worker_id = db_worker.id
                db_queue.error_log = "UserAlreadyParticipantError: Already a participant"
                db_queue.processed_at = now
                db_worker.total_chats += 1
                join_successful = True

            # Exception Handling: Invite Request Sent (Admin approval pending)
            except InviteRequestSentError:
                logger.info(
                    f"📩 Worker {worker.phone} sent join request to {target_str} (pending admin review)."
                )
                db_queue.status = "joined"
                db_queue.assigned_worker_id = db_worker.id
                db_queue.error_log = "InviteRequestSentError: Request sent to admin"
                db_queue.processed_at = now
                db_worker.joins_today += 1
                db_worker.total_chats += 1
                join_successful = True

            # Exception Handling: Expired, Private, or Invalid Handles
            except (
                InviteHashExpiredError,
                InviteHashInvalidError,
                ChannelPrivateError,
                UsernameInvalidError,
                UsernameNotOccupiedError,
                UserBannedInChannelError,
            ) as exc:
                err_text = f"{exc.__class__.__name__}: {exc}"
                logger.warning(
                    f"❌ Target {target_str} failed ({err_text}). Marking failed in queue."
                )
                db_queue.status = "failed"
                db_queue.error_log = err_text
                db_queue.processed_at = now

            except Exception as exc:
                err_text = f"Unexpected error: {exc}"
                logger.error(f"Unexpected error joining {target_str}: {exc}", exc_info=True)
                db_queue.status = "failed"
                db_queue.error_log = err_text
                db_queue.processed_at = now

            # Step 4: Calculate and set stage cooldown for this worker
            stage = db_worker.warmup_stage or 1
            stage_cfg = STAGE_CONFIGS.get(stage, STAGE_CONFIGS[1])
            min_pause, max_pause = stage_cfg["pause_range"]

            if join_successful:
                pause_sec = random.uniform(min_pause, max_pause)
                cooldown_time = now + timedelta(seconds=pause_sec)
                self._worker_cooldowns[str(db_worker.id)] = cooldown_time
                logger.info(
                    f"Worker {worker.phone} (Stage {stage}): Next join scheduled in "
                    f"{pause_sec / 60.0:.1f} minutes ({cooldown_time.strftime('%H:%M:%S')} UTC)."
                )
            else:
                # If target was invalid/failed, worker only needs a tiny polite pause
                self._worker_cooldowns[str(db_worker.id)] = now + timedelta(seconds=random.uniform(10.0, 30.0))

            await session.commit()

        return join_successful

    async def run(self) -> None:
        """Main orchestrator loop."""
        self._running = True
        logger.info("SafeJoiner worker started.")
        logger.info("Press Ctrl+C to terminate cleanly.")

        while self._running:
            try:
                # 1. Check MSK Night Mode (01:00 to 08:00 MSK)
                is_night, night_sleep = is_msk_night_mode()
                if is_night:
                    logger.info(
                        f"🌙 Moscow Night Mode active (01:00-08:00 MSK). Sleeping for "
                        f"{night_sleep / 3600.0:.2f} hours..."
                    )
                    await asyncio.sleep(min(night_sleep, 1800.0))
                    continue

                # 2. Check for next item in join_queue
                queue_item = await self.get_next_queue_item()
                if not queue_item:
                    logger.info("join_queue is empty. Sleeping 45 seconds for new items...")
                    await asyncio.sleep(45.0)
                    continue

                # 3. Pick eligible worker
                worker, sleep_sec = await self.get_next_available_worker()
                if not worker:
                    logger.info(
                        f"All workers busy, on cooldown, or at daily limits. Sleeping {sleep_sec:.0f}s..."
                    )
                    await asyncio.sleep(sleep_sec)
                    continue

                # 4. Execute stealth join
                await self.execute_join_cycle(worker, queue_item)

                # Short loop tick
                await asyncio.sleep(self.check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in SafeJoiner main loop: {exc}", exc_info=True)
                await asyncio.sleep(15.0)

        await self._close_all_clients()
        logger.info("SafeJoiner shut down cleanly.")

    def stop(self) -> None:
        self._running = False


# Helper CLI utilities for managing worker accounts pool
async def import_tg_accounts_to_worker_accounts() -> int:
    """Import active accounts from tg_accounts table into worker_accounts."""
    imported = 0
    async with SessionLocal() as session:
        res = await session.execute(select(TgAccount))
        accounts = res.scalars().all()

        existing_phones = set(
            (await session.execute(select(WorkerAccount.phone))).scalars().all()
        )

        for acc in accounts:
            if not acc.session_string or acc.phone in existing_phones:
                continue

            stage = 1
            if acc.warmup_level and acc.warmup_level >= 75:
                stage = 3
            elif acc.warmup_level and acc.warmup_level >= 30:
                stage = 2

            worker = WorkerAccount(
                phone=acc.phone,
                session_string=acc.session_string,
                warmup_stage=stage,
                joins_today=0,
                total_chats=0,
                is_active=True,
                last_reset_date=datetime.now(timezone.utc).date(),
            )
            session.add(worker)
            imported += 1

        await session.commit()

    logger.info(f"Imported {imported} accounts from tg_accounts into worker_accounts.")
    return imported


async def add_worker_account(phone: str, session_str: str, stage: int = 1) -> None:
    """Add a new technical account to worker_accounts pool."""
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(WorkerAccount).where(WorkerAccount.phone == phone))
        ).scalars().first()

        if existing:
            existing.session_string = session_str
            existing.warmup_stage = stage
            existing.is_active = True
            logger.info(f"Updated existing worker {phone}.")
        else:
            new_worker = WorkerAccount(
                phone=phone,
                session_string=session_str,
                warmup_stage=stage,
                joins_today=0,
                total_chats=0,
                is_active=True,
                last_reset_date=datetime.now(timezone.utc).date(),
            )
            session.add(new_worker)
            logger.info(f"Created new worker {phone} with warmup stage {stage}.")
        await session.commit()


async def print_status() -> None:
    """Display current statistics of worker accounts and queue."""
    async with SessionLocal() as session:
        workers = (await session.execute(select(WorkerAccount))).scalars().all()
        q_pending = len(
            (await session.execute(select(JoinQueue).where(JoinQueue.status == "pending"))).scalars().all()
        )
        q_joined = len(
            (await session.execute(select(JoinQueue).where(JoinQueue.status == "joined"))).scalars().all()
        )
        q_failed = len(
            (await session.execute(select(JoinQueue).where(JoinQueue.status == "failed"))).scalars().all()
        )
        q_skipped = len(
            (await session.execute(select(JoinQueue).where(JoinQueue.status == "skipped"))).scalars().all()
        )

        print("\n" + "=" * 60)
        print("📊 SAFE JOINER POOL STATUS")
        print("=" * 60)
        print(f"Queue: Pending: {q_pending} | Joined: {q_joined} | Failed: {q_failed} | Skipped: {q_skipped}")
        print("-" * 60)
        print(f"Workers Pool ({len(workers)} accounts):")
        for w in workers:
            flood = w.flood_wait_until.strftime("%Y-%m-%d %H:%M") if w.flood_wait_until else "None"
            print(
                f" • Phone: {w.phone:<16} | Stage: {w.warmup_stage} | "
                f"Today: {w.joins_today} | Total: {w.total_chats}/450 | "
                f"Active: {w.is_active} | FloodWait: {flood}"
            )
        print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Telegram Safe Joiner Worker")
    parser.add_argument("--status", action="store_true", help="Print pool & queue statistics")
    parser.add_argument(
        "--import-tg-accounts",
        action="store_true",
        help="Import accounts from tg_accounts into worker_accounts",
    )
    parser.add_argument(
        "--add-account",
        nargs=2,
        metavar=("PHONE", "SESSION_STRING"),
        help="Add or update a worker account",
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="Warmup stage for new account (1, 2, or 3)",
    )

    args = parser.parse_args()

    if args.status:
        await print_status()
        return

    if args.import_tg_accounts:
        await import_tg_accounts_to_worker_accounts()
        await print_status()
        return

    if args.add_account:
        phone, session_str = args.add_account
        await add_worker_account(phone, session_str, stage=args.stage)
        await print_status()
        return

    # Check if pool is empty and offer auto-import
    async with SessionLocal() as session:
        workers_count = len((await session.execute(select(WorkerAccount))).scalars().all())
        if workers_count == 0:
            logger.info("worker_accounts is empty. Checking for accounts in tg_accounts...")
            imported = await import_tg_accounts_to_worker_accounts()
            if imported == 0:
                logger.warning(
                    "\n" + "=" * 65 + "\n"
                    "⚠️  No worker accounts found in worker_accounts!\n"
                    "Please add at least one technical account using:\n"
                    "  python safe_joiner.py --add-account '+79991234567' 'STRING_SESSION'\n"
                    "Or import existing Mini App accounts with:\n"
                    "  python safe_joiner.py --import-tg-accounts\n"
                    + "=" * 65
                )

    joiner = SafeJoiner()

    # Graceful shutdown handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, joiner.stop)
        except NotImplementedError:
            pass  # Windows event loop doesn't implement add_signal_handler

    await joiner.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user. Exiting.")
