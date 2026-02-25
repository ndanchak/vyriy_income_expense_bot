# Directive: Expense Bot

## Objective

Record business expenses into PostgreSQL and Google Sheets "Витрати" tab, with optional receipt link.

## Execution Scripts

- `execution/bot/handlers/expense.py` — Full expense flow (/expense → buttons + text → save)
- `execution/bot/services/sheets.py` — `append_expense_row()` writes to "Витрати" tab

## Trigger

User types `/expense` in the Telegram group.

## Flow

1. Category (inline keyboard): 14 options — Laundry, Guest Amenities, Utilities, Marketing, Management Fee, Maintenance, Capital Expenses, Commissions, Cleaning and Administration, Chemicals, Other, Software, Depreciation fund, Taxes
2. Amount (text input)
3. Description (text input)
4. Payment method (inline keyboard): Cash, Bank Transfer
5. Paid By (inline keyboard): Nestor, Ihor, Ira, Other, Account
6. Receipt link (URL or skip)
7. Save to DB + Sheets, send confirmation

## Fast Entry

Format: `/expense category;amount;description;paid_by`
Example: `/expense Laundry;850;Towel washing;Nestor`

If invalid category → show error with format help and full category list.

## Google Sheets Column Map (Витрати, A-J)

Date (YYYY-MM-DD 0:00:00) | Category | Amount | Description | Payment Method | Paid By | Receipt Link | Vendor | Property | Notes

## State Machine

`expense:awaiting_category` → `expense:awaiting_amount` → `expense:awaiting_description` → `expense:awaiting_payment_method` → `expense:awaiting_paid_by` → `expense:awaiting_receipt`

## Receipt OCR Auto-Detection

When a non-Monobank photo is sent, OCR classifies it as a receipt. Pre-fills vendor and amount from OCR, then enters normal flow at category step. If amount is pre-filled, skips amount input and goes directly to description.

## Edge Cases

- **Amount validation:** Must be positive number. Handles spaces, commas, non-breaking spaces.
- **Receipt URL:** Must start with "http". If not, asks again or offers skip.
- **Fast entry category mismatch:** Shows bulleted list of all valid categories.
- **Old data backward compat:** Transactions without description/paid_by columns default to empty strings in Sheets sync.

## Category Callback Mappings

| Callback | Label |
|---|---|
| exp_laundry | Laundry |
| exp_guest_amenities | Guest Amenities |
| exp_utilities | Utilities |
| exp_marketing | Marketing |
| exp_mgmt_fee | Management Fee |
| exp_maintenance | Maintenance |
| exp_capex | Capital Expenses |
| exp_commissions | Commissions |
| exp_cleaning_admin | Cleaning and Administration |
| exp_chemicals | Chemicals |
| exp_other | Other |
| exp_software | Software |
| exp_depreciation | Depreciation fund |
| exp_taxes | Taxes |

## Payment Method Callback Mappings

| Callback | Label |
|---|---|
| method_cash | Cash |
| method_transfer | Bank Transfer |

## Paid By Callback Mappings

| Callback | Label |
|---|---|
| paidby_nestor | Nestor |
| paidby_ihor | Ihor |
| paidby_ira | Ira |
| paidby_other | Other |
| paidby_account | Account |

## Accessible By

All team members in the Telegram group: Nestor, Іра, Михайло.
