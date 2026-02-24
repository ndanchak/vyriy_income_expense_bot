"""
Google Sheets write service using gspread.

Handles both "Доходи" (income) and "Витрати" (expenses) tabs.
All calls are synchronous (gspread limitation) — handlers must wrap
in asyncio.to_thread() to avoid blocking the event loop.
"""

import base64
import json
import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEETS_CREDS_JSON, GOOGLE_SHEETS_ID

logger = logging.getLogger(__name__)

# Characters that trigger formula interpretation in Google Sheets
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")

_client: Optional[gspread.Client] = None

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client() -> gspread.Client:
    """Initialize or return cached gspread client.

    Credentials decoded from base64-encoded service account JSON.
    """
    global _client
    if _client is None:
        creds_json = json.loads(base64.b64decode(GOOGLE_SHEETS_CREDS_JSON))
        credentials = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        _client = gspread.authorize(credentials)
        logger.info("gspread client initialized")
    return _client


def _sanitize_cell(value) -> str:
    """Prevent Google Sheets formula injection.

    If a string value starts with =, +, -, @, or control characters,
    prefix with a single quote so Sheets treats it as plain text.
    Numeric values are passed through unchanged.
    """
    if isinstance(value, (int, float)):
        return value
    s = str(value)
    if s and s[0] in _FORMULA_PREFIXES:
        return f"'{s}"
    return s


def _sanitize_row(row: list) -> list:
    """Sanitize all cells in a row to prevent formula injection."""
    return [_sanitize_cell(cell) for cell in row]


def append_income_row(data: dict) -> bool:
    """Append a row to the 'Доході' sheet tab.

    Column mapping (Make.com module 30):
        A: Date          — YYYY-MM-DD 0:00:00
        B: Day#          — empty (Sheets formula)
        C: Amount        — number
        D: Property      — display name
        E: Platform      — INST / BC / Airbnb / HutsHub / Direct
        F: Guest Name    — sender name
        G: Nights        — empty (Sheets formula)
        H: Check-in      — DD.MM.YYYY or empty
        I: Check-out     — DD.MM.YYYY or empty
        J: Payment Type  — Передоплата / Доплата / Оплата / Сапи
        K: Account Type  — Account / Cash
        L: Notes         — purpose or SUP duration
        M: Month         — e.g. "February 2026"

    Returns True on success, False on failure.
    """
    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
        worksheet = spreadsheet.worksheet("Доходи")

        row = _sanitize_row([
            data.get("date", ""),           # A: Date
            "",                              # B: Day# (formula)
            data.get("amount", ""),          # C: Amount
            data.get("property", ""),        # D: Property
            data.get("platform", ""),        # E: Platform
            data.get("guest_name", ""),      # F: Guest Name
            "",                              # G: Nights (formula)
            data.get("checkin", ""),         # H: Check-in
            data.get("checkout", ""),        # I: Check-out
            data.get("payment_type", ""),    # J: Payment Type
            data.get("account_type", ""),    # K: Account Type
            data.get("notes", ""),           # L: Notes
            data.get("month", ""),           # M: Month
        ])

        worksheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Income row appended to Sheets: %s %s %s",
                     data.get("date"), data.get("amount"), data.get("property"))
        return True

    except Exception as e:
        logger.error("Failed to write income to Sheets: %s", e)
        return False


def append_expense_row(data: dict) -> bool:
    """Append a row to the 'Витрати' sheet tab.

    Column mapping:
        A: Date           — YYYY-MM-DD 0:00:00
        B: Category       — Прибирання / Комунальні / ...
        C: Amount         — number
        D: Property       — Гніздечко / Чайка / Чапля / Всі / empty
        E: Vendor         — vendor/service provider name
        F: Payment Method — Готівка / Рахунок
        G: Notes          — free text
        H: Receipt Link   — Google Drive URL or empty

    Returns True on success, False on failure.
    """
    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
        worksheet = spreadsheet.worksheet("Витрати")

        row = _sanitize_row([
            data.get("date", ""),              # A: Date
            data.get("category", ""),          # B: Category
            data.get("amount", ""),            # C: Amount
            data.get("property", ""),          # D: Property
            data.get("vendor", ""),            # E: Vendor
            data.get("payment_method", ""),    # F: Payment Method
            data.get("notes", ""),             # G: Notes
            data.get("receipt_url", ""),        # H: Receipt Link
        ])

        worksheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Expense row appended to Sheets: %s %s %s",
                     data.get("date"), data.get("amount"), data.get("category"))
        return True

    except Exception as e:
        logger.error("Failed to write expense to Sheets: %s", e)
        return False
