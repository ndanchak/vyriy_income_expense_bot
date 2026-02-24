# Vyriy House — Railway Application Architecture

**Document type:** Technical Architecture & Implementation Plan  
**Status:** Design only — no code written  
**Target stack:** Python · FastAPI · PostgreSQL · Railway · Claude Code  
**Last updated:** February 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Application Structure](#2-application-structure)
3. [Database Schema](#3-database-schema)
4. [Automation Modules](#4-automation-modules)
5. [Conversation State Machine](#5-conversation-state-machine)
6. [Google Sheets Bridge](#6-google-sheets-bridge)
7. [Environment Variables](#7-environment-variables)
8. [Implementation Plan](#8-implementation-plan)
9. [Claude Code Strategy](#9-claude-code-strategy)
10. [Cost Comparison](#10-cost-comparison)

---

## 1. System Overview

The Railway application is a single Python process that replaces all Make.com scenarios. It runs 24/7, responds to Telegram webhooks instantly (no polling delay), and owns a PostgreSQL database as the single source of truth for all business data — income, expenses, bookings, guests, cleaning, and operational state.

Unlike Make.com where each scenario is isolated, the Railway app shares state across all modules. The expense bot knows about bookings, the guest communication engine knows about payments, and the CRM module has full guest history — all without manual data bridging.

### 1.1 Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│  L1 — ENTRY POINTS                                      │
│  Telegram webhook · Email parser · Scheduled jobs       │
├─────────────────────────────────────────────────────────┤
│  L2 — PROCESSING (Handler Modules)                      │
│  income · expense · booking · guest_comms · crm         │
│  cleaning · reviews · pricing · analytics               │
├─────────────────────────────────────────────────────────┤
│  L3 — SERVICES                                          │
│  Google Vision OCR · Google Sheets · Google Calendar    │
│  APScheduler · IMAP email reader                        │
├─────────────────────────────────────────────────────────┤
│  L4 — DATA (PostgreSQL on Railway)                      │
│  transactions · bookings · guests · scheduled_jobs      │
│  bot_sessions · cleaning_tasks · properties             │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Key Advantages Over Make.com

| Capability | Make.com | Railway |
|---|---|---|
| Conversation state | Lost on scenario end | PostgreSQL — survives restarts |
| Response time | 15-min polling minimum | Instant webhook |
| Guest history / CRM | No cross-scenario memory | Full relational database |
| Cost at 10 properties | $29/mo | $5/mo (unchanged) |
| Complex logic | Visual builder limits | Full Python |
| Concurrent users | One flow at a time | Handles entire team simultaneously |

---

## 2. Application Structure

One Python project, deployed on Railway, connected to GitHub for auto-deploy on push.

### 2.1 Project Layout

```
vyriy-bot/
├── main.py                      # Entry point — starts bot, scheduler, webhook server
├── config.py                    # Environment variables, property constants
├── CLAUDE.md                    # Context file for Claude Code sessions
│
├── database/
│   ├── connection.py            # Async PostgreSQL connection pool (asyncpg)
│   ├── models.py                # SQLAlchemy table definitions
│   └── migrations/              # Alembic schema version files
│       ├── 001_initial.sql
│       └── 002_add_crm_tags.sql
│
├── handlers/                    # One file per automation module
│   ├── income.py                # Module 1: Income bot flow
│   ├── expense.py               # Module 2: Expense bot flow
│   ├── booking.py               # Module 3: Booking pipeline
│   ├── guest_comms.py           # Module 4: Guest communication sequences
│   ├── crm.py                   # Module 5: Guest profiles and re-engagement
│   ├── cleaning.py              # Module 6: Cleaning coordination
│   ├── reviews.py               # Module 7: Review requests and management
│   ├── pricing.py               # Module 8: Dynamic pricing logic
│   └── analytics.py             # Module 9: P&L reports, weekly digest
│
├── services/
│   ├── ocr.py                   # Google Vision API wrapper
│   ├── sheets.py                # Google Sheets read/write (gspread)
│   ├── calendar.py              # Google Calendar API
│   ├── email_reader.py          # IMAP reader for Airbnb/Booking.com emails
│   └── scheduler.py             # APScheduler setup and job management
│
├── utils/
│   ├── parsers.py               # Regex parsers: Monobank, receipts, booking emails
│   ├── formatters.py            # Message formatting and template rendering
│   └── state.py                 # State machine helpers
│
├── templates/
│   ├── uk/                      # Ukrainian message templates
│   └── en/                      # English message templates
│
├── requirements.txt
├── Dockerfile
└── railway.toml
```

### 2.2 Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Bot framework | python-telegram-bot v21 | Telegram webhook + inline keyboards |
| Web server | FastAPI | Webhook endpoint + health check |
| Database ORM | SQLAlchemy + asyncpg | PostgreSQL async queries |
| Scheduler | APScheduler | Persistent cron-like jobs |
| OCR | Google Vision API | Screenshot → text extraction |
| Sheets | gspread | Google Sheets read/write |
| Calendar | Google Calendar API | Booking/cleaning events |
| Email parsing | imaplib + beautifulsoup4 | Airbnb/Booking.com inbox |
| Env management | python-dotenv | Secrets and config |
| Migrations | Alembic | Schema versioning |
| Hosting | Railway Hobby ($5/mo) | 24/7 process + PostgreSQL plugin |

---

## 3. Database Schema

PostgreSQL on Railway (free tier included with Hobby plan, up to 1GB). All tables are defined here upfront so that any module can be added later without schema redesign.

### 3.1 `transactions` — income and expense unified

```sql
CREATE TABLE transactions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type            VARCHAR NOT NULL CHECK (type IN ('income', 'expense')),
  date            DATE NOT NULL,
  amount          DECIMAL(10,2) NOT NULL,
  property_id     VARCHAR,           -- gnizd | chaika | chaplia | sup | null
  platform        VARCHAR,           -- INST | BC | Airbnb | HutsHub | Direct | null
  counterparty    VARCHAR,           -- sender name (income) or vendor (expense)
  payment_type    VARCHAR,           -- Передоплата | Доплата | Оплата | Сапи
  account_type    VARCHAR,           -- Account | Cash
  category        VARCHAR,           -- expense: cleaning | utilities | maintenance | materials | marketing | other
  checkin_date    DATE,              -- income rows: booking check-in
  checkout_date   DATE,              -- income rows: booking check-out
  sup_duration    VARCHAR,           -- SUP rental duration if applicable
  booking_id      UUID REFERENCES bookings(id),
  notes           TEXT,              -- OCR purpose field or manual notes
  source          VARCHAR,           -- telegram_bot | email_parser | manual
  sheets_synced   BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_property ON transactions(property_id);
CREATE INDEX idx_transactions_type ON transactions(type);
```

### 3.2 `bookings`

```sql
CREATE TABLE bookings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform        VARCHAR NOT NULL,  -- Airbnb | BC | INST | HutsHub | Direct
  platform_ref    VARCHAR UNIQUE,    -- booking reference from platform
  property_id     VARCHAR NOT NULL,  -- gnizd | chaika | chaplia
  guest_id        UUID REFERENCES guests(id),
  checkin_date    DATE NOT NULL,
  checkout_date   DATE NOT NULL,
  nights          INTEGER,           -- auto-calculated on insert
  guests_count    INTEGER,
  total_price     DECIMAL(10,2),
  platform_fee    DECIMAL(10,2),
  net_revenue     DECIMAL(10,2),
  status          VARCHAR DEFAULT 'confirmed',  -- confirmed | cancelled | completed | no_show
  special_requests TEXT,
  comms_stage     VARCHAR,           -- current guest communication stage
  review_requested BOOLEAN DEFAULT FALSE,
  review_received  BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

### 3.3 `guests` — CRM

```sql
CREATE TABLE guests (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name         VARCHAR NOT NULL,
  phone             VARCHAR,
  email             VARCHAR,
  language          VARCHAR DEFAULT 'uk',  -- uk | en | pl | ru
  total_bookings    INTEGER DEFAULT 0,
  total_spent       DECIMAL(10,2) DEFAULT 0,
  first_stay        DATE,
  last_stay         DATE,
  is_repeat         BOOLEAN DEFAULT FALSE,
  preferred_property VARCHAR,
  tags              TEXT[],            -- ['vip', 'family', 'early_checkin']
  notes             TEXT,
  reengage_sent_at  TIMESTAMP,
  created_at        TIMESTAMP DEFAULT NOW()
);
```

### 3.4 `scheduled_jobs` — communication queue

```sql
CREATE TABLE scheduled_jobs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type    VARCHAR NOT NULL,   -- pre_arrival_7d | checkin_instructions | checkin_day |
                                  -- first_night | mid_stay | pre_checkout | post_checkout |
                                  -- review_followup | cleaning_reminder | reengage
  booking_id  UUID REFERENCES bookings(id),
  run_at      TIMESTAMP NOT NULL,
  status      VARCHAR DEFAULT 'pending',  -- pending | sent | skipped | failed
  sent_at     TIMESTAMP,
  payload     JSONB,              -- any data needed at execution time
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_jobs_run_at_status ON scheduled_jobs(run_at, status);
```

### 3.5 `bot_sessions` — conversation state

```sql
CREATE TABLE bot_sessions (
  chat_id     BIGINT PRIMARY KEY,   -- Telegram chat ID
  user_id     BIGINT,               -- Telegram user ID
  state       VARCHAR,              -- e.g. 'income:awaiting_property'
  context     JSONB DEFAULT '{}',   -- all collected data for current flow
  updated_at  TIMESTAMP DEFAULT NOW()
);
```

### 3.6 `properties` — configuration table

```sql
CREATE TABLE properties (
  id              VARCHAR PRIMARY KEY,  -- gnizd | chaika | chaplia
  display_name    VARCHAR NOT NULL,     -- Гніздечко | Чайка | Чапля
  address         TEXT,
  max_guests      INTEGER,
  wifi_name       VARCHAR,
  wifi_password   VARCHAR,
  entry_code      VARCHAR,
  checkin_time    VARCHAR DEFAULT '16:00',
  checkout_time   VARCHAR DEFAULT '11:00',
  airbnb_cal_url  VARCHAR,
  bc_listing_id   VARCHAR,
  cleaner_chat_id BIGINT,
  active          BOOLEAN DEFAULT TRUE
);
```

### 3.7 `cleaning_tasks`

```sql
CREATE TABLE cleaning_tasks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id      UUID REFERENCES bookings(id),
  property_id     VARCHAR,
  scheduled_date  DATE,
  scheduled_time  VARCHAR,
  cleaner_notified BOOLEAN DEFAULT FALSE,
  status          VARCHAR DEFAULT 'scheduled',  -- scheduled | in_progress | complete | issue
  completed_at    TIMESTAMP,
  issues_reported TEXT,
  cost            DECIMAL(10,2),
  created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## 4. Automation Modules

Each module is one handler file. They share the database but are otherwise independent — build, test, and deploy one at a time.

---

### Module 1: Income Bot (`handlers/income.py`)

**Replaces:** Make.com vyriy-income-bot.json (31 modules)  
**Trigger:** Photo message sent to the Telegram group

#### Flow

```
User sends Monobank screenshot
        ↓
bot receives photo → download to memory buffer
        ↓
Google Vision OCR → fullTextAnnotation.text
        ↓
parsers.py regex extraction:
  sender_name  → (?:Від|від)[:\s]+([^\n]+)
  amount       → ([\d\s]+[,.]?\d*)\s*(?:₴|грн|UAH)
  date         → (\d{2}[./]\d{2}[./]\d{4})
  purpose      → (?:Призначення|Коментар)[:\s]+([^\n]+)
        ↓
Save to bot_sessions: state=income:awaiting_property
context = { ocr fields, photo_file_id, message_id }
        ↓
Send InlineKeyboard: Гніздечко | Чайка | Чапля | SUP | Пропустити
        ↓
  ┌─ if SUP selected ──────────────────────────────────┐
  │  Ask duration: 1год | 2год | 3год | Інше           │
  └────────────────────────────────────────────────────┘
        ↓
Send InlineKeyboard: Передоплата | Доплата | Оплата | Пропустити
        ↓
Send InlineKeyboard: INST | BC | Airbnb | HutsHub | Прямий | Пропустити
        ↓
Send InlineKeyboard: Рахунок | Готівка
        ↓
Ask for dates (text input or Пропустити button)
        ↓
INSERT into transactions (type='income', all fields)
        ↓
sheets.py → append row to Доходи tab
        ↓
Send confirmation message to group
        ↓
Delete bot_sessions row → return to idle
```

#### State advantage over Make.com

In Make.com, if the scenario fails mid-flow, all context is lost. In Railway, `bot_sessions` persists in PostgreSQL. If the server restarts between steps, the user continues from exactly where they left off on next message.

---

### Module 2: Expense Bot (`handlers/expense.py`)

**Trigger A:** `/витрата` command (with optional inline params)  
**Trigger B:** Photo message (receipt) → OCR extracts amount and vendor

#### Flow

```
Trigger A: /витрата прибирання Гніздечко 850
  → parse inline: category=cleaning, property=gnizd, amount=850
  → skip to confirmation if all fields present

Trigger B: receipt photo
  → OCR → extract amount, vendor, date
  → state=expense:awaiting_category

InlineKeyboard: Прибирання | Комунальні | Обслуговування
                Матеріали | Маркетинг | Інше
        ↓
InlineKeyboard: Гніздечко | Чайка | Чапля | Всі | Пропустити
        ↓
InlineKeyboard: Готівка | Рахунок
        ↓
INSERT into transactions (type='expense')
        ↓
sheets.py → append row to Витрати tab
        ↓
Confirmation message
```

#### Accessible by

Nestor, Іра, Михайло — all in the Telegram group. Role is inferred from Telegram user_id if needed (e.g., Михайло's entries auto-tag maintenance category).

---

### Module 3: Booking Pipeline (`handlers/booking.py`)

**Trigger:** IMAP email polling every 5 minutes on Gmail  
**Also:** Manual `/бронювання` command for Instagram/HutsHub/direct bookings

#### Email parsing targets

```
Airbnb sender:      automated@airbnb.com
  Subject pattern:  "Reservation confirmed"
  Fields to parse:  guest name, check-in/out, property, amount, confirmation code

Booking.com sender: noreply@booking.com
  Subject pattern:  "New reservation"
  Fields to parse:  guest name, dates, property, amount, booking number
```

#### Flow

```
IMAP scan every 5min → filter by sender + subject pattern
        ↓
Parse HTML email → extract all booking fields
        ↓
Duplicate check: SELECT WHERE platform_ref = ?
  → if exists: skip (idempotent)
        ↓
Guest lookup: SELECT FROM guests WHERE full_name ILIKE ?
  → if match: link to existing guest, update last_stay
  → if no match: INSERT new guest record
        ↓
INSERT into bookings (linked to guest_id)
        ↓
Schedule communication jobs:
  INSERT scheduled_jobs for each of 9 touch points
  (run_at = checkin - offset for each type)
        ↓
Google Calendar: create event, color-coded by property
        ↓
Telegram group notification: booking summary card
```

#### Manual booking command

```
/бронювання
  → ask platform: INST | HutsHub | Прямий
  → ask property
  → ask guest name + phone
  → ask dates
  → ask amount
  → INSERT booking + schedule all jobs
```

---

### Module 4: Guest Communications Engine (`handlers/guest_comms.py`)

**Trigger:** APScheduler job runs every 15 minutes  
Queries: `SELECT FROM scheduled_jobs WHERE run_at <= NOW() AND status = 'pending'`

No Make.com polling cost. One background thread. Handles all properties simultaneously.

#### Scheduled job types

| Job Type | Timing | Content |
|---|---|---|
| `booking_confirmation` | Immediate on booking | Welcome + property highlights + what to expect |
| `pre_arrival_7d` | 7 days before checkin | Local tips, restaurants, weather, transport |
| `checkin_instructions` | 48h before checkin | Full guide: address, entry code, WiFi, parking |
| `checkin_day` | Check-in day 12:00 | Arrival check — on track? Need anything? |
| `first_night` | Check-in day 20:00 | Settled in OK? Any issues? |
| `mid_stay` | Day 2 morning 10:00 | Check-in, offer linen change for 7+ night stays |
| `pre_checkout` | Day before 18:00 | Checkout reminder + instructions |
| `post_checkout` | 4h after checkout | Thank you + review request with link |
| `review_followup` | 7 days after checkout | Gentle reminder if no review received |

#### Language selection

```python
def get_template(job_type, language):
    # templates/uk/{job_type}.txt  → default
    # templates/en/{job_type}.txt  → if guest.language == 'en'
    # templates/pl/{job_type}.txt  → if guest.language == 'pl'
```

Language is stored on the `guests` record. Can be set manually via `/мова [guest_name] [uk|en|pl]` command or detected from phone number prefix.

#### Message delivery

For Airbnb and Booking.com bookings: messages go via platform messaging API (or email fallback). For direct/Instagram bookings: messages go to phone via WhatsApp link or manual Telegram prompt to Іра.

---

### Module 5: CRM / Guest Database (`handlers/crm.py`)

Not a standalone trigger — runs as part of Modules 3 and 4. Builds guest intelligence automatically.

#### Functions

| Function | Logic |
|---|---|
| Guest creation | On new booking: normalize name → INSERT if no match found |
| Repeat detection | `SELECT FROM guests WHERE full_name ILIKE ?` → set `is_repeat=true`, update `total_bookings` |
| Lifetime value | Auto-calculated: `SUM(transactions.amount) WHERE booking.guest_id = ?` |
| VIP tagging | Auto-tag if `total_bookings >= 3` OR `total_spent > 15000 UAH` |
| Preferred property | Most frequent property from booking history |
| Re-engagement | Weekly APScheduler job: guests where `last_stay < 6 months ago`, no future booking → send message |

#### Team commands

```
/гість [name]     → lookup full guest profile: bookings, total spent, tags, notes
/тег [name] [tag] → manually add tag to guest (vip, family, corporate, etc.)
/нотатка [name] [text] → add manual note to guest record
```

---

### Module 6: Cleaning Coordination (`handlers/cleaning.py`)

**Trigger:** Booking confirmed (runs at end of Module 3 pipeline)

#### Flow

```
Booking confirmed
        ↓
Calculate cleaning window:
  checkout_time = 11:00
  cleaning_start = 11:30
  estimated_duration = 3 hours
  next_checkin = booking.checkin_time (16:00 default)
        ↓
INSERT cleaning_tasks
        ↓
Telegram message to cleaner (by property.cleaner_chat_id):
  "Прибирання [property] [date] з 11:30
   Наступний заїзд: [guest_name] о 16:00
   Особливі побажання: [special_requests]"
        ↓
Day of checkout, 2h before:
  Reminder to cleaner
  Check if guest confirmed checkout
        ↓
Cleaner replies /готово
  → ask for issues (Yes/No keyboard)
  → if issues: text input → create maintenance alert → notify Михайло
  → log completion time
  → UPDATE booking status → 'ready'
  → if amount provided: INSERT expense (type='expense', category='cleaning')
```

---

### Module 7: Review Management (`handlers/reviews.py`)

**Trigger:** `post_checkout` and `review_followup` jobs from scheduled_jobs table  
**Also:** Owner can trigger manually via `/відгук [booking_id]`

#### Flow

```
post_checkout job fires (4h after checkout)
        ↓
Send thank-you + review request
  → platform-specific review link
  → UPDATE bookings SET review_requested=TRUE
        ↓
7 days: check if review_received=FALSE
  → send review_followup message
        ↓
14 days: if still no review → mark 'no_review', stop
```

#### Negative review alert

When a review below 4.5 is detected (via manual report or future API scraping), immediately notify owner via Telegram with full review text and draft response.

---

### Module 8: Dynamic Pricing (`handlers/pricing.py`)

**Trigger:** APScheduler daily job at 06:00

```
Gather data:
  - current bookings for next 90 days (occupancy per date)
  - day of week for each unbooked date
  - upcoming events in Lviv (manual config or scraping)
  - seasonal multiplier from config

Apply pricing matrix:
  base_rate × seasonal_mult × dow_mult × occupancy_adj × event_mult

Flag significant changes (>10%) → send to owner for approval
Minor changes (<10%) → auto-apply via iCal or API

Log all price changes with rationale
```

Pricing rules stored in `config.py` as a data structure — easy to update without code changes.

---

### Module 9: Analytics & Reporting (`handlers/analytics.py`)

| Report | Frequency | Delivery |
|---|---|---|
| Weekly digest | Monday 09:00 | Telegram group message |
| Monthly P&L | 1st of month 09:00 | Telegram + Google Sheets tab |
| Cash flow alert | Daily 08:00 | Telegram if projected cash < threshold |
| Occupancy gap alert | Daily 06:00 | Flag unbooked dates within 14 days |
| On-demand | `/звіт` command | Instant current month summary |

#### Weekly digest content

```
📊 Тиждень [dates]

💰 Дохід: X,XXX ₴ (▲/▼ X% vs минулий тиждень)
🏠 Бронювань: X
📅 Завантаженість: XX%
⭐ Середній рейтинг: X.X

По об'єктах:
  Гніздечко: X,XXX ₴ · X ночей
  Чайка: X,XXX ₴ · X ночей
  Чапля: X,XXX ₴ · X ночей
```

---

## 5. Conversation State Machine

The core advantage of Railway over Make.com. Every multi-step bot flow uses a state machine stored in PostgreSQL. The bot always knows where each user is in any flow, survives restarts, and handles multiple team members simultaneously in the same group.

### 5.1 State Naming Convention

```
Format: {module}:{current_step}

Income states:
  income:awaiting_property        user sees property keyboard
  income:awaiting_payment_type    user sees payment type keyboard
  income:awaiting_platform        user sees platform keyboard
  income:awaiting_account_type    cash or account keyboard
  income:awaiting_dates           waiting for text input or skip
  income:awaiting_sup_duration    SUP flow: waiting for duration choice

Expense states:
  expense:awaiting_category
  expense:awaiting_property
  expense:awaiting_payment_method

Booking states (manual entry):
  booking:awaiting_platform
  booking:awaiting_property
  booking:awaiting_guest_name
  booking:awaiting_dates
  booking:awaiting_amount

Idle: no row in bot_sessions → bot ready for new command
```

### 5.2 Context Object

The `context` JSONB column holds everything collected so far in the current flow:

```json
{
  "ocr_sender": "Коваленко Марина",
  "ocr_amount": 2400,
  "ocr_date": "19.02.2026",
  "ocr_purpose": "оренда котеджу",
  "property": "gnizd",
  "payment_type": "Передоплата",
  "platform": null,
  "account_type": "Account",
  "checkin": null,
  "checkout": null,
  "message_id": 12345,
  "photo_file_id": "AgACAgIAAxkBAAI..."
}
```

At any step, pressing `/скасувати` → DELETE from bot_sessions → return to idle.

### 5.3 Concurrent Users

Multiple team members can use the bot simultaneously. Each has their own `bot_sessions` row keyed by `chat_id`. No cross-contamination possible.

---

## 6. Google Sheets Bridge

The Railway app writes to Google Sheets in addition to PostgreSQL. The team continues using the spreadsheet they know during transition. PostgreSQL is the source of truth for analytics; Sheets is the human-readable view.

### 6.1 Write Targets

| Sheet Tab | Written By | Columns |
|---|---|---|
| Доходи | income handler | Date, Day#, Amount, Property, Platform, Guest, Nights, Check-in, Check-out, Payment Type, Account, Notes, Month |
| Витрати | expense handler | Date, Category, Amount, Property, Vendor, Payment Method, Notes |
| Бронювання | booking pipeline | Booking ID, Platform, Guest, Dates, Nights, Revenue, Status |
| Прибирання | cleaning handler | Date, Property, Cleaner, Status, Cost, Issues |

### 6.2 Retry Logic

`sheets_synced` flag on each transaction row. If the Sheets write fails (rate limit, network), a background job retries all `sheets_synced=FALSE` rows every hour. Data is never lost — PostgreSQL holds it regardless.

---

## 7. Environment Variables

Set in Railway dashboard → Variables tab. Never stored in code.

```
TELEGRAM_BOT_TOKEN          from BotFather
TELEGRAM_GROUP_CHAT_ID      your group's chat ID
TELEGRAM_OWNER_CHAT_ID      Nestor's personal chat ID for alerts

DATABASE_URL                auto-set by Railway PostgreSQL plugin

GOOGLE_VISION_API_KEY       from console.cloud.google.com
GOOGLE_SHEETS_CREDS_JSON    service account JSON, base64 encoded
GOOGLE_SHEETS_ID            your main spreadsheet ID
GOOGLE_CALENDAR_ID          main calendar ID

GMAIL_ADDRESS               inbox for booking platform emails
GMAIL_APP_PASSWORD          Google app-specific password (not main password)

WEBHOOK_SECRET              random string for Telegram webhook validation
WEBHOOK_URL                 https://your-app.railway.app/webhook

PROPERTY_IDS                gnizd,chaika,chaplia
```

All property-specific config (addresses, entry codes, cleaner chat IDs, WiFi) lives in the `properties` database table — not in environment variables. Adding a new property = INSERT one row, no config changes.

---

## 8. Implementation Plan

Built incrementally with Claude Code. Each phase is independently deployable. Make.com runs in parallel until each module is validated — nothing breaks existing operations during the build.

---

### Phase 1 — Foundation + Income Bot

**Duration:** Week 1–2  
**Delivers:** Railway app running, income tracking working in production

**Tasks:**
- Set up Railway project, connect PostgreSQL plugin, connect GitHub repo for auto-deploy
- Create full database schema (all tables from Section 3 — define once, use forever)
- Build `main.py` — FastAPI webhook server + bot initialization + scheduler startup
- Build `database/connection.py` — async connection pool
- Build `utils/state.py` — state machine get/set/clear helpers
- Build `services/ocr.py` — Google Vision wrapper (from existing Make.com JSON blueprint logic)
- Build `utils/parsers.py` — Monobank regex patterns (same as current Make.com module 6b)
- Build `handlers/income.py` — full income flow (Section 4, Module 1)
- Build `services/sheets.py` — Доходи tab write
- Deploy and test with real Monobank screenshots in the group
- Run in parallel with Make.com income scenario — compare outputs for 1 week
- Disable Make.com income scenario once validated

**Success criteria:** Income recorded in DB and Sheets identically to Make.com, zero data loss, state survives bot restart mid-flow.

---

### Phase 2 — Expense Bot + Booking Pipeline

**Duration:** Week 3–4  
**Delivers:** Full financial tracking automated, bookings flowing into DB

**Tasks:**
- Build `handlers/expense.py` — command + receipt OCR flow (Section 4, Module 2)
- Add Витрати tab write to `services/sheets.py`
- Build `services/email_reader.py` — IMAP connection, Airbnb + Booking.com email parsers
- Build `handlers/booking.py` — full pipeline including guest lookup/create (Section 4, Module 3)
- Build `services/calendar.py` — Google Calendar event creation
- Build `services/scheduler.py` — APScheduler setup with job persistence
- Integrate scheduled_jobs INSERT into booking pipeline (all 9 touch points per booking)
- Test full booking flow: email arrives → DB → Calendar → Telegram notification
- Disable Make.com booking scenarios once validated

**Success criteria:** All new bookings auto-appear in DB, Calendar, and Telegram. Expenses log correctly from both command and photo.

---

### Phase 3 — Guest Communications Engine

**Duration:** Week 5–6  
**Delivers:** Full automated guest communication running without manual intervention

**Tasks:**
- Build `handlers/guest_comms.py` — scheduler job executor (Section 4, Module 4)
- Build all 9 message templates in `templates/uk/` and `templates/en/`
- Build `utils/formatters.py` — template rendering with booking data substitution
- Implement language detection logic
- Add `/пропустити` and manual override commands per job type
- Add `/повідомлення [booking_id] [job_type]` command for manual trigger
- Test complete sequence on a real booking end-to-end (all 9 touch points)
- Disable Make.com guest communication scenarios

**Success criteria:** Guest receives all 9 messages at correct times, in correct language, with correct property-specific details, without any manual action from the team.

---

### Phase 4 — CRM + Cleaning + Analytics

**Duration:** Week 7–9  
**Delivers:** Full operational system — Make.com fully retired

**Tasks:**
- Build `handlers/crm.py` — repeat detection, VIP tagging, re-engagement job (Section 4, Module 5)
- Build `/гість`, `/тег`, `/нотатка` lookup commands
- Build `handlers/cleaning.py` — full coordination flow (Section 4, Module 6)
- Build `handlers/reviews.py` — post-checkout + followup (Section 4, Module 7)
- Build `handlers/analytics.py` — weekly digest + monthly P&L + on-demand `/звіт` (Section 4, Module 9)
- Build cash flow and occupancy gap alerts
- Full system testing: simulate complete guest lifecycle from booking to review
- Make.com fully disabled

**Success criteria:** Zero manual intervention required for any routine operational task. Team only touches the bot for expense logging and issue handling.

---

### Phase 5 — Pricing + Advanced Features

**Duration:** Month 3+  
**Delivers:** Revenue optimization, system hardened for scale

**Tasks:**
- Build `handlers/pricing.py` — daily pricing job (Section 4, Module 8)
- Build maintenance tracking (issue reporting from guests via Telegram command)
- Add multi-property analytics (portfolio view)
- Performance optimization as booking volume grows
- Monitoring: error alerting to owner if any scheduled job fails 3x in a row
- Adding new properties: INSERT into `properties` table, zero code changes required

---

## 9. Claude Code Strategy

Claude Code is the developer for this project. Sessions are focused, one module at a time. The `CLAUDE.md` file in the project root is fed to Claude Code at session start so it has full context about the business, the architecture, and what's already built.

### 9.1 CLAUDE.md Structure

```markdown
# Vyriy House Bot — Claude Code Context

## Business
Vacation rental business, 3 properties near Lviv.
Team: Nestor (owner), Іра (operations), Михайло (maintenance), cleaners.
Telegram group is the central operational hub.

## What's built (update after each phase)
- [x] Phase 1: Income bot
- [ ] Phase 2: Expense + Booking

## Architecture
See ARCHITECTURE.md for full system design.

## Key decisions
- PostgreSQL is source of truth, Sheets is human-readable mirror
- All property config in DB, not env vars
- State machine uses bot_sessions table
- APScheduler for all time-based jobs (not cron)

## Coding standards
- Async everywhere (asyncpg, python-telegram-bot v21 async)
- No hardcoded strings — templates in /templates/, config in config.py
- Every DB write has error handling + retry logic
- Log all errors to Telegram owner chat
```

### 9.2 Session Workflow

1. Open Claude Code in the `vyriy-bot/` project directory
2. State the specific task: `"Build handlers/expense.py as described in the architecture doc"`
3. Claude Code reads CLAUDE.md + existing code for context
4. Claude Code writes the module, runs syntax checks, fixes errors
5. You test in the actual Telegram group
6. Claude Code fixes any issues found
7. Commit → Railway auto-deploys via GitHub connection

### 9.3 Estimated Build Cost

| Phase | Estimated session length | Approximate cost |
|---|---|---|
| Phase 1: Foundation + income bot | 3–4 hours | ~$15–20 |
| Phase 2: Expense + booking pipeline | 3–4 hours | ~$15–20 |
| Phase 3: Guest communications | 2–3 hours | ~$10–15 |
| Phase 4: CRM + cleaning + analytics | 3–4 hours | ~$15–20 |
| Ongoing: bug fixes and iterations | 1–2h / month | ~$5–10/mo |
| New feature on request | 1–2 hours | ~$5–10 |
| **Total one-time build cost** | | **~$55–75** |

---

## 10. Cost Comparison

### Monthly running cost

| | Make.com now (3 props) | Make.com at 7 props | Railway (any scale) |
|---|---|---|---|
| Platform cost | $9/mo | $18/mo | $5/mo |
| Developer cost | $0 | $0 | ~$5–10/mo (Claude Code) |
| **Total monthly** | **$9/mo** | **$18/mo** | **$10–15/mo** |
| Conversation state | ✗ | ✗ | ✓ PostgreSQL |
| Response time | 15min polling | 15min polling | Instant webhook |
| Guest CRM / history | ✗ | ✗ | ✓ Full database |
| Cost at 10 properties | $29/mo | $29/mo | $10–15/mo |
| Cost at 20 properties | $79/mo | $79/mo | $10–15/mo (unchanged) |

### One-time cost

| | Make.com | Railway |
|---|---|---|
| Build cost | $0 | ~$70 (Claude Code sessions) |
| Break-even vs Make.com $18 plan | — | ~10 months |
| Break-even vs Make.com $29 plan | — | ~4 months |

### Recommendation

Stay on Make.com for Phase 1 of the business (now through ~property #4). Begin Railway build when either:
- Make.com plan would jump to $18/mo (property #4 threshold), OR
- A feature is needed that Make.com cannot do elegantly (persistent CRM, instant response, complex state)

Whichever comes first — probably 4–6 months from now. The architecture is ready. Claude Code makes the build straightforward.

---

*Architecture document — design only, no code. Ready for Claude Code implementation phase by phase.*
