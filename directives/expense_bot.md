# Directive: Expense Bot

## Objective

Record business expenses into PostgreSQL and Google Sheets "Витрати" tab, with optional receipt photo upload to Google Drive.

## Execution Scripts

- `execution/bot/handlers/expense.py` — Full expense flow (/витрата → buttons + text → save)
- `execution/bot/services/sheets.py` — `append_expense_row()` writes to "Витрати" tab
- `execution/bot/services/drive.py` — `upload_receipt()` uploads photo to Google Drive

## Trigger

User types `/витрата` in the Telegram group.

## Flow

1. Category (inline keyboard): Прибирання, Комунальні, Обслуговування, Матеріали, Маркетинг, Інше
2. Property (inline keyboard): Гніздечко, Чайка, Чапля, Всі, Пропустити
3. Amount (text input)
4. Vendor name (text input or skip)
5. Payment method (inline keyboard): Готівка, Рахунок
6. Receipt photo (photo upload → auto Google Drive upload, or skip)
7. Notes (text input or skip)
8. Save to DB + Sheets, send confirmation

## Google Sheets Column Map (Витрати, A-H)

Date (YYYY-MM-DD 0:00:00) | Category | Amount | Property | Vendor | Payment Method | Notes | Receipt Link

## State Machine

`expense:awaiting_category` → `expense:awaiting_property` → `expense:awaiting_amount` → `expense:awaiting_vendor` → `expense:awaiting_payment_method` → `expense:awaiting_receipt` → `expense:awaiting_notes`

## Receipt Upload

- Google Drive API v3 with service account credentials
- Upload to folder specified by GOOGLE_DRIVE_FOLDER_ID
- Filename: `receipt_YYYYMMDD_HHMMSS.jpg`
- Permission: anyone with link can view
- URL stored in both PostgreSQL (receipt_url) and Sheets (Receipt Link column)
- Drive folder must be shared with the service account email

## Edge Cases

- **Receipt upload fails:** Show warning, offer skip button. Transaction saved without receipt link.
- **Large receipt photo:** Telegram max photo size is 20MB. python-telegram-bot handles compression.
- **Amount validation:** Must be positive number. Handles spaces, commas, non-breaking spaces.
- **Vendor skip:** Notes skip keyboard serves as vendor skip too. Empty vendor is acceptable.

## Category Callback Mappings

| Callback | Ukrainian Label |
|---|---|
| exp_cleaning | Прибирання |
| exp_utilities | Комунальні |
| exp_maintenance | Обслуговування |
| exp_materials | Матеріали |
| exp_marketing | Маркетинг |
| exp_other | Інше |

## Accessible By

All team members in the Telegram group: Nestor, Іра, Михайло.
