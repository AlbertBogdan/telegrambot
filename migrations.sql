-- Nutribot database schema for Supabase/PostgreSQL

-- Users table: one row per Telegram user
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    norm_b REAL NOT NULL CHECK (norm_b >= 0),
    norm_j REAL NOT NULL CHECK (norm_j >= 0),
    norm_u REAL NOT NULL CHECK (norm_u >= 0),
    onboarded BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Daily log table: one row per user per day
CREATE TABLE IF NOT EXISTS daily_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_b REAL NOT NULL DEFAULT 0,
    total_j REAL NOT NULL DEFAULT 0,
    total_u REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, date)
);

-- Index for calendar month queries
CREATE INDEX IF NOT EXISTS idx_daily_log_user_date
    ON daily_log (user_id, date);
