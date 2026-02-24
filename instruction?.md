# Setup Instructions for Vyriy Expenses Automation

Based on the project's CLAUDE.md, here are the setup requirements:

## Prerequisites

1. **Telegram Bot** — Create via [BotFather](https://t.me/BotFather), get the bot token
2. **Google Cloud Project** with:
   - Cloud Vision API enabled (for OCR)
   - Google Sheets API enabled
   - OAuth 2.0 credentials downloaded as `credentials.json`
3. **Make.com account** (for the automation blueprint)

## Google Sheets Setup

Create a Google Sheet with a tab named exactly **"Доходи"** with these column headers:

| Col | Header |
|-----|--------|
| A | Date |
| B | Day# |
| C | Amount |
| D | Property |
| E | Platform |
| F | Guest Name |
| G | Nights |
| H | Check-in |
| I | Check-out |
| J | Payment Type |
| K | Account Type |
| L | Notes |
| M | Month |

Columns **B** (Day#) and **G** (Nights) should contain formulas — the bot leaves them empty.

## Make.com Blueprint Setup

1. Import the blueprint into Make.com
2. Replace `YOUR_SPREADSHEET_ID_HERE` in module 30 with your actual Google Sheet ID
3. Configure these connections:
   - **Telegram** — paste the bot token from BotFather
   - **Google Vision API** — enter your API key
   - **Google Sheets** — authorize via OAuth

## Local Development (`.env`)

Place a `.env` file in the project root with:

```
TELEGRAM_BOT_TOKEN=your_bot_token
GOOGLE_VISION_API_KEY=your_api_key
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

## File Security

Ensure these are in `.gitignore`:
- `credentials.json`
- `token.json`
- `.env`
- `.tmp/`

## Verify It Works

1. Send a Monobank payment screenshot to the Telegram group
2. The bot should OCR the image and prompt with inline buttons (property, payment type, platform, dates)
3. After completing the flow, check the "Доходи" tab for the new row

---

Want me to check the current state of the project files to see what's already configured and what still needs setup?