# CLAUDE.md

# Agent Instructions

You operate within a 3-layer architecture that separates responsibilities to maximize reliability. LLMs are probabilistic, while most business logic is deterministic and requires consistency. This system solves that problem.

## 3-Layer Architecture

### Layer 1: Directive (What to do)
- Essentially SOPs written in Markdown, living in `directives/`
- They define objectives, inputs, tools/scripts to use, outputs, and edge cases
- Natural-language instructions, like you’d give to a mid-level employee

### Layer 2: Orchestration (Decisions)
- Your job: intelligent routing.
- Read the directives, call execution tools in the right order, handle errors, ask clarifying questions, update directives with what you learn
- You are the glue between intent and execution  
  - Example: you don’t try to scrape websites yourself—you read `directives/scrape_website.md`, define inputs/outputs, then run `execution/scrape_single_site.py`

### Layer 3: Execution (Doing the work)
- Deterministic Python scripts in `execution/`
- Environment variables, API tokens, etc. are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast  
- Use scripts instead of manual work  
- Well-commented

**Why it works:**  
If you do everything yourself, errors compound.  
90% accuracy per step = ~59% success over 5 steps.  
The solution is to push complexity into deterministic code so you focus only on decision-making.

---

## Operating Principles

### 1. Check existing tools first
Before writing a script:
- Check `execution/` according to your directive
- Create new scripts only if none exist

### 2. Self-correct when something breaks
- Read the error message and stack trace
- Fix the script and test again  
  - If it uses paid tokens/credits, ask the user first
- Update the directive with what you learned:
  - API limits
  - Timing constraints
  - Edge cases

**Example flow:**
- Hit an API rate limit  
- Check the API docs  
- Find a batch endpoint  
- Rewrite the script to use it  
- Test  
- Update the directive

### 3. Update directives as you learn
- Directives are living documents
- Update them when you discover:
  - API constraints
  - Better approaches
  - Common errors
  - Timing expectations
- Do **not** create or overwrite directives without asking unless explicitly instructed
- Directives must be preserved and improved over time—not used ad hoc and discarded

---

## Self-Correction Loop

Errors are learning opportunities. When something breaks:

1. Fix it  
2. Update the tool  
3. Test the tool to confirm it works  
4. Update the directive to include the new flow  
5. The system is now stronger

---

## Web App Development

### Tech Stack
When asked to create a web app, use:

- **Frontend**: Next.js + React + Tailwind CSS  
- **Backend**: FastAPI (Python) or Next.js API routes

### Brand Guidelines
- Before development, check for `brand-guidelines.md` in the project root
- If present, use the specified fonts and colors to maintain brand consistency

### Directory Structure for Applications

project-root/
├── frontend/ # Next.js app
│ ├── app/ # Next.js App Router
│ ├── components/ # React components
│ ├── public/ # Static assets
│ └── package.json
├── backend/ # FastAPI API (if needed)
│ ├── main.py # Entry point
│ ├── requirements.txt
│ └── .env
├── directives/ # Markdown SOPs
├── execution/ # Utility Python scripts
├── .tmp/ # Intermediate files
└── brand-guidelines.md # (optional) Fonts and colors



---

## File Organization

### Deliverables vs Intermediates
- **Deliverables**
  - Google Sheets
  - Google Slides
  - Other cloud-based outputs accessible to the user
- **Intermediates**
  - Temporary files needed during processing

### Directory Rules
- `.tmp/`
  - All intermediate files (folders, scraped data, temporary exports)
  - Never commit
  - Always regenerable
- `execution/`
  - Deterministic Python scripts (tools)
- `directives/`
  - Markdown SOPs (instruction set)
- `.env`
  - Environment variables and API keys
- `credentials.json`, `token.json`
  - Google OAuth credentials
  - Must be in `.gitignore`

**Key principle:**  
Local files are only for processing.  
Deliverables live in cloud services where the user can access them.  
Everything in `.tmp/` can be deleted and regenerated at any time.



## Project Overview

**Vyriy House** — vacation rental automation for 3 properties (Гніздечко, Чайка, Чапля) + SUP rental near Lviv, Ukraine. Owner: Nestor (50/50 with Igor). Team uses a Telegram group as the operational hub.


## What the Income Bot Does

Monobank payment screenshot in Telegram group → Google Vision OCR → interactive Telegram buttons (property, payment type, platform, dates) → Google Sheets row in "Доходи" tab.

### Negative Payment Disambiguation

When OCR detects a **negative** amount on a Monobank screenshot (outgoing payment), the bot asks:
- "Що це?" → [💸 Витрата] [↩️ Повернення гостю]
- **Витрата** → starts expense flow with pre-filled amount (absolute value), date, vendor (recipient), description (purpose), payment method auto-set to Bank Transfer
- **Повернення гостю** → starts income flow (marks as return, keeps negative amount)

### Planned Make.com Blueprint Module Flow

1. **Trigger:** Telegram Watch Messages → filter for photos only
2. **OCR:** Download image → Google Vision API TEXT_DETECTION (language hints: uk, ru)
3. **Parse:** Regex extraction from Monobank text — sender_name, amount, date, purpose
4. **Interactive flow:** Property → (SUP duration OR Payment type) → Dates → Platform
5. **Write:** Google Sheets "Доходи" tab → send confirmation message

### Key Technical Details

- **OCR regex patterns** (Monobank screenshot format):
  - sender: `(?:Від|від|від кого)[:\s]+([^\n]+)`
  - amount: `([\d\s]+[,.]?\d*)\s*(?:₴|грн|UAH)`
  - date: `(\d{2}[./]\d{2}[./]\d{4})`
  - purpose: `(?:Призначення|Коментар|Повідомлення)[:\s]+([^\n]+)`
- **SUP branch:** When "SUP Rental" selected → asks duration instead of payment type, auto-sets Payment Type = "Сапи", auto-detects Cash if "готівка" in purpose
- **Skip logic:** Every question has "Пропустити" button → writes empty string, shows warning in confirmation
- **Formula columns:** Day# (col B) and Nights (col G) are Sheets formulas — bot leaves them empty

## Google Sheets "Доходи" Column Map

| Col | Header | Bot writes |
|---|---|---|
| A | Date | `YYYY-MM-DD 0:00:00` |
| B | Day# | Empty (formula) |
| C | Amount | Number (UAH) |
| D | Property | Гніздечко / Чайка / Чапля / SUP Rental |
| E | Platform | Website / Instagram / Booking / HutsHub / AirBnB / Phone / Return |
| F | Guest Name | From Monobank sender field |
| G | Nights | Empty (formula) |
| H | Check-in | DD.MM.YYYY or empty |
| I | Check-out | DD.MM.YYYY or empty |
| J | Payment Type | Передоплата / Доплата / Оплата / Сапи |
| K | Account Type | Account / Cash / Nestor Account |
| L | Notes | OCR purpose or SUP duration |
| M | Month | e.g. "June 2025" |

## Callback Data Mappings

| Callback | Label |
|---|---|
| `prop_gnizd` | Гніздечко |
| `prop_chaika` | Чайка |
| `prop_chaplia` | Чапля |
| `prop_sup` | SUP Rental |
| `pay_prepay` | Передоплата |
| `pay_balance` | Доплата |
| `pay_full` | Оплата |
| `plat_website` | Website |
| `plat_instagram` | Instagram |
| `plat_booking` | Booking |
| `plat_hutshub` | HutsHub |
| `plat_airbnb` | AirBnB |
| `plat_phone` | Phone |
| `plat_return` | Return |
| `acc_nestor` | Nestor Account |
| `dur_1h` / `dur_2h` / `dur_3h` / `dur_halfday` / `dur_fullday` | Duration labels |
| `exp_rent_utilities` | Rent & Utilities |
| `exp_salary` | Salary |
| `exp_taxes` | Taxes |
| `exp_chemicals` | Chemicals |
| `exp_cosmetics` | Cosmetics etc |
| `exp_guest_amenities` | Guest Amenities |
| `exp_software` | Software |
| `exp_other` | Other |
| `exp_depreciation` | Depreciation fund |
| `exp_advertisement` | Advertisement |
| `exp_commissions` | Commissions |
| `exp_laundry` | Laundry |
| `sub_electricity` / `sub_woods` / `sub_water` / `sub_sewerage` / `sub_internet` / `sub_phone` / `sub_security` / `sub_garbage` / `sub_account_fee` / `sub_other` | Rent & Utilities subcategories |
| `sub_housekeeper` / `sub_smm` / `sub_zavgosp` / `sub_manager` | Salary subcategories |
| `sub_yediniy` / `sub_viyskoviy` / `sub_esv` / `sub_tur` / `sub_ep_nestor` / `sub_vz_nestor` | Taxes subcategories |
| `flow_expense` | Витрата (disambiguation) |
| `flow_return` | Повернення гостю (disambiguation) |
| `method_vyriy_card` | VyriY Card |
| `method_vyriy_transfer` | VyriY Bank Transfer |
| `method_other` | Other |
| `paidby_nestor` | Nestor |
| `paidby_ihor` | Ihor |
| `paidby_ira` | Ira |
| `paidby_other` | Other |
| `paidby_account` | Account |

## Setup Requirements (for fresh import)

1. Replace `YOUR_SPREADSHEET_ID_HERE` in module 30
2. Telegram bot token via BotFather → Make.com connection
3. Google Vision API key (Cloud Vision API enabled)
4. Google Sheets OAuth connection
5. Sheet tab named exactly "Доходи" with exact column headers above

## Future Railway Migration (Not Yet Built)

Architecture is fully designed in `vyriy-railway-architecture.md`. Target stack: Python, FastAPI, PostgreSQL, Railway ($5/mo). Planned modules beyond income bot:

- Expense bot (`/витрата` command + receipt OCR)
- Booking pipeline (IMAP email parser for Airbnb/Booking.com)
- Guest communications engine (9 automated touch points per booking)
- CRM / guest database with repeat detection and VIP tagging
- Cleaning coordination
- Review management
- Dynamic pricing
- Analytics & reporting (weekly digest, monthly P&L)

State machine design uses `bot_sessions` PostgreSQL table with `{module}:{step}` state naming convention.

## Language & Locale

All user-facing text is in Ukrainian. The team communicates in Ukrainian. Variable names and code comments should be in English. Platform abbreviation "INST" = Instagram, "BC" = Booking.com.

## Business Context

- Extreme seasonality (270% high/low variance)
- Booking platforms: Airbnb, Booking.com, Instagram (INST), HutsHub, direct
- Expansion planned: hot tub + potentially 4 new properties

---

## Development Rules & Lessons Learned

### 1. Always use `python3` (not `python`)
This machine does not have `python` aliased. Always use `python3` to run any scripts, tests, or REPL commands.

### 2. Always run tests after modifications — but confirm first
After any code change, run verification tests (import checks, unit tests, integration tests) to catch issues early. **Always confirm with the user before running tests**, especially if they consume paid API credits or external services.

### 3. Read files before editing
Always use the Read tool on a file before attempting to Write or Edit it. The tooling enforces this — writing without reading first will fail.

### 4. Test incrementally, not all at once
When making multi-file changes, test each step individually rather than waiting until the end. This catches issues early and makes debugging easier.

---

## Summary

You sit between:
- Human intent (directives)
- Deterministic execution (Python scripts)

Your role:
- Read instructions
- Make decisions
- Call tools
- Handle errors
- Continuously improve the system

Be pragmatic.  
Be reliable.  
Self-correct.

