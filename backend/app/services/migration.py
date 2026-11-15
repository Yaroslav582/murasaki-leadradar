from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.config import DATA_DIR, settings
from app.db import SessionLocal
from app.models import (
    Dialog,
    Lead,
    Message,
    ParseJob,
    Proxy,
    TelegramBroadcast,
    TelegramChatTarget,
    TelegramCommentLog,
    TelegramCommentTarget,
    TelegramOrder,
    TelegramParsedUser,
    TgAccount,
    Transaction,
    User,
    DemoSite,
)

logger = logging.getLogger(__name__)


def _parse_dt(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


def _parse_json(val: Any, default: Any = None) -> Any:
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default


async def import_sqlite_data_to_postgres(sqlite_path: Path | str) -> dict[str, int]:
    """Imports all data from local SQLite parser.db into PostgreSQL / Supabase."""
    path = Path(sqlite_path)
    if not path.exists():
        return {}

    conn = sqlite3.connect(path.as_posix())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def get_table_names() -> set[str]:
        rows = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        return {r[0] for r in rows}

    existing_tables = get_table_names()
    counts: dict[str, int] = {}

    async with SessionLocal() as session:
        # 1. Users
        if "users" in existing_tables:
            rows = cursor.execute("SELECT * FROM users").fetchall()
            for r in rows:
                u_id = r["id"]
                if not (await session.get(User, u_id)):
                    session.add(
                        User(
                            id=u_id,
                            telegram_id=r["telegram_id"],
                            username=r["username"],
                            first_name=r["first_name"],
                            credits_balance=r["credits_balance"] if "credits_balance" in r.keys() else 50,
                            referrer_id=r["referrer_id"] if "referrer_id" in r.keys() else None,
                            referral_code=r["referral_code"] if "referral_code" in r.keys() else None,
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["users"] = len(rows)

        # 2. Proxies
        if "proxies" in existing_tables:
            rows = cursor.execute("SELECT * FROM proxies").fetchall()
            for r in rows:
                p_id = r["id"]
                if not (await session.get(Proxy, p_id)):
                    session.add(
                        Proxy(
                            id=p_id,
                            user_id=r["user_id"] if "user_id" in r.keys() else None,
                            protocol=r["protocol"] or "socks5",
                            host=r["host"],
                            port=r["port"],
                            username=r["username"],
                            password=r["password"],
                            is_alive=bool(r["is_alive"]),
                            last_check=_parse_dt(r["last_check"]),
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["proxies"] = len(rows)

        # 3. TgAccounts
        if "tg_accounts" in existing_tables:
            rows = cursor.execute("SELECT * FROM tg_accounts").fetchall()
            for r in rows:
                acc_id = r["id"]
                if not (await session.get(TgAccount, acc_id)):
                    session.add(
                        TgAccount(
                            id=acc_id,
                            user_id=r["user_id"] if "user_id" in r.keys() else None,
                            phone=r["phone"],
                            username=r["username"],
                            session_string=r["session_string"] if "session_string" in r.keys() else None,
                            device_model=r["device_model"] if "device_model" in r.keys() else "Samsung Galaxy S21",
                            system_version=r["system_version"] if "system_version" in r.keys() else "SDK 30",
                            app_version=r["app_version"] if "app_version" in r.keys() else "8.4.1",
                            proxy_id=r["proxy_id"] if "proxy_id" in r.keys() else None,
                            status=r["status"] or "active",
                            flood_until=_parse_dt(r["flood_until"]),
                            daily_actions_count=r["daily_actions_count"] or 0,
                            daily_actions_reset_at=_parse_dt(r["daily_actions_reset_at"]) if "daily_actions_reset_at" in r.keys() else None,
                            warmup_level=r["warmup_level"] or 0,
                            warmup_preset=r["warmup_preset"] if "warmup_preset" in r.keys() else "optimal",
                            auto_warmup=bool(r["auto_warmup"]) if "auto_warmup" in r.keys() else False,
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["tg_accounts"] = len(rows)

        # Check local legacy leadradar_user.session
        legacy_session = DATA_DIR / "leadradar_user.session"
        if legacy_session.exists():
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession

                temp_client = TelegramClient(
                    (DATA_DIR / "leadradar_user").as_posix(),
                    settings.telegram_api_id or 2040,
                    settings.telegram_api_hash or "b18441a1ff607e10a989891a5462e627",
                )
                str_s = StringSession.save(temp_client.session)
                if str_s:
                    phone = settings.telegram_phone or "+14642193549"
                    res = await session.execute(select(TgAccount).where(TgAccount.phone == phone))
                    existing_acc = res.scalars().first()
                    if existing_acc:
                        existing_acc.session_string = str_s
                        existing_acc.status = "active"
                    else:
                        session.add(
                            TgAccount(
                                phone=phone,
                                session_string=str_s,
                                status="active",
                            )
                        )
                    await session.commit()
                    logger.info("Migrated legacy leadradar_user.session to tg_accounts in Supabase")
            except Exception as exc:
                logger.warning("Could not convert legacy session during migration: %s", exc)

        # 4. Leads
        if "leads" in existing_tables:
            rows = cursor.execute("SELECT * FROM leads").fetchall()
            for r in rows:
                l_id = r["id"]
                if not (await session.get(Lead, l_id)):
                    session.add(
                        Lead(
                            id=l_id,
                            name=r["name"],
                            category=r["category"] or "",
                            city=r["city"] or "",
                            address=r["address"] or "",
                            phone=r["phone"],
                            website_url=r["website_url"],
                            has_website=bool(r["has_website"]),
                            rating=r["rating"],
                            reviews_count=r["reviews_count"] or 0,
                            latitude=r["latitude"],
                            longitude=r["longitude"],
                            social_links=_parse_json(r["social_links"], {}),
                            emails=_parse_json(r["emails"], []),
                            opening_hours=_parse_json(r["opening_hours"], []),
                            price_level=r["price_level"],
                            source=r["source"] or "demo",
                            source_id=r["source_id"],
                            status=r["status"] or "new",
                            notes=r["notes"],
                            demo_id=r["demo_id"],
                            enriched_at=_parse_dt(r["enriched_at"]),
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["leads"] = len(rows)

        # 5. DemoSites
        if "demo_sites" in existing_tables:
            rows = cursor.execute("SELECT * FROM demo_sites").fetchall()
            for r in rows:
                d_id = r["id"]
                if not (await session.get(DemoSite, d_id)):
                    session.add(
                        DemoSite(
                            id=d_id,
                            lead_id=r["lead_id"],
                            title=r["title"] or "",
                            html=r["html"] or "",
                            message=r["message"] or "",
                            published=bool(r["published"]),
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["demo_sites"] = len(rows)

        # 6. ParseJobs
        if "parse_jobs" in existing_tables:
            rows = cursor.execute("SELECT * FROM parse_jobs").fetchall()
            for r in rows:
                pj_id = r["id"]
                if not (await session.get(ParseJob, pj_id)):
                    session.add(
                        ParseJob(
                            id=pj_id,
                            source=r["source"] or "demo",
                            status=r["status"] or "queued",
                            params=_parse_json(r["params"], {}),
                            total_found=r["total_found"] or 0,
                            total_saved=r["total_saved"] or 0,
                            error=r["error"],
                            log=r["log"],
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                            finished_at=_parse_dt(r["finished_at"]),
                        )
                    )
            await session.commit()
            counts["parse_jobs"] = len(rows)

        # 7. TelegramChatTargets
        if "telegram_chat_targets" in existing_tables:
            rows = cursor.execute("SELECT * FROM telegram_chat_targets").fetchall()
            for r in rows:
                t_id = r["id"]
                if not (await session.get(TelegramChatTarget, t_id)):
                    session.add(
                        TelegramChatTarget(
                            id=t_id,
                            chat_id=r["chat_id"],
                            title=r["title"] or "",
                            username=r["username"],
                            kind=r["kind"] or "both",
                            is_active=bool(r["is_active"]),
                            cooldown_minutes=r["cooldown_minutes"] if "cooldown_minutes" in r.keys() else 120,
                            custom_text=r["custom_text"] if "custom_text" in r.keys() else None,
                            auto_post_enabled=bool(r["auto_post_enabled"]) if "auto_post_enabled" in r.keys() else False,
                            last_checked_at=_parse_dt(r["last_checked_at"]),
                            last_post_at=_parse_dt(r["last_post_at"]),
                            next_post_at=_parse_dt(r["next_post_at"]) if "next_post_at" in r.keys() else None,
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["telegram_chat_targets"] = len(rows)

        # 8. TelegramOrders
        if "telegram_orders" in existing_tables:
            rows = cursor.execute("SELECT * FROM telegram_orders").fetchall()
            for r in rows:
                o_id = r["id"]
                if not (await session.get(TelegramOrder, o_id)):
                    session.add(
                        TelegramOrder(
                            id=o_id,
                            chat_id=r["chat_id"],
                            chat_title=r["chat_title"] or "",
                            source=r["source"] if "source" in r.keys() else "telegram",
                            source_url=r["source_url"] if "source_url" in r.keys() else None,
                            message_id=r["message_id"] or 0,
                            author_id=r["author_id"],
                            author_username=r["author_username"],
                            author_name=r["author_name"],
                            raw_text=r["raw_text"] or "",
                            summary=r["summary"] or "",
                            category=r["category"] or "Веб-сайт",
                            budget=r["budget"],
                            response_text=r["response_text"],
                            scheduled_for=_parse_dt(r["scheduled_for"]),
                            responded_at=_parse_dt(r["responded_at"]),
                            status=r["status"] or "pending",
                            error=r["error"],
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["telegram_orders"] = len(rows)

        # 9. Dialogs & Messages
        if "dialogs" in existing_tables:
            rows = cursor.execute("SELECT * FROM dialogs").fetchall()
            for r in rows:
                dlg_id = r["id"]
                if not (await session.get(Dialog, dlg_id)):
                    session.add(
                        Dialog(
                            id=dlg_id,
                            account_id=r["account_id"],
                            peer_id=r["peer_id"],
                            peer_username=r["peer_username"],
                            peer_name=r["peer_name"],
                            lead_id=r["lead_id"],
                            status=r["status"] or "new",
                            ai_auto_reply_enabled=bool(r["ai_auto_reply_enabled"]) if "ai_auto_reply_enabled" in r.keys() else True,
                            unread_count=r["unread_count"] or 0,
                            last_message_at=_parse_dt(r["last_message_at"]),
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["dialogs"] = len(rows)

        if "messages" in existing_tables:
            rows = cursor.execute("SELECT * FROM messages").fetchall()
            for r in rows:
                m_id = r["id"]
                if not (await session.get(Message, m_id)):
                    session.add(
                        Message(
                            id=m_id,
                            dialog_id=r["dialog_id"],
                            account_id=r["account_id"],
                            direction=r["direction"] or "in",
                            text=r["text"] or "",
                            tg_message_id=r["tg_message_id"],
                            is_ai_generated=bool(r["is_ai_generated"]),
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["messages"] = len(rows)

        # 10. Transactions
        if "transactions" in existing_tables:
            rows = cursor.execute("SELECT * FROM transactions").fetchall()
            for r in rows:
                t_id = r["id"]
                if not (await session.get(Transaction, t_id)):
                    session.add(
                        Transaction(
                            id=t_id,
                            user_id=r["user_id"],
                            amount=r["amount"] or 0,
                            type=r["type"] or "deposit",
                            module_name=r["module_name"],
                            description=r["description"],
                            created_at=_parse_dt(r["created_at"]) or datetime.now(),
                        )
                    )
            await session.commit()
            counts["transactions"] = len(rows)

    conn.close()
    return counts
