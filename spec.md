# Vyriy House — Income & Expense Bot Specification

## What This Automation Does

A Telegram bot that lives in the Vyriy House team group chat. It records income payments and business expenses into a PostgreSQL database **and** mirrors every entry to Google Sheets — so the team keeps using the spreadsheet they know while the database becomes the reliable source of truth.

Three distinct flows:

---

## Flow 1: Income via Monobank Screenshot (OCR)

**Trigger:** Any team member sends a Monobank payment screenshot to the group.

### Step-by-step user experience:

**1. User sends screenshot →** Bot downloads the image, runs Google Vision OCR, extracts text, and parses out four fields using regex:

| Field | Regex | Example result |
|---|---|---|
| Sender | `(?:Від\|від\|від кого)[:\s]+([^\n]+)` | Коваленко Марина |
| Amount | `([\d\s]+[,.]?\d*)\s*(?:₴\|грн\|UAH)` | 2400.00 |
| Date | `(\d{2}[./]\d{2}[./]\d{4})` | 19.02.2026 |
| Purpose | `(?:Призначення\|Коментар\|Повідомлення)[:\s]+([^\n]+)` | оренда котеджу |

**2. Bot replies with OCR summary + property buttons:**

```
💳 Отримано платіж

👤 Від: Коваленко Марина
💰 Сума: 2 400,00 ₴
📅 Дата: 19.02.2026
📝 Призначення: оренда котеджу

🏠 До якого об'єкту відноситься?
```

Buttons:
```
[🏠 Гніздечко] [🐦 Чайка]
[🦢 Чапля]     [🏄 SUP Rental]
[⏭ Пропустити]
```

**3a. If property selected (not SUP) → Payment Type:**

```
💳 Тип платежу:

[💰 Передоплата] [💵 Доплата]
[✅ Оплата]      [⏭ Пропустити]
```

**3b. If SUP Rental selected → Duration instead:**

```
🏄 SUP Rental — оберіть тривалість:

[⏱ 1 година]      [⏱ 2 години]
[⏱ 3 години]      [🌅 Пів дня (4г)]
[☀️ Весь день]     [⏭ Пропустити]
```

Auto-sets: Payment Type = "Сапи", Account Type = "Cash" if purpose contains "готівка", else "Account".

**4. Platform:**

```
🌐 Платформа:

[🌐 Website]    [📸 Instagram]
[🏨 Booking]    [🔗 HutsHub]
[✈️ AirBnB]     [📞 Phone]
[↩️ Return]      [⏭ Пропустити]
```

**5. Account Type (for non-SUP only):**

```
💳 Тип рахунку:

[🏦 Рахунок]        [💵 Готівка]
[👤 Nestor Account]
```

**6. Dates:**

```
📅 Введіть дати бронювання (необов'язково):

Формат:
ЧЕК-ІН: 22.02.2026
ЧЕК-АУТ: 25.02.2026

[⏭ Пропустити дати]
```

User types dates as text, or presses skip.

**7. Confirmation message:**

```
✅ Записано в Google Sheets

🏠 Об'єкт: Гніздечко
💰 Сума: 2 400,00 ₴
👤 Від: Коваленко Марина
💳 Тип: Передоплата
🌐 Платформа: INST
📅 Чек-ін: 22.02.2026
📅 Чек-аут: 25.02.2026
📆 Місяць: February 2026
```

**What gets written:**

| Where | Data |
|---|---|
| PostgreSQL `transactions` | type=income, all fields, source=ocr, sheets_synced=true/false |
| Google Sheets "Доходи" tab | Row with 13 columns (Date through Month), Day# and Nights left empty for formulas |

---

## Flow 2: Income Manual Entry (`/дохід`)

**Trigger:** User types `/дохід` in the group chat.

### Step-by-step user experience:

**1.** Bot asks: `💰 Введіть суму (в грн):` → User types amount (e.g., "2400")

**2.** Bot asks: `👤 Введіть ім'я гостя:` → User types name (e.g., "Коваленко Марина")

**3–7.** Same button flow as OCR mode: Property → (SUP Duration OR Payment Type) → Platform → Account Type → Dates

**8.** Confirmation message (identical format to OCR flow)

**What gets written:** Same as OCR flow, but with `source=manual` in the database.

---

## Flow 3: Expense Entry (`/витрата`)

**Trigger:** User types `/витрата` in the group chat.

### Step-by-step user experience:

**1. Category:**

```
📂 Категорія витрати:

[🧹 Прибирання]      [💡 Комунальні]
[🔧 Обслуговування]  [📦 Матеріали]
[📣 Маркетинг]       [📋 Інше]
```

**2. Property:**

```
🏠 Об'єкт:

[🏠 Гніздечко] [🐦 Чайка]
[🦢 Чапля]     [🏘 Всі]
[⏭ Пропустити]
```

**3.** Bot asks: `💰 Введіть суму (в грн):` → User types amount

**4.** Bot asks: `🏪 Назва постачальника/виконавця (або натисніть Пропустити):` → User types vendor name or presses skip button

**5. Payment method:**

```
💳 Спосіб оплати:

[💵 Готівка]  [🏦 Рахунок]
```

**6. Receipt (optional):**

```
📎 Надішліть фото чеку для завантаження, або пропустіть:

[⏭ Пропустити]
```

If user sends a photo:
- Bot uploads it to a shared Google Drive folder
- Filename: `receipt_YYYYMMDD_HHMMSS.jpg`
- Sets "anyone with link can view" permission
- Stores the shareable URL

**7.** Bot asks: `📝 Додайте нотатку (або натисніть Пропустити):` → User types note or skips

**8. Confirmation:**

```
✅ Витрату записано

📂 Категорія: Прибирання
🏠 Об'єкт: Гніздечко
💰 Сума: 850,00 ₴
🏪 Виконавець: Марія
💳 Оплата: Готівка
📎 Чек: https://drive.google.com/file/d/xxx/view
📝 Нотатка: прибирання після гостей
```

**What gets written:**

| Where | Data |
|---|---|
| PostgreSQL `transactions` | type=expense, all fields, receipt_url, source=manual |
| Google Sheets "Витрати" tab | Row: Date, Category, Amount, Property, Vendor, Payment Method, Notes, Receipt Link |
| Google Drive | Receipt photo file (if provided) |

---

## Cancel Flow (All Flows)

At **any step**, user can type `/скасувати`. Bot responds:

```
❌ Операцію скасовано
```

Session is cleared. Bot returns to idle, ready for the next command.

---

## Buttons & Keyboards Summary

| Screen | Buttons | Callback data |
|---|---|---|
| Property | Гніздечко, Чайка, Чапля, SUP Rental, Пропустити | prop_gnizd, prop_chaika, prop_chaplia, prop_sup, prop_skip |
| Payment Type | Передоплата, Доплата, Оплата, Пропустити | pay_prepay, pay_balance, pay_full, pay_skip |
| Platform | Website, Instagram, Booking, HutsHub, AirBnB, Phone, Return, Пропустити | plat_website, plat_instagram, plat_booking, plat_hutshub, plat_airbnb, plat_phone, plat_return, plat_skip |
| SUP Duration | 1 год, 2 год, 3 год, Пів дня, Весь день, Пропустити | dur_1h, dur_2h, dur_3h, dur_halfday, dur_fullday, dur_skip |
| Account Type | Рахунок, Готівка, Nestor Account | acc_account, acc_cash, acc_nestor |
| Dates | Пропустити дати | dates_skip |
| Expense Category | Прибирання, Комунальні, Обслуговування, Матеріали, Маркетинг, Інше | exp_cleaning, exp_utilities, exp_maintenance, exp_materials, exp_marketing, exp_other |
| Expense Property | Гніздечко, Чайка, Чапля, Всі, Пропустити | prop_gnizd, prop_chaika, prop_chaplia, prop_all, prop_skip |
| Payment Method | Готівка, Рахунок | method_cash, method_account |
| Receipt | Пропустити | receipt_skip |
| Notes | Пропустити | notes_skip |

---

## What It Looks Like

### Telegram Chat Appearance

The bot communicates entirely through:
1. **Text messages** with Markdown formatting (bold headers, emoji prefixes)
2. **Inline keyboards** — rows of buttons directly under each message
3. **Edit-in-place** — when a button is pressed, the message updates to show the next question (keeps chat clean, no message flooding)

Visual style:
- Each question is a short 1-2 line prompt with an emoji prefix
- Buttons are arranged in 2-column grids (2 buttons per row)
- "Пропустити" (skip) button is always alone on the last row
- Confirmation messages use a card format with emoji + label + value on each line
- All text is in Ukrainian

### Google Sheets Appearance

**"Доходи" tab** — one row per income entry:
```
| 2026-02-19 0:00:00 | [formula] | 2400 | Гніздечко | Instagram | Коваленко Марина | [formula] | 22.02.2026 | 25.02.2026 | Передоплата | Account | оренда котеджу | February 2026 |
```

**"Витрати" tab** — one row per expense:
```
| 2026-02-19 0:00:00 | Прибирання | 850 | Гніздечко | Марія | Готівка | прибирання після гостей | https://drive.google.com/... |
```

---

## Build Steps (3 Phases)

### Step 1: Bot Skeleton with Fake Data (Make it work and look right)

Build the complete Telegram bot with all three flows, hardcoded responses, and no external API calls:

- **main.py** with FastAPI + webhook endpoint
- **All keyboards** built and working (buttons render, callbacks fire)
- **All state transitions** working end-to-end (state machine in PostgreSQL)
- **Fake OCR:** When photo received, return hardcoded parsed data: `sender="Тестовий Гість"`, `amount=1000`, `date="20.02.2026"`, `purpose="тестовий платіж"`
- **Fake Sheets:** Print row data to console instead of writing to Google Sheets
- **Fake Drive:** Print "would upload receipt" to console instead of uploading
- **Real database:** PostgreSQL INSERT works, transactions are stored
- **All Ukrainian messages** formatted correctly with emojis
- **Cancel flow** working at every step

**Goal:** Walk through all 3 flows in Telegram, see all buttons, get confirmation messages. Everything looks exactly like production, but no Google API calls.

### Step 2: Connect Real APIs (Make it real)

Replace all fakes with real integrations:

- **Google Vision OCR** — real screenshot → real text extraction → real regex parsing
- **Google Sheets** — real writes to "Доходи" and "Витрати" tabs with correct column mapping
- **Google Drive** — real receipt photo upload, real shareable links
- **sheets_sync** background job — retry failed Sheets writes every hour
- **Error handling** — graceful failures, user-facing error messages in Ukrainian

**Goal:** Send a real Monobank screenshot, walk through the flow, see the row appear in Google Sheets.

### Step 3: Deploy to Railway (Make it permanent)

- **Dockerfile** and **railway.toml** configuration
- Push to GitHub → Railway auto-deploy
- Set all environment variables in Railway dashboard
- Run database migration on Railway PostgreSQL
- Switch webhook URL from ngrok to Railway
- Run in parallel with Make.com for 1 week to compare outputs
- Deactivate Make.com income scenario once validated

**Goal:** Bot runs 24/7 on Railway, responds instantly, survives restarts (sessions resume from PostgreSQL state).
