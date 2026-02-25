"""
Regex parsers for Monobank OCR text, receipt OCR, and date input.

Ports the exact regex patterns from Make.com module 6b:
- sender:  regexGet(text, '(?:Від|від|От|від кого)[:\\s]+([^\\n]+)', 1)
- amount:  regexGet(text, '([\\d\\s]+[,.]?\\d*)\\s*(?:₴|грн|UAH)', 1)
- date:    regexGet(text, '(\\d{2}[./]\\d{2}[./]\\d{4})', 1)
- purpose: regexGet(text, '(?:Призначення|Коментар|Повідомлення|призначення)[:\\s]+([^\\n]+)', 1)

Also includes:
- detect_ocr_type(): classify OCR text as Monobank income or expense receipt
- parse_receipt_ocr(): extract vendor, amount, date from receipt/check photos
"""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# Ukrainian month names → month number (for parsing "23 лютого 2026" format)
_UK_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}


def parse_monobank_ocr(text: str) -> dict:
    """Extract payment fields from Monobank screenshot OCR text.

    Returns dict with keys: sender_name, amount, date, purpose.
    Missing fields default to empty string / None.
    """
    # Normalize whitespace: replace non-breaking spaces with regular spaces
    normalized = text.replace("\u00a0", " ")

    sender = _extract(normalized, r"(?:Від|від|От|від кого)[:\s]+([^\n]+)")

    # Amount: Google Vision OCR reads ₴ as € (euro sign!) in modern Monobank screenshots.
    # Also handle ₴, грн, UAH for other formats.
    # Actual OCR output looks like: "1 450.00 €" or "4800.00 €"
    # IMPORTANT: use [ ] (literal space) not \s — \s matches newlines and crosses lines!
    _currency = r"(?:₴|€|грн|UAH)"
    amount_raw = (
        # Pattern 1: number followed by currency sign (handles ₴ OCR'd as €)
        _extract(normalized, rf"(\d[\d ]*[,.]?\d*)\s*{_currency}")
        # Pattern 2: currency sign before number
        or _extract(normalized, rf"{_currency}\s*(\d[\d ]*[,.]?\d*)")
        # Pattern 3: standalone number with decimals as fallback (e.g. "10 000.00")
        or _extract(normalized, r"(\d[\d ]*\d[,.]\d{2})")
    )

    # Date: try Ukrainian month format FIRST (modern Monobank uses "23 лютого 2026").
    # DD.MM.YYYY fallback can incorrectly match dates from purpose text.
    date_str = _extract_ukrainian_date(normalized)
    if not date_str:
        date_str = _extract(normalized, r"(\d{2}[./]\d{2}[./]\d{4})")

    # Purpose: try labeled format first (old Monobank / other banks)
    purpose = _extract(normalized, r"(?:Призначення|Коментар|Повідомлення|призначення)[:\s]+([^\n]+)")

    # Fallback: in modern Monobank, purpose is the last line(s) after the amount.
    # OCR structure: "...\n{amount} €\n{purpose text}"
    if not purpose:
        amount_line_match = re.search(rf"[\d\s.,]+{_currency}\s*\n(.+)", normalized, re.DOTALL)
        if amount_line_match:
            # Take everything after the amount line, clean up
            remaining = amount_line_match.group(1).strip()
            # Remove trailing timestamps like "19:57 /" or "20:50 //"
            remaining = re.sub(r"\d{2}:\d{2}\s*/*\s*$", "", remaining).strip()
            # Remove OCR noise: single-char lines, short ALL-CAPS lines (UI elements),
            # trailing timestamps like "20:50 //"
            if remaining:
                clean_lines = []
                for line in remaining.split("\n"):
                    line = line.strip()
                    if len(line) <= 2:
                        continue  # skip single/double char noise ("=", "OY", "E", "O")
                    if re.match(r"^[A-ZА-ЯІЇЄҐ]{1,3}$", line):
                        continue  # skip short uppercase-only lines (UI button artifacts)
                    if re.match(r"^\d{2}:\d{2}\s*/*\s*$", line):
                        continue  # skip standalone timestamp lines ("20:50 //")
                    clean_lines.append(line)
                purpose = "\n".join(clean_lines).strip() if clean_lines else None

    # Clean amount: remove spaces, replace comma with dot (Make.com module 6b logic)
    amount: Optional[Decimal] = None
    if amount_raw:
        cleaned = amount_raw.strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            amount = Decimal(cleaned)
        except (InvalidOperation, ValueError):
            amount = None
    logger.info("Amount parsing: raw=%r → cleaned=%r → decimal=%s",
                amount_raw, amount_raw.strip().replace(" ", "").replace(",", ".") if amount_raw else None, amount)

    # Clean sender: strip "Від:" / "від:" leftovers
    if sender:
        sender = sender.replace("Від:", "").replace("від:", "").strip()

    return {
        "sender_name": sender or "",
        "amount": amount,
        "date": date_str.strip() if date_str else "",
        "purpose": purpose.strip() if purpose else "",
    }


def _extract_ukrainian_date(text: str) -> Optional[str]:
    """Extract date from Ukrainian text format like '23 лютого 2026, 08:53'.

    Returns date as DD.MM.YYYY string, or None.
    """
    months_pattern = "|".join(_UK_MONTHS.keys())
    match = re.search(rf"(\d{{1,2}})\s+({months_pattern})\s+(\d{{4}})", text)
    if match:
        day = int(match.group(1))
        month = _UK_MONTHS[match.group(2)]
        year = match.group(3)
        return f"{day:02d}.{month:02d}.{year}"
    return None


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


# ---------------------------------------------------------------------------
# OCR type detection + receipt parsing
# ---------------------------------------------------------------------------

# Receipt indicators: fiscal receipt keywords (very specific, won't appear in Monobank)
_RECEIPT_KEYWORDS = re.compile(
    r"ЧЕК|КАСИР|ШТРИХ-КОД|ФІСКАЛЬНИЙ|БЕЗГОТІВКОВ|ПН\s+\d",
    re.IGNORECASE,
)


def detect_ocr_type(text: str) -> str:
    """Classify OCR text as 'monobank' (income) or 'expense' (receipt).

    Strategy: positively detect receipts, default to monobank.
    Receipt keywords (ЧЕК, КАСИР, ШТРИХ-КОД, ФІСКАЛЬНИЙ) are very specific
    and won't appear in Monobank screenshots.
    Monobank is the primary use case, so unknown photos default to income.
    This avoids fragile currency detection (Vision OCR maps ₴ unpredictably).
    """
    if not text:
        return "monobank"

    if _RECEIPT_KEYWORDS.search(text):
        return "expense"

    return "monobank"


def parse_receipt_ocr(text: str) -> dict:
    """Extract vendor, amount, and date from a receipt/check OCR text.

    Returns dict with keys: vendor, amount (Decimal|None), date (str), raw_text.
    """
    normalized = text.replace("\u00a0", " ")

    # --- Vendor ---
    # Usually the first meaningful line (store name like "АТБ-МАРКЕТ", "СІЛЬПО")
    # Skip very short lines, blank lines, and lines with just numbers/symbols
    vendor = ""
    for line in normalized.split("\n"):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        # Skip lines that are purely numeric, timestamps, or receipt metadata
        if re.match(r"^[\d\s.,:/-]+$", line):
            continue
        if re.match(r"^(ЧЕК|КАСИР|ШТРИХ|ПН\s)", line, re.IGNORECASE):
            continue
        vendor = line
        break

    # --- Amount ---
    # Receipt patterns: "СУМА 495,00 ГРН", "116,40 ГРН", "БЕЗГОТІВКОВА 495,00 ГРН"
    amount: Optional[Decimal] = None
    # Pattern 1: "СУМА" followed by number and optional ГРН
    amount_raw = _extract(normalized, r"СУМА\s+([\d\s]+[,.]?\d*)\s*(?:ГРН)?")
    # Pattern 2: number followed by ГРН
    if not amount_raw:
        amount_raw = _extract(normalized, r"([\d\s]+[,.]\d{2})\s*ГРН")
    # Pattern 3: "БЕЗГОТІВКОВА" or "ГОТІВКА" followed by number
    if not amount_raw:
        amount_raw = _extract(normalized, r"(?:БЕЗГОТІВКОВ\w*|ГОТІВКА)\s+([\d\s]+[,.]?\d*)")

    if amount_raw:
        cleaned = amount_raw.strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            amount = Decimal(cleaned)
        except (InvalidOperation, ValueError):
            amount = None

    # --- Date ---
    # Receipts typically use DD.MM.YYYY format
    date_str = _extract(normalized, r"(\d{2}[./]\d{2}[./]\d{4})")

    logger.info(
        "Receipt parsing: vendor=%r, amount=%s, date=%r",
        vendor, amount, date_str,
    )

    return {
        "vendor": vendor,
        "amount": amount,
        "date": date_str.strip() if date_str else "",
        "raw_text": text,
    }
