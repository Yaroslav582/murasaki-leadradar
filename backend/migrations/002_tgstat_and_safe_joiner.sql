-- ==============================================================================
-- Migration: 002_tgstat_and_safe_joiner.sql
-- Description: Worker accounts pool and join queue for TGStat parser & safe joiner
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql
-- ==============================================================================

-- 1. Enable UUID generator extensions if not yet present
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Worker accounts pool table (technical parser/joiner accounts)
CREATE TABLE IF NOT EXISTS worker_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(32) NOT NULL UNIQUE,
    session_string TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    warmup_stage INT NOT NULL DEFAULT 1 CHECK (warmup_stage IN (1, 2, 3)),
    joins_today INT NOT NULL DEFAULT 0,
    total_chats INT NOT NULL DEFAULT 0,
    flood_wait_until TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Join queue table (discovered channels/chats waiting for stealth joining)
CREATE TABLE IF NOT EXISTS join_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username_or_link VARCHAR(255) NOT NULL UNIQUE,
    tgstat_id BIGINT,
    category VARCHAR(100),
    members_count INT DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'joined', 'failed', 'skipped')),
    assigned_worker_id UUID REFERENCES worker_accounts(id) ON DELETE SET NULL,
    error_log TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- 4. High-performance indexes
CREATE INDEX IF NOT EXISTS idx_worker_accounts_active_flood 
ON worker_accounts (is_active, flood_wait_until, total_chats);

CREATE INDEX IF NOT EXISTS idx_join_queue_status_created 
ON join_queue (status, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_join_queue_username 
ON join_queue (username_or_link);

CREATE INDEX IF NOT EXISTS idx_join_queue_worker 
ON join_queue (assigned_worker_id);

-- 5. Stored function to reset joins_today counter once per day (Midnight UTC)
CREATE OR REPLACE FUNCTION reset_daily_joins()
RETURNS void AS $$
BEGIN
    UPDATE worker_accounts
    SET joins_today = 0,
        last_reset_date = CURRENT_DATE,
        updated_at = NOW()
    WHERE joins_today > 0 OR last_reset_date < CURRENT_DATE;
END;
$$ LANGUAGE plpgsql;

-- 6. (Optional) Supabase pg_cron schedule if pg_cron extension is enabled:
-- To enable pg_cron in Supabase: Database -> Extensions -> search "pg_cron" -> enable.
-- Then execute:
-- SELECT cron.schedule('reset-daily-joins-worker-accounts', '0 0 * * *', 'SELECT reset_daily_joins()');
