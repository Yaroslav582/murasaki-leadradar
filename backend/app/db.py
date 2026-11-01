from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATA_DIR, settings


def _normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = _normalize_url(settings.database_url)
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=not _is_sqlite,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from app import models  # noqa: F401  (register mappings)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # SQLite lightweight migration for telegram tables
        if _is_sqlite:
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

            await conn.run_sync(_migrate_columns)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
