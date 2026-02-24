"""
Regex parsers for Monobank OCR text and date input.

Ports the exact regex patterns from Make.com module 6b:
- sender:  regexGet(text, '(?:Від|від|От|від кого)[:\\s]+([^\\n]+)', 1)
- amount:  regexGet(text, '([\\d\\s]+[,.]?\\d*)\\s*(?:₴|грн|UAH)', 1)
- date:    regexGet(text, '(\\d{2}[./]\\d{2}[./]\\d{4})', 1)
- purpose: regexGet(text, '(?:Призначення|Коментар|Повідомлення|призначення)[:\\s]+([^\\n]+)', 1)
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_monobank_ocr(text: str) -> dict:
    """Extract payment fields from Monobank screenshot OCR text.

    Returns dict with keys: sender_name, amount, date, purpose.
    Missing fields default to empty string / None.
    """
    sender = _extract(text, r"(?:Від|від|От|від кого)[:\s]+([^\n]+)")
    amount_raw = _extract(text, r"([\d\s]+[,.]?\d*)\s*(?:₴|грн|UAH)")
    date_str = _extract(text, r"(\d{2}[./]\d{2}[./]\d{4})")
    purpose = _extract(text, r"(?:Призначення|Коментар|Повідомлення|призначення)[:\s]+([^\n]+)")

    # Clean amount: remove spaces, replace comma with dot (Make.com module 6b logic)
    amount: Optional[Decimal] = None
    if amount_raw:
        cleaned = amount_raw.strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            amount = Decimal(cleaned)
        except (InvalidOperation, ValueError):
            amount = None

    # Clean sender: strip "Від:" / "від:" leftovers
    if sender:
        sender = sender.replace("Від:", "").replace("від:", "").strip()

    return {
        "sender_name": sender or "",
        "amount": amount,
        "date": date_str.strip() if date_str else "",
        "purpose": purpose.strip() if purpose else "",
    }


def parse_dates_input(text: str) -> tuple[Optional[str], Optional[str]]:
    """Parse check-in/check-out from user text.

    Expected format (from Make.com modules 26-27):
        ЧЕК-ІН: 22.02.2026
        ЧЕК-АУТ: 25.02.2026

    Also accepts free-form like "22.02-25.02" or "22.02.2026 - 25.02.2026".
    Returns (checkin, checkout) as DD.MM.YYYY strings, or None if not found.
    """
    checkin = None
    checkout = None

    # Method 1: explicit ЧЕК-ІН / ЧЕК-АУТ labels (primary)
    ci_match = re.search(r"ЧЕК-ІН[:\s]+(\d{2}\.\d{2}\.\d{4})", text, re.IGNORECASE)
    co_match = re.search(r"ЧЕК-АУТ[:\s]+(\d{2}\.\d{2}\.\d{4})", text, re.IGNORECASE)

    if ci_match:
        checkin = ci_match.group(1)
    if co_match:
        checkout = co_match.group(1)

    # Method 2: two dates separated by dash or space (fallback)
    if not checkin and not checkout:
        dates = re.findall(r"(\d{2}\.\d{2}\.\d{4})", text)
        if len(dates) >= 2:
            checkin = dates[0]
            checkout = dates[1]
        elif len(dates) == 1:
            checkin = dates[0]

    return checkin, checkout


def convert_date_for_sheets(dd_mm_yyyy: str) -> str:
    """Convert DD.MM.YYYY → 'YYYY-MM-DD 0:00:00' for Sheets Date column.

    Handles both dot and slash separators.
    """
    cleaned = dd_mm_yyyy.replace("/", ".")
    try:
        dt = datetime.strptime(cleaned, "%d.%m.%Y")
        return dt.strftime("%Y-%m-%d") + " 0:00:00"
    except ValueError:
        return dd_mm_yyyy  # return as-is if parsing fails


def get_month_label(dd_mm_yyyy: str) -> str:
    """Convert DD.MM.YYYY → 'February 2026' for Sheets Month column.

    Make.com module 29: formatDate(parseDate(date, 'DD.MM.YYYY'), 'MMMM YYYY')
    """
    cleaned = dd_mm_yyyy.replace("/", ".")
    try:
        dt = datetime.strptime(cleaned, "%d.%m.%Y")
        return dt.strftime("%B %Y")  # e.g., "February 2026"
    except ValueError:
        return ""


def _extract(text: str, pattern: str) -> Optional[str]:
    """Extract first capture group from text, or None."""
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None
