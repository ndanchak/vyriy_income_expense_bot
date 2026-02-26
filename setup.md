# Vyriy House Bot — Deployment & Usage Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Telegram Bot Setup](#telegram-bot-setup)
3. [Google Cloud Setup](#google-cloud-setup)
4. [Google Sheets Setup](#google-sheets-setup)
5. [Google Drive Setup](#google-drive-setup)
6. [Local Development](#local-development)
7. [Railway Deployment (Production)](#railway-deployment-production)
8. [Verify Deployment](#verify-deployment)
9. [How to Use the Bot](#how-to-use-the-bot)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- A Telegram account
- A Google account (for Cloud Console, Sheets, Drive)
- A [Railway](https://railway.app) account (free tier is fine for low traffic)
- Git installed locally
- Python 3.12+ (for local development only)

---

## Telegram Bot Setup

### Create the bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. "Vyriy House Bot")
4. Choose a username (e.g. `vyriy_house_bot`)
5. Copy the **bot token** — save it, you'll need it later

### Get group chat ID

1. Add the bot to your Telegram work group
2. Send any message in the group
3. Open this URL in a browser (replace `<TOKEN>` with your bot token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. Find `"chat":{"id":-100XXXXXXXXXX}` — this negative number is your **TELEGRAM_GROUP_CHAT_ID**

### Get owner's personal chat ID

1. Send any message directly to the bot (not in a group)
2. Open the same `getUpdates` URL
3. Find the `"chat":{"id":XXXXXXXXX}` from the direct message — this is your **TELEGRAM_OWNER_CHAT_ID**

> **Security note:** The bot authorizes by **chat ID**, not by user ID. In the group chat, all members (Nestor, Ihor, Ira) can use the bot. The owner's private chat allows Nestor to use the bot 1-on-1. Messages from any other chat are silently ignored.

---

## Google Cloud Setup

### Create project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it "Vyriy House Bot" → Create

### Enable APIs

In the new project, go to **APIs & Services → Library** and enable:

1. **Cloud Vision API** — for Monobank screenshot OCR
2. **Google Sheets API** — for writing income/expense rows
3. **Google Drive API** — for receipt file uploads

### Create Vision API key

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → API Key**
3. Copy the key — this is your **GOOGLE_VISION_API_KEY**
4. (Recommended) Click **Restrict key** → restrict to "Cloud Vision API" only

### Create Service Account (for Sheets + Drive)

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → Service Account**
3. Name: `vyriy-bot-sheets` → Create
4. Role: skip (no role needed at project level) → Continue → Done
5. Click the newly created service account email
6. Go to **Keys** tab → **Add Key → Create new key → JSON**
7. A `.json` file downloads — this is your service account key

### Encode the service account key to base64

Run in terminal:

```bash
base64 -i ~/Downloads/vyriy-bot-sheets-XXXXX.json | tr -d '\n'
```

Copy the entire output — this is your **GOOGLE_SHEETS_CREDS_JSON** value.

**Keep the original JSON file safe. Do NOT commit it to git.**

---

## Google Sheets Setup

### Create the spreadsheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new spreadsheet
2. Name it "Vyriy House — Фінанси"
3. Copy the spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
   This is your **GOOGLE_SHEETS_ID**

### Share with the service account

1. Click **Share** on the spreadsheet
2. Paste the service account email (e.g. `vyriy-bot-sheets@your-project.iam.gserviceaccount.com`)
3. Give it **Editor** access
4. Uncheck "Notify people" → Share

### Create "Доходи" tab (Income)

Rename the default "Sheet1" tab to **Доходи** (exact Ukrainian spelling). Add these headers in row 1:

| Col | Header |
|-----|--------|
| A1 | Date |
| B1 | Day# |
| C1 | Amount |
| D1 | Property |
| E1 | Platform |
| F1 | Guest Name |
| G1 | Nights |
| H1 | Check-in |
| I1 | Check-out |
| J1 | Payment Type |
| K1 | Account Type |
| L1 | Notes |
| M1 | Month |

> Columns B (Day#) and G (Nights) contain your own formulas — the bot leaves them empty.

### Create "Витрати" tab (Expenses)

Create a second tab named **Витрати** (exact Ukrainian spelling). Add these headers in row 1:

| Col | Header |
|-----|--------|
| A1 | Date |
| B1 | Category |
| C1 | Amount |
| D1 | Description |
| E1 | Payment Method |
| F1 | Paid By |
| G1 | Receipt Link |
| H1 | Vendor |
| I1 | Property |
| J1 | Notes |

---

## Google Drive Setup

### Create a receipts folder

1. Go to [Google Drive](https://drive.google.com)
2. Create a new folder named "Vyriy Receipts"
3. Open the folder — copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_HERE
   ```
   This is your **GOOGLE_DRIVE_FOLDER_ID**

### Share with the service account

1. Right-click the folder → Share
2. Paste the service account email
3. Give **Editor** access → Share

---

## Local Development

### Install PostgreSQL

```bash
# macOS with Homebrew
brew install postgresql@16
brew services start postgresql@16
```

### Create the database

```bash
createdb vyriy_dev
```

> The bot runs migrations automatically on startup — you don't need to run SQL files manually.

### Create `.env` file

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCDEF...
TELEGRAM_GROUP_CHAT_ID=-100XXXXXXXXXX
TELEGRAM_OWNER_CHAT_ID=XXXXXXXXX

# Database (local)
DATABASE_URL=postgresql://localhost:5432/vyriy_dev

# Google Vision OCR
GOOGLE_VISION_API_KEY=AIzaSy...

# Google Sheets
GOOGLE_SHEETS_CREDS_JSON=ewogICJ0eXBlIj...
GOOGLE_SHEETS_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz

# Google Drive
GOOGLE_DRIVE_FOLDER_ID=1XyZ...

# Webhook (leave WEBHOOK_URL empty for local polling mode)
WEBHOOK_SECRET=<generate with command below>
WEBHOOK_URL=
```

Generate the webhook secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Install dependencies and run

```bash
cd execution/bot
pip install -r requirements.txt
uvicorn main:api --host 0.0.0.0 --port 8000 --reload
```

With `WEBHOOK_URL` empty, the bot runs in **polling mode** — no ngrok needed for local development.

> **Optional:** If you want webhook mode locally, install ngrok (`brew install ngrok`), run `ngrok http 8000`, and set `WEBHOOK_URL=https://abcd-1234.ngrok-free.app` in `.env`.

---

## Railway Deployment (Production)

### Step 1: Push code to GitHub

Make sure your code is in a GitHub repository. The bot code lives in `execution/bot/` with its own `Dockerfile` and `railway.toml`.

### Step 2: Create Railway project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **New Project → Deploy from GitHub repo**
3. Select your repository
4. Set the **Root Directory** to `execution/bot` (important — this is where the Dockerfile lives)
5. Railway will detect the Dockerfile automatically

### Step 3: Add PostgreSQL

1. In your Railway project, click **New → Database → Add PostgreSQL**
2. Railway auto-sets `DATABASE_URL` in your service — no manual config needed
3. The bot runs both migrations (`001_initial.sql` and `002_expense_refactor.sql`) automatically on startup

### Step 4: Set environment variables

In your Railway service, go to **Variables** tab and add:

| Variable | Value | Notes |
|----------|-------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token | From BotFather |
| `TELEGRAM_GROUP_CHAT_ID` | `-100XXXXXXXXXX` | Your group chat |
| `TELEGRAM_OWNER_CHAT_ID` | `XXXXXXXXX` | Nestor's private chat |
| `GOOGLE_VISION_API_KEY` | `AIzaSy...` | Cloud Vision API key |
| `GOOGLE_SHEETS_CREDS_JSON` | `ewogICJ0eXBlIj...` | Base64 service account |
| `GOOGLE_SHEETS_ID` | `1AbCdEf...` | Spreadsheet ID |
| `GOOGLE_DRIVE_FOLDER_ID` | `1XyZ...` | Drive folder ID |
| `WEBHOOK_SECRET` | `<64-char hex>` | Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `WEBHOOK_URL` | `https://your-service.up.railway.app` | Your Railway public URL (must be HTTPS) |

> **Do NOT set `DATABASE_URL`** — Railway provides it automatically from the PostgreSQL addon.

### Step 5: Get your Railway public URL

1. Go to your service's **Settings → Networking**
2. Under **Public Networking**, click **Generate Domain**
3. Copy the URL (e.g. `https://vyriy-bot-production.up.railway.app`)
4. Set it as `WEBHOOK_URL` in Variables

### Step 6: Deploy

Railway auto-deploys on push to main. After deploy:

1. Check the deploy logs for `Vyriy House Bot started successfully`
2. Visit `https://your-service.up.railway.app/health` — should return `{"status":"ok"}`
3. Send a test message to the Telegram group

### Redeployment

Just push to your main branch — Railway redeploys automatically. You can also trigger manual deploys from the Railway dashboard.

---

## Verify Deployment

After deploying, run through these checks:

| Test | What to do | Expected result |
|------|-----------|-----------------|
| Health check | Visit `https://your-url/health` | `{"status":"ok"}` |
| Webhook | Run `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` | Shows your URL, no errors |
| Income (OCR) | Send a Monobank screenshot to the group | Bot replies with parsed amount + property buttons |
| Income (manual) | Send `/income` in the group | Bot asks for amount |
| Expense (interactive) | Send `/expense` in the group | Bot shows 14 category buttons |
| Expense (fast) | Send `/expense Laundry;500;Towels;Nestor` | Bot confirms immediately |
| Cancel | Start any flow, then send `/cancel` | Bot cancels and clears session |
| Google Sheets | Check "Доходи" and "Витрати" tabs | New rows appear after completing flows |
| Authorization | Message bot from an unknown account | Bot does not respond |

---

## How to Use the Bot

### Available Commands

| Command | Description |
|---------|-------------|
| `/income` | Start manual income entry |
| `/expense` | Start interactive expense entry |
| `/expense Category;Amount;Description;Paid By` | Fast expense entry (one-liner) |
| `/cancel` | Cancel current operation |
| `/start` | Show available commands |
| `/help` | Show detailed usage instructions |

### Recording Income (Screenshot — Main Flow)

1. **Send a Monobank payment screenshot** to the group chat
2. Bot runs OCR, extracts amount, sender, date, purpose
3. Bot shows **property buttons** — select one or more (multi-select):
   - Гніздечко, Чайка, Чапля — vacation properties
   - SUP Rental — paddle board rental
   - Tap to toggle ✅, then press "Підтвердити"
4. **Payment type**: Передоплата / Доплата / Оплата (skip for SUP — auto-set to "Сапи")
5. **Platform**: Website / Instagram / Booking / HutsHub / AirBnB / Phone / Return
6. **Account type**: Account / Cash / Nestor Account (skip for SUP — auto-detected)
7. **Dates**: Enter check-in/check-out (format: `ЧЕК-ІН: 22.02.2026` `ЧЕК-АУТ: 25.02.2026`) or skip
8. Bot saves to database + Google Sheets "Доходи" tab, shows confirmation

> **Team handoff:** Any team member can continue another member's session. E.g., Ihor sends a screenshot, Ira presses the buttons.

### Recording Income (Manual)

1. Send `/income`
2. Enter **amount** (e.g. `2400` or `1 500,50`)
3. Enter **guest name**
4. Continue from step 3 of the screenshot flow (property → payment → platform → etc.)

### Recording Expenses (Interactive)

1. Send `/expense`
2. Select **category** (14 options):
   - Laundry, Guest Amenities, Utilities, Marketing, Management Fee, Maintenance, Capital Expenses, Commissions, Cleaning & Admin, Chemicals, Software, Depreciation fund, Taxes, Other
3. Enter **amount**
4. Enter **description** (free text)
5. Select **payment method**: Cash / Bank Transfer
6. Select **paid by**: Nestor / Ihor / Ira / Other / Account
7. **Receipt link** (optional): paste a Google Drive URL, or press Skip
8. Bot saves to database + Google Sheets "Витрати" tab, shows confirmation

### Recording Expenses (Fast One-Liner)

```
/expense Laundry;850;Towel washing service;Nestor
```

Format: `/expense Category;Amount;Description;Paid By`

- **Category** — case-insensitive, partial match works (e.g. `laun` = Laundry)
- **Amount** — number (e.g. `850` or `1200,50`)
- **Description** — free text
- **Paid By** — Nestor / Ihor / Ira / Other / Account (partial match works)

Only category and amount are required. Description and Paid By can be omitted:
```
/expense Utilities;340
```

### Recording Expenses (Receipt Photo)

1. Send a **receipt photo** (not a Monobank screenshot) to the group
2. Bot detects it as an expense receipt via OCR (looks for keywords like ЧЕК, КАСИР, ФІСКАЛЬНИЙ)
3. Bot extracts vendor, amount, date from the receipt
4. Continue from step 2 of the interactive flow (category → description → payment → etc.)

### Cancelling an Operation

At any step, send `/cancel` or press the ❌ Скасувати button to abort the current flow.

### Skipping Optional Steps

Many steps have a "Пропустити" (Skip) button. Skipped fields are saved as empty — a warning appears in the confirmation message.

---

## Data Flow

```
Telegram Group → Bot (Railway) → PostgreSQL (Railway)
                                → Google Sheets (cloud)
```

- **PostgreSQL** is the source of truth
- **Google Sheets** is a convenience copy (for quick team access)
- If a Sheets write fails, the data is still in PostgreSQL — an hourly background job retries failed writes

---

## Cost Estimate

| Service | Cost |
|---------|------|
| Railway (Starter plan) | ~$5/month |
| Railway PostgreSQL | Included in plan |
| Google Cloud Vision | Free tier: 1,000 images/month |
| Google Sheets API | Free |
| Google Drive API | Free |
| Telegram Bot API | Free |
| **Total** | **~$5/month** |

---

## Security Features

- **Chat authorization**: Bot only responds to configured group chat + owner's private chat
- **Webhook secret verification**: HMAC constant-time comparison prevents spoofed requests
- **HTTPS enforcement**: Bot refuses to start if webhook URL is not HTTPS
- **Rate limiting**: 60 requests/minute per IP on webhook endpoint
- **Callback validation**: All button presses are validated against known options
- **SQL injection protection**: Parameterized queries everywhere
- **Sheets formula injection**: Cell values starting with `=`, `+`, `-`, `@` are automatically escaped
- **PII protection**: Sensitive OCR text only logged at DEBUG level (not visible in production)
- **Non-root Docker**: Container runs as unprivileged user
- **SSL database**: Encrypted connection to PostgreSQL for remote databases

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond | Check `TELEGRAM_GROUP_CHAT_ID` matches your group. Run `getWebhookInfo` to verify webhook |
| Bot responds in some chats but not others | Only `TELEGRAM_GROUP_CHAT_ID` and `TELEGRAM_OWNER_CHAT_ID` are allowed |
| OCR returns empty text | Check Vision API key. Try a clearer screenshot. Check Railway logs for errors |
| "WEBHOOK_URL must use HTTPS" error | Set `WEBHOOK_URL` to an `https://` URL, or leave it empty for polling mode |
| Sheets write fails | Verify service account has Editor access. Check `GOOGLE_SHEETS_CREDS_JSON` is valid base64 |
| Amount parsed as 0 | Monobank uses non-breaking spaces — the parser handles them, but check OCR output via DEBUG logs |
| Database connection error | Local: check PostgreSQL is running. Railway: check `DATABASE_URL` is set (auto from addon) |
| Rate limited (429 errors) | Normal under heavy load. Telegram retries automatically. Check for abuse if persistent |
| Old expense columns | If upgrading, the `002_expense_refactor.sql` migration runs automatically. Update "Витрати" tab headers in Sheets manually |
| Want to add more authorized chats | Add more chat IDs to `TELEGRAM_GROUP_CHAT_ID` / `TELEGRAM_OWNER_CHAT_ID` in env, or extend `ALLOWED_CHAT_IDS` in `config.py` |
