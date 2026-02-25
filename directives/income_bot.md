# Directive: Income Bot

## Objective

Record income payments into PostgreSQL and Google Sheets "Доході" tab. Two modes: OCR from Monobank screenshots and manual entry via /дохід command.

## Execution Scripts

- `execution/bot/handlers/income.py` — OCR flow (photo → Vision API → regex → buttons → save)
- `execution/bot/handlers/income_manual.py` — Manual flow (/дохід → text input → buttons → save)
- `execution/bot/services/ocr.py` — Google Vision API TEXT_DETECTION wrapper
- `execution/bot/services/sheets.py` — `append_income_row()` writes to "Доході" tab
- `execution/bot/utils/parsers.py` — Monobank regex patterns and date parsers

## OCR Regex Patterns (Monobank)

| Field | Pattern | Notes |
|---|---|---|
| Sender | `(?:Від\|від\|От\|від кого)[:\s]+([^\n]+)` | Strip "Від:" prefix after match |
| Amount | `([\d\s]+[,.]?\d*)\s*(?:₴\|грн\|UAH)` | Remove spaces, replace comma with dot |
| Date | `(\d{2}[./]\d{2}[./]\d{4})` | Handles both dot and slash separators |
| Purpose | `(?:Призначення\|Коментар\|Повідомлення\|призначення)[:\s]+([^\n]+)` | Trim whitespace |

## Google Sheets Column Map (Доході, A-M)

Date (YYYY-MM-DD 0:00:00) | Day# (empty/formula) | Amount | Property | Platform (Website/Instagram/Booking/HutsHub/AirBnB/Phone/Return) | Guest Name | Nights (empty/formula) | Check-in (DD.MM.YYYY) | Check-out (DD.MM.YYYY) | Payment Type | Account Type (Account/Cash/Nestor Account) | Notes | Month

## State Machine

OCR: `income:awaiting_property` → `income:awaiting_sup_duration` (if SUP) → `income:awaiting_payment_type` → `income:awaiting_platform` → `income:awaiting_account_type` → `income:awaiting_dates`

Manual: `income_manual:awaiting_amount` → `income_manual:awaiting_guest_name` → `income_manual:awaiting_property` → (same as OCR from here)

## Edge Cases

- **OCR fails to parse amount:** amount=None → show warning, let user proceed with buttons and enter manually later in Sheets
- **Non-Monobank screenshot:** OCR returns text but regex finds nothing → show warning with empty fields
- **User sends photo during active session:** Reject with "завершіть поточну операцію"
- **Monobank format changes:** Update regex patterns in `utils/parsers.py`, then update this directive
- **Amount with non-breaking spaces:** Parser handles \u00a0 (Monobank uses these in amounts like "2 400")
- **Date with slash separator (DD/MM/YYYY):** Parser handles both dots and slashes

## SUP Branch Logic

When property = SUP Rental:
1. Ask duration instead of payment type
2. Auto-set payment_type = "Сапи"
3. Auto-detect account_type: if "готівка" in purpose → Cash, else Account
4. Notes column gets "Тривалість: {duration}" instead of purpose
5. Skip account_type step (already determined)

## API Cost

Google Vision: first 1000 images/month FREE, then $1.50/1000. At ~100 screenshots/month = $0.00.
