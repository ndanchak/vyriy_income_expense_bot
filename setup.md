# Vyriy House Bot — Setup Guide

## Status Overview

| Component | Status | Notes |
|-----------|--------|-------|
| Python codebase | Done | `execution/bot/` — handlers, services, utils, database |
| Directives | Done | `directives/income_bot.md`, `directives/expense_bot.md` |
| Dockerfile + railway.toml | Done | Ready for Railway deploy |
| DB migration | Done | `001_initial.sql` |
| `.env` file | **MISSING** | Only `.env.example` exists — must create `.env` |
| `.gitignore` | **MISSING** | Must create to protect secrets |
| Google Cloud project | **NEEDS SETUP** | Vision API + Sheets API + Drive API + Service Account |
| Telegram bot | **NEEDS SETUP** | Bot token + group chat ID |
| PostgreSQL (local) | **NEEDS SETUP** | For local development |
| Railway project | **NEEDS SETUP** | For production deployment |
| Google Sheets | **NEEDS SETUP** | "Доходи" and "Витрати" tabs with exact headers |

---

## Step 1: Create `.gitignore`

Create a `.gitignore` in the project root with:

```
.env
credentials.json
token.json
.tmp/
__pycache__/
*.pyc
.DS_Store
```

---

## Step 2: Telegram Bot

### 2.1 Create the bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. "Vyriy House Bot")
4. Choose a username (e.g. `vyriy_house_bot`)
5. Copy the **bot token** — you'll need it for `.env`

### 2.2 Get group chat ID

1. Add the bot to your Telegram group
2. Send any message in the group
3. Open this URL in a browser (replace `<TOKEN>` with your bot token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. Find `"chat":{"id":-100XXXXXXXXXX}` — this negative number is your `TELEGRAM_GROUP_CHAT_ID`

### 2.3 Get your personal chat ID

1. Send any message directly to the bot (not in a group)
2. Open the same `getUpdates` URL
3. Find the `"chat":{"id":XXXXXXXXX}` from the direct message — this is your `TELEGRAM_OWNER_CHAT_ID`

---

## Step 3: Google Cloud Project

### 3.1 Create project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it "Vyriy House Bot" → Create

### 3.2 Enable APIs

In the new project, go to **APIs & Services → Library** and enable:

1. **Cloud Vision API** — for Monobank screenshot OCR
2. **Google Sheets API** — for writing income/expense rows
3. **Google Drive API** — for uploading receipt photos

### 3.3 Create Vision API key

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → API Key**
3. Copy the key — this is your `GOOGLE_VISION_API_KEY`
4. (Recommended) Click **Restrict key** → restrict to "Cloud Vision API" only

### 3.4 Create Service Account (for Sheets + Drive)

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → Service Account**
3. Name: `vyriy-bot-sheets` → Create
4. Role: skip (no role needed at project level) → Continue → Done
5. Click the newly created service account email
6. Go to **Keys** tab → **Add Key → Create new key → JSON**
7. A `.json` file downloads — this is your service account key

### 3.5 Encode the service account key to base64

Run in terminal:

```bash
base64 -i ~/Downloads/vyriy-bot-sheets-XXXXX.json | tr -d '\n'
```

Copy the output — this is your `GOOGLE_SHEETS_CREDS_JSON` value for `.env`.

**Keep the original JSON file safe but do NOT put it in the repo.**

---

## Step 4: Google Sheets

### 4.1 Create the spreadsheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new spreadsheet
2. Name it "Vyriy House — Фінанси"
3. Copy the spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
   This is your `GOOGLE_SHEETS_ID`

### 4.2 Share with the service account

1. Click **Share** on the spreadsheet
2. Paste the service account email (looks like `vyriy-bot-sheets@your-project.iam.gserviceaccount.com`)
3. Give it **Editor** access
4. Uncheck "Notify people" → Share

### 4.3 Create "Доходи" tab

Rename the default "Sheet1" tab to **Доходи** (exact spelling). Add these headers in row 1:

| Col | Header (exact) |
|-----|----------------|
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

**Important:** Columns B (Day#) and G (Nights) contain formulas — the bot leaves them empty. Add your formulas there manually.

### 4.4 Create "Витрати" tab

Create a second tab named **Витрати** (exact spelling). Add these headers in row 1:

| Col | Header (exact) |
|-----|----------------|
| A1 | Date |
| B1 | Category |
| C1 | Amount |
| D1 | Property |
| E1 | Vendor |
| F1 | Payment Method |
| G1 | Notes |
| H1 | Receipt Link |

---

## Step 5: Google Drive (Receipt Uploads)

### 5.1 Create a folder

1. Go to [Google Drive](https://drive.google.com)
2. Create a new folder named "Vyriy Receipts"
3. Open the folder — copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_HERE
   ```
   This is your `GOOGLE_DRIVE_FOLDER_ID`

### 5.2 Share with the service account

1. Right-click the folder → Share
2. Paste the service account email
3. Give **Editor** access → Share

---

## Step 6: PostgreSQL (Local Development)

### 6.1 Install PostgreSQL

```bash
# macOS with Homebrew
brew install postgresql@16
brew services start postgresql@16
```

### 6.2 Create the database

```bash
createdb vyriy_dev
```

### 6.3 Run the migration

```bash
psql vyriy_dev < execution/bot/database/migrations/001_initial.sql
```

Verify:

```bash
psql vyriy_dev -c "\dt"
```

You should see `transactions` and `bot_sessions` tables.

---

## Step 7: Create `.env` File

Copy the example and fill in real values:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCDEF...        # from BotFather (Step 2.1)
TELEGRAM_GROUP_CHAT_ID=-100XXXXXXXXXX          # from getUpdates (Step 2.2)
TELEGRAM_OWNER_CHAT_ID=XXXXXXXXX               # from getUpdates (Step 2.3)

# Database
DATABASE_URL=postgresql://localhost:5432/vyriy_dev

# Google Vision OCR
GOOGLE_VISION_API_KEY=AIzaSy...                # from Cloud Console (Step 3.3)

# Google Sheets
GOOGLE_SHEETS_CREDS_JSON=ewogICJ0eXBlIj...    # base64-encoded JSON (Step 3.5)
GOOGLE_SHEETS_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz  # from spreadsheet URL (Step 4.1)

# Google Drive
GOOGLE_DRIVE_FOLDER_ID=1XyZ...                 # from Drive folder URL (Step 5.1)

# Webhook
WEBHOOK_SECRET=<generate below>
WEBHOOK_URL=https://your-ngrok-url             # see Step 8
```

Generate the webhook secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as `WEBHOOK_SECRET`.

---

## Step 8: Local Development with ngrok

Telegram needs a public HTTPS URL to send webhook updates. For local development, use ngrok.

### 8.1 Install ngrok

```bash
brew install ngrok
```

Sign up at [ngrok.com](https://ngrok.com) and add your auth token:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 8.2 Start ngrok tunnel

```bash
ngrok http 8000
```

Copy the `Forwarding` HTTPS URL (e.g. `https://abcd-1234.ngrok-free.app`) and set it as `WEBHOOK_URL` in your `.env`.

### 8.3 Start the bot locally

```bash
cd execution/bot
pip install -r requirements.txt
uvicorn main:api --host 0.0.0.0 --port 8000 --reload
```

The bot will automatically register the webhook with Telegram on startup.

---

## Step 9: Railway Deployment (Production)

### 9.1 Create Railway project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **New Project → Deploy from GitHub repo**
3. Select your repository
4. Railway will detect the `Dockerfile` and `railway.toml` automatically

### 9.2 Add PostgreSQL

1. In your Railway project, click **New → Database → Add PostgreSQL**
2. Railway auto-sets `DATABASE_URL` — no manual config needed

### 9.3 Set environment variables

In your Railway service, go to **Variables** and add all values from your `.env` **except** `DATABASE_URL` (already set by Railway):

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token |
| `TELEGRAM_GROUP_CHAT_ID` | Your group chat ID |
| `TELEGRAM_OWNER_CHAT_ID` | Your personal chat ID |
| `GOOGLE_VISION_API_KEY` | Your Vision API key |
| `GOOGLE_SHEETS_CREDS_JSON` | Base64-encoded service account JSON |
| `GOOGLE_SHEETS_ID` | Your spreadsheet ID |
| `GOOGLE_DRIVE_FOLDER_ID` | Your Drive folder ID |
| `WEBHOOK_SECRET` | Your generated secret |
| `WEBHOOK_URL` | `https://your-service.up.railway.app` |

### 9.4 Run the migration

In the Railway PostgreSQL service, open the **Query** tab and paste the contents of `execution/bot/database/migrations/001_initial.sql`. Execute it.

Alternatively, connect via `psql` using the Railway connection string and run:

```bash
psql $DATABASE_URL < execution/bot/database/migrations/001_initial.sql
```

### 9.5 Deploy

Railway auto-deploys on push to main. Verify:

1. Check the deploy logs for `Application startup complete`
2. Visit `https://your-service.up.railway.app/health` — should return OK
3. Send a Monobank screenshot to the Telegram group — the bot should respond with property buttons

---

## Step 10: Verify Everything Works

### Income flow (OCR)

1. Send a Monobank payment screenshot to the Telegram group
2. Bot should reply with parsed amount/sender and property buttons
3. Walk through: Property → Payment Type → Platform → Account Type → Dates
4. Check the "Доходи" tab in Google Sheets for the new row

### Income flow (Manual)

1. Send `/дохід` in the group
2. Bot asks for amount → guest name → property → etc.
3. Check Google Sheets

### Expense flow

1. Send `/витрата` in the group
2. Walk through: Category → Property → Amount → Vendor → Payment Method → Receipt → Notes
3. Check the "Витрати" tab in Google Sheets
4. If receipt was uploaded, check the Google Drive folder

### Cancel

1. Start any flow, then send `/скасувати`
2. Bot should cancel and clear the session

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond to photos | Check bot is in the group, has admin rights or privacy mode is off. Verify webhook with `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo` |
| OCR returns empty text | Check Vision API key is correct and API is enabled. Try a cleaner screenshot |
| Sheets write fails | Verify service account has Editor access to the spreadsheet. Check `GOOGLE_SHEETS_CREDS_JSON` is valid base64 |
| Drive upload fails | Verify service account has Editor access to the folder. Check `GOOGLE_DRIVE_FOLDER_ID` |
| Database connection error | For local: check PostgreSQL is running (`brew services list`). For Railway: check `DATABASE_URL` is set |
| Webhook not receiving updates | Run `getWebhookInfo` to check. Make sure `WEBHOOK_URL` is accessible from the internet |
| "Unauthorized" from Telegram | Bot token is wrong or expired — regenerate via BotFather |
| Amount parsed as 0 | Non-breaking spaces in Monobank screenshots — the parser handles `\u00a0` but check OCR output |
