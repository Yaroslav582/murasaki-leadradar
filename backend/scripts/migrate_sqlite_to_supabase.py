#!/usr/bin/env python3
"""CLI utility to migrate all Murasaki LeadRadar SQLite data into cloud Supabase PostgreSQL."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))


async def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite parser.db to Supabase PostgreSQL.")
    parser.add_argument(
        "--db-url",
        dest="db_url",
        help="Target PostgreSQL/Supabase connection string (defaults to DATABASE_URL in .env)",
        default=None,
    )
    parser.add_argument(
        "--sqlite-path",
        dest="sqlite_path",
        help="Path to SQLite parser.db (defaults to backend/data/parser.db)",
        default=str(backend_dir / "data" / "parser.db"),
    )
    args = parser.parse_args()

    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url

    from app.config import settings
    from app.db import init_db, DATABASE_URL, _is_sqlite
    from app.services.migration import import_sqlite_data_to_postgres

    print(f"Target Database URL: {DATABASE_URL}")
    if _is_sqlite:
        print("[!] Warning: Target is SQLite. To migrate to Supabase, set DATABASE_URL=postgresql+asyncpg://...")
        sys.exit(1)

    print("[1/3] Initializing schema and tables in Supabase...")
    await init_db()

    print(f"[2/3] Migrating data from SQLite ({args.sqlite_path})...")
    results = await import_sqlite_data_to_postgres(args.sqlite_path)

    print("[3/3] Migration summary:")
    for table, count in results.items():
        print(f"  - {table}: {count} records transferred")

    print("\n[+] Migration to Supabase completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
