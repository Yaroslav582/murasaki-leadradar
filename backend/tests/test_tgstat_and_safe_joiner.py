"""
Tests for TGStatCollector and SafeJoiner
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
import pytest
from app.db import SessionLocal
from app.models import JoinQueue, WorkerAccount, utcnow
from tgstat_collector import (
    TGStatCollector,
    clean_username_or_link,
    extract_discussion_from_about,
)
from safe_joiner import SafeJoiner, is_msk_night_mode, STAGE_CONFIGS


def test_clean_username_or_link():
    assert clean_username_or_link("@mychat") == "@mychat"
    assert clean_username_or_link("mychat") == "@mychat"
    assert clean_username_or_link("https://t.me/mychat") == "@mychat"
    assert clean_username_or_link("t.me/mychat") == "@mychat"
    assert clean_username_or_link("https://t.me/+AbCdEfGh123") == "https://t.me/+AbCdEfGh123"
    assert clean_username_or_link("https://t.me/joinchat/AbCdEfGh123") == "https://t.me/joinchat/AbCdEfGh123"


def test_extract_discussion_from_about():
    about_text = "Канал о дизайне и фрилансе.\nНаш чат: @design_freelance_chat\nПо рекламе: @admin"
    chat = extract_discussion_from_about(about_text)
    assert chat == "@design_freelance_chat"

    about_invite = "Канал разработчиков. Чат проекта: https://t.me/+SecretGroup123"
    chat2 = extract_discussion_from_about(about_invite)
    assert chat2 == "https://t.me/+SecretGroup123"

    about_empty = "Просто канал без чата."
    assert extract_discussion_from_about(about_empty) is None


def test_msk_night_mode():
    is_night, wait_sec = is_msk_night_mode()
    assert isinstance(is_night, bool)
    assert isinstance(wait_sec, float)
    if is_night:
        assert wait_sec > 0


def test_stage_configs():
    assert STAGE_CONFIGS[1]["max_daily"] == 4
    assert STAGE_CONFIGS[2]["max_daily"] == 10
    assert STAGE_CONFIGS[3]["max_daily"] == 18
    assert STAGE_CONFIGS[1]["pause_range"] == (7200.0, 14400.0)


@pytest.mark.asyncio
async def test_worker_account_lifecycle_and_reset():
    async with SessionLocal() as session:
        # Create test worker
        worker = WorkerAccount(
            phone="+79990001122",
            session_string="mock_string_session",
            warmup_stage=1,
            joins_today=4,
            total_chats=10,
            is_active=True,
            last_reset_date=date(2025, 1, 1), # Yesterday in the past
        )
        session.add(worker)
        await session.commit()
        await session.refresh(worker)

        joiner = SafeJoiner()

        # 1. Test daily counter reset
        await joiner._reset_daily_counters_if_needed(worker, session)
        assert worker.joins_today == 0
        assert worker.last_reset_date == datetime.now(timezone.utc).date()

        # 2. Test auto-upgrade of warmup stage based on account age
        worker.created_at = utcnow() - timedelta(days=25)
        new_stage = await joiner._auto_advance_warmup_stage(worker, session)
        assert new_stage == 3
        assert worker.warmup_stage == 3

        # Cleanup
        await session.delete(worker)
        await session.commit()


@pytest.mark.asyncio
async def test_join_queue_deduplication():
    collector = TGStatCollector(min_ci=5.0, min_members=100)

    raw_sample = [
        # Should be included (peer_type == 'chat', > 100 members)
        {
            "id": 101,
            "peer_type": "chat",
            "username": "@freelance_super_test",
            "participants_count": 500,
            "ci_index": 12.0,
            "tgstat_restrictions": [],
        },
        # Should be filtered out (dead channel: participants < 100)
        {
            "id": 102,
            "peer_type": "chat",
            "username": "@dead_chat_test",
            "participants_count": 12,
            "ci_index": 1.0,
            "tgstat_restrictions": [],
        },
        # Channel with linked discussion in about
        {
            "id": 103,
            "peer_type": "channel",
            "username": "@some_channel",
            "about": "Полезные заказы. Чат: @orders_linked_chat",
            "participants_count": 2500,
            "ci_index": 25.0,
            "tgstat_restrictions": [],
        },
    ]

    existing = {"@already_exists_chat"}
    extracted = await collector.filter_and_extract_targets(raw_sample, existing)

    extracted_links = [x["username_or_link"] for x in extracted]
    assert "@freelance_super_test" in extracted_links
    assert "@orders_linked_chat" in extracted_links
    assert "@dead_chat_test" not in extracted_links
