from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATA_DIR, settings

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    # Strip enclosing quotes if present in .env
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1].strip()

    # Normalize PostgreSQL prefixes for asyncpg
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[11:]
    elif url.startswith("postgresql://") and "+asyncpg" not in url and "+psycopg" not in url:
        url = "postgresql+asyncpg://" + url[13:]

    # Remove unsupported asyncpg parameters (e.g. pgbouncer=true from Prisma/Supabase snippets)
    if "asyncpg" in url and "?" in url:
        parts = urlsplit(url)
        query_params = parse_qs(parts.query)
        # asyncpg does not accept pgbouncer kwarg
        query_params.pop("pgbouncer", None)

        # If Supabase pooler host and no ssl specified, default to sslmode=require
        if ("supabase.co" in parts.netloc or "supabase.com" in parts.netloc) and not any(
            k in query_params for k in ("ssl", "sslmode")
        ):
            query_params["sslmode"] = ["require"]

        new_query = urlencode(query_params, doseq=True)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

    return url


DATABASE_URL = _normalize_url(settings.get_database_url())
_is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args: dict = {}
if _is_sqlite:
    connect_args = {"check_same_thread": False}
else:
    # Supabase Transaction Pooler (port 6543) / asyncpg
    # statement_cache_size=0 and ssl='require' are strictly required
    if "asyncpg" in DATABASE_URL:
        connect_args = {
            "statement_cache_size": 0,
            "ssl": "require",
        }
    elif "psycopg" in DATABASE_URL:
        connect_args = {
            "prepare_threshold": None,
        }

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=not _is_sqlite,
    pool_recycle=300 if not _is_sqlite else -1,
    connect_args=connect_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from app import models  # noqa: F401  (register mappings)

    # 1. Hard check for Supabase PostgreSQL connection (no silent failure)
    if not _is_sqlite:
        try:
            async with engine.connect() as test_conn:
                from sqlalchemy import text
                res = await test_conn.execute(text("SELECT 1"))
                res.scalar()
            print("\n=======================================================")
            print("✅ Connected to Supabase PostgreSQL")
            print(f"Target: {engine.url.host}:{engine.url.port}/{engine.url.database}")
            print("=======================================================\n")
            logger.info("✅ Connected to Supabase PostgreSQL: %s:%s/%s", engine.url.host, engine.url.port, engine.url.database)
        except Exception as exc:
            print("\n=======================================================")
            print("❌ CRITICAL: Failed to connect to Supabase PostgreSQL!")
            print(f"Target: {engine.url.host}:{engine.url.port}/{engine.url.database}")
            print(f"Error: {exc}")
            print("Check DATABASE_URL credentials, port (6543 for pooler), and password.")
            print("=======================================================\n")
            logger.critical("❌ Failed to connect to Supabase PostgreSQL: %s", exc)
            raise RuntimeError(f"Failed to connect to Supabase PostgreSQL: {exc}") from exc

    async with engine.begin() as conn:
        # 2. Create all missing tables in Supabase / SQLite
        await conn.run_sync(Base.metadata.create_all)

        # 3. Schema migrations & compatibility views
        if not _is_sqlite:
            # PostgreSQL / Supabase
            def _migrate_postgres(sync_conn):
                from sqlalchemy import text
                statements = [
                    # users
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS credits_balance INTEGER DEFAULT 50;",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id VARCHAR(36);",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(32);",
                    # tg_accounts
                    "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS user_id BIGINT;",
                    "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS session_string TEXT;",
                    "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS warmup_preset VARCHAR(24) DEFAULT 'optimal';",
                    "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS auto_warmup BOOLEAN DEFAULT FALSE;",
                    "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS daily_actions_reset_at TIMESTAMPTZ;",
                    # proxies
                    "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS user_id BIGINT;",
                    # dialogs
                    "ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS ai_auto_reply_enabled BOOLEAN DEFAULT TRUE;",
                    # telegram_orders
                    "ALTER TABLE telegram_orders ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'telegram';",
                    "ALTER TABLE telegram_orders ADD COLUMN IF NOT EXISTS source_url VARCHAR(500);",
                    # telegram_chat_targets
                    "ALTER TABLE telegram_chat_targets ADD COLUMN IF NOT EXISTS cooldown_minutes INTEGER DEFAULT 120;",
                    "ALTER TABLE telegram_chat_targets ADD COLUMN IF NOT EXISTS custom_text TEXT;",
                    "ALTER TABLE telegram_chat_targets ADD COLUMN IF NOT EXISTS auto_post_enabled BOOLEAN DEFAULT FALSE;",
                    "ALTER TABLE telegram_chat_targets ADD COLUMN IF NOT EXISTS next_post_at TIMESTAMPTZ;",
                    # Compatibility views for 'demos' and 'orders'
                    "CREATE OR REPLACE VIEW demos AS SELECT * FROM demo_sites;",
                    "CREATE OR REPLACE VIEW orders AS SELECT * FROM telegram_orders;",
                ]
                for stmt in statements:
                    try:
                        sync_conn.execute(text(stmt))
                    except Exception as exc:
                        logger.debug("PostgreSQL migration note for '%s': %s", stmt[:35], exc)

            await conn.run_sync(_migrate_postgres)
        else:
            # SQLite lightweight migrations
            def _migrate_columns(sync_conn):
                import sqlite3
                cursor = sync_conn.connection.cursor()

                # telegram_chat_targets
                cursor.execute("PRAGMA table_info(telegram_chat_targets)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                new_cols = [
                    ("cooldown_minutes", "INTEGER DEFAULT 120"),
                    ("custom_text", "TEXT"),
                    ("auto_post_enabled", "BOOLEAN DEFAULT 0"),
                    ("next_post_at", "DATETIME"),
                ]
                for col_name, col_def in new_cols:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE telegram_chat_targets ADD COLUMN {col_name} {col_def}")

                # telegram_orders
                cursor.execute("PRAGMA table_info(telegram_orders)")
                existing_order_cols = {row[1] for row in cursor.fetchall()}
                new_order_cols = [
                    ("source", "VARCHAR(32) DEFAULT 'telegram'"),
                    ("source_url", "VARCHAR(500)"),
                ]
                for col_name, col_def in new_order_cols:
                    if col_name not in existing_order_cols:
                        cursor.execute(f"ALTER TABLE telegram_orders ADD COLUMN {col_name} {col_def}")

                # users (if existing)
                cursor.execute("PRAGMA table_info(users)")
                existing_user_cols = {row[1] for row in cursor.fetchall()}
                if existing_user_cols:
                    new_user_cols = [
                        ("credits_balance", "INTEGER DEFAULT 50"),
                        ("referrer_id", "VARCHAR(36)"),
                        ("referral_code", "VARCHAR(32)"),
                    ]
                    for col_name, col_def in new_user_cols:
                        if col_name not in existing_user_cols:
                            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

                # tg_accounts (if existing)
                cursor.execute("PRAGMA table_info(tg_accounts)")
                existing_acc_cols = {row[1] for row in cursor.fetchall()}
                if existing_acc_cols:
                    new_acc_cols = [
                        ("session_string", "TEXT"),
                        ("warmup_preset", "VARCHAR(24) DEFAULT 'optimal'"),
                        ("auto_warmup", "BOOLEAN DEFAULT 0"),
                        ("daily_actions_reset_at", "DATETIME"),
                    ]
                    for col_name, col_def in new_acc_cols:
                        if col_name not in existing_acc_cols:
                            cursor.execute(f"ALTER TABLE tg_accounts ADD COLUMN {col_name} {col_def}")

                # dialogs (if existing)
                cursor.execute("PRAGMA table_info(dialogs)")
                existing_dlg_cols = {row[1] for row in cursor.fetchall()}
                if existing_dlg_cols:
                    new_dlg_cols = [
                        ("ai_auto_reply_enabled", "BOOLEAN DEFAULT 1"),
                    ]
                    for col_name, col_def in new_dlg_cols:
                        if col_name not in existing_dlg_cols:
                            cursor.execute(f"ALTER TABLE dialogs ADD COLUMN {col_name} {col_def}")

            await conn.run_sync(_migrate_columns)

    # 3. Check for automatic initial migration from SQLite to PostgreSQL if PostgreSQL is empty
    if not _is_sqlite:
        await _check_and_auto_import_from_sqlite()


async def _check_and_auto_import_from_sqlite() -> None:
    """If connected to PostgreSQL/Supabase and database is empty, automatically imports data from local SQLite parser.db."""
    sqlite_path = DATA_DIR / "parser.db"
    if not sqlite_path.exists():
        return

    try:
        from sqlalchemy import func, select
        from app.models import Lead, User

        async with SessionLocal() as session:
            user_count = await session.scalar(select(func.count(User.id)))
            lead_count = await session.scalar(select(func.count(Lead.id)))
            if (user_count or 0) > 0 or (lead_count or 0) > 0:
                # PostgreSQL already has data, no auto-import needed
                return

        logger.info("Fresh PostgreSQL/Supabase database detected. Starting auto-import from local SQLite...")
        from app.services.migration import import_sqlite_data_to_postgres
        imported = await import_sqlite_data_to_postgres(sqlite_path)
        logger.info("Auto-import completed successfully: %s", imported)
    except Exception as exc:
        logger.warning("Could not auto-import from SQLite to PostgreSQL: %s", exc)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
