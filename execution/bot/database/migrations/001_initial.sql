-- Vyriy House Bot — Phase 1 schema
-- Tables: transactions (unified income/expense) + bot_sessions (conversation state)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Unified income & expense ledger
CREATE TABLE IF NOT EXISTS transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            VARCHAR NOT NULL CHECK (type IN ('income', 'expense')),
    date            DATE NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    property_id     VARCHAR,           -- gnizd | chaika | chaplia | sup | null
    platform        VARCHAR,           -- INST | BC | Airbnb | HutsHub | Direct | null
    counterparty    VARCHAR,           -- sender name (income) or vendor (expense)
    payment_type    VARCHAR,           -- Передоплата | Доплата | Оплата | Сапи
    account_type    VARCHAR,           -- Account | Cash
    category        VARCHAR,           -- expense only: Прибирання | Комунальні | …
    checkin_date    DATE,
    checkout_date   DATE,
    sup_duration    VARCHAR,           -- SUP rental duration label
    notes           TEXT,
    receipt_url     TEXT,              -- Google Drive link (expenses with receipts)
    source          VARCHAR,           -- ocr | manual | email_parser
    sheets_synced   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_date       ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_property   ON transactions(property_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type       ON transactions(type);
-- Partial index: only unsynced rows — makes retry job fast
CREATE INDEX IF NOT EXISTS idx_transactions_unsynced   ON transactions(sheets_synced) WHERE sheets_synced = FALSE;

-- Telegram conversation state machine
CREATE TABLE IF NOT EXISTS bot_sessions (
    chat_id     BIGINT PRIMARY KEY,
    user_id     BIGINT,
    state       VARCHAR,              -- e.g. 'income:awaiting_property'
    context     JSONB DEFAULT '{}',   -- all collected data for current flow
    updated_at  TIMESTAMP DEFAULT NOW()
);
