"""
Ukrainian message formatters for Telegram bot responses.

Ports Make.com modules 7 (OCR summary) and 31 (confirmation).
All user-facing text is in Ukrainian.
"""

from typing import Optional

from config import (
    PROPERTY_MAP,
    PAYMENT_TYPE_MAP,
    PLATFORM_MAP,
    SUP_DURATION_MAP,
    ACCOUNT_TYPE_MAP,
    EXPENSE_CATEGORY_MAP,
    EXPENSE_PROPERTY_MAP,
    PAYMENT_METHOD_MAP,
)


def format_ocr_summary(parsed: dict) -> str:
    """Format the initial OCR result message — Make.com module 7.

    Shows extracted payment data and asks for property selection.
    """
    amount_str = _format_amount(parsed.get("amount"))
    return (
        "💳 *Отримано платіж*\n"
        "\n"
        f"👤 Від: {parsed.get('sender_name', '—')}\n"
        f"💰 Сума: {amount_str} ₴\n"
        f"📅 Дата: {parsed.get('date', '—')}\n"
        f"📝 Призначення: {parsed.get('purpose', '—')}\n"
        "\n"
        "🏠 *До якого об'єкту відноситься?*"
    )


def format_income_confirmation(ctx: dict) -> str:
    """Format income confirmation — Make.com module 31.

    Different format for SUP vs property bookings.
    """
    property_cb = ctx.get("property", "")
    is_sup = property_cb == "prop_sup"

    property_label = PROPERTY_MAP.get(property_cb, ctx.get("property_label", "—"))
    amount_str = _format_amount(ctx.get("amount") or ctx.get("ocr_amount"))
    sender = ctx.get("guest_name") or ctx.get("ocr_sender", "—")
    date_str = ctx.get("date") or ctx.get("ocr_date", "—")

    if is_sup:
        dur_cb = ctx.get("sup_duration", "")
        duration_label = SUP_DURATION_MAP.get(dur_cb, dur_cb)
        return (
            "✅ *SUP Rental записано*\n"
            "\n"
            f"🏄 Об'єкт: SUP Rental\n"
            f"💰 Сума: {amount_str} ₴\n"
            f"👤 Від: {sender}\n"
            f"⏱ Тривалість: {duration_label}\n"
            f"📅 Дата: {date_str}\n"
            f"🗂 Тип: Сапи"
        )

    # Property booking confirmation
    pay_cb = ctx.get("payment_type", "")
    payment_label = PAYMENT_TYPE_MAP.get(pay_cb, pay_cb)
    plat_cb = ctx.get("platform", "")
    platform_label = PLATFORM_MAP.get(plat_cb, plat_cb)
    acc_cb = ctx.get("account_type", "")
    account_label = ACCOUNT_TYPE_MAP.get(acc_cb, acc_cb)
    month = ctx.get("month", "")

    lines = [
        "✅ *Записано в Google Sheets*",
        "",
        f"🏠 Об'єкт: {property_label}",
        f"💰 Сума: {amount_str} ₴",
        f"👤 Від: {sender}",
        f"💳 Тип: {payment_label}",
        f"🌐 Платформа: {platform_label}",
        f"🏦 Рахунок: {account_label}",
    ]

    checkin = ctx.get("checkin")
    checkout = ctx.get("checkout")
    if checkin:
        lines.append(f"📅 Чек-ін: {checkin}")
    if checkout:
        lines.append(f"📅 Чек-аут: {checkout}")

    if month:
        lines.append(f"📆 Місяць: {month}")

    # Warnings for skipped fields
    warnings = _get_skip_warnings(ctx)
    if warnings:
        lines.append("")
        lines.extend(warnings)

    return "\n".join(lines)


def format_expense_confirmation(ctx: dict) -> str:
    """Format expense confirmation message."""
    cat_cb = ctx.get("category", "")
    category_label = EXPENSE_CATEGORY_MAP.get(cat_cb, cat_cb)
    prop_cb = ctx.get("property", "")
    property_label = EXPENSE_PROPERTY_MAP.get(prop_cb, PROPERTY_MAP.get(prop_cb, "—"))
    amount_str = _format_amount(ctx.get("amount"))
    vendor = ctx.get("vendor", "—")
    method_cb = ctx.get("payment_method", "")
    method_label = PAYMENT_METHOD_MAP.get(method_cb, method_cb)
    receipt_url = ctx.get("receipt_url", "")
    notes = ctx.get("notes", "")

    lines = [
        "✅ *Витрату записано*",
        "",
        f"📂 Категорія: {category_label}",
        f"🏠 Об'єкт: {property_label}",
        f"💰 Сума: {amount_str} ₴",
        f"🏪 Виконавець: {vendor}",
        f"💳 Оплата: {method_label}",
    ]

    if receipt_url:
        lines.append(f"📎 Чек: {receipt_url}")

    if notes:
        lines.append(f"📝 Нотатка: {notes}")

    return "\n".join(lines)


def format_cancel_message() -> str:
    """Cancel confirmation."""
    return "❌ Операцію скасовано"


def format_manual_income_start() -> str:
    """Prompt for manual income amount entry."""
    return "💰 *Введіть суму (в грн):*"


def format_ask_guest_name() -> str:
    """Prompt for guest name."""
    return "👤 *Введіть ім'я гостя:*"


def format_ask_property() -> str:
    """Prompt for property selection."""
    return "🏠 *До якого об'єкту відноситься?*"


def format_ask_payment_type() -> str:
    """Prompt for payment type."""
    return "💳 *Тип платежу:*"


def format_ask_platform() -> str:
    """Prompt for platform."""
    return "🌐 *Платформа:*"


def format_ask_account_type() -> str:
    """Prompt for account type."""
    return "💳 *Тип рахунку:*"


def format_ask_dates() -> str:
    """Prompt for check-in / check-out dates."""
    return (
        "📅 *Введіть дати бронювання* (необов'язково):\n"
        "\n"
        "Формат:\n"
        "`ЧЕК-ІН: 22.02.2026`\n"
        "`ЧЕК-АУТ: 25.02.2026`\n"
        "\n"
        "Або натисніть кнопку для пропуску."
    )


def format_ask_sup_duration() -> str:
    """Prompt for SUP duration."""
    return "🏄 *SUP Rental — оберіть тривалість:*"


def format_ask_expense_category() -> str:
    """Prompt for expense category."""
    return "📂 *Категорія витрати:*"


def format_ask_expense_property() -> str:
    """Prompt for expense property."""
    return "🏠 *Об'єкт:*"


def format_ask_expense_amount() -> str:
    """Prompt for expense amount."""
    return "💰 *Введіть суму (в грн):*"


def format_ask_expense_vendor() -> str:
    """Prompt for vendor name."""
    return "🏪 *Назва постачальника/виконавця:*"


def format_ask_expense_payment_method() -> str:
    """Prompt for payment method."""
    return "💳 *Спосіб оплати:*"


def format_ask_expense_receipt() -> str:
    """Prompt for receipt photo."""
    return "📎 *Надішліть фото чеку для завантаження, або пропустіть:*"


def format_ask_expense_notes() -> str:
    """Prompt for expense notes."""
    return "📝 *Додайте нотатку (або натисніть Пропустити):*"


def format_receipt_uploaded() -> str:
    """Confirm receipt was uploaded."""
    return "📎 Чек завантажено!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_amount(amount) -> str:
    """Format amount for display: 2400 → '2 400,00'."""
    if amount is None:
        return "—"
    try:
        num = float(amount)
        # Ukrainian locale: space as thousands separator, comma as decimal
        integer_part = int(num)
        decimal_part = int(round((num - integer_part) * 100))
        int_str = f"{integer_part:,}".replace(",", " ")
        return f"{int_str},{decimal_part:02d}"
    except (ValueError, TypeError):
        return str(amount)


def _get_skip_warnings(ctx: dict) -> list[str]:
    """Generate warning messages for skipped fields."""
    warnings = []
    skip_checks = [
        ("property", "prop_skip", "Об'єкт"),
        ("payment_type", "pay_skip", "Тип платежу"),
        ("platform", "plat_skip", "Платформа"),
        ("sup_duration", "dur_skip", "Тривалість SUP"),
    ]
    for key, skip_val, label in skip_checks:
        if ctx.get(key) == skip_val:
            warnings.append(f"⚠️ {label}: не вказано — оновіть вручну")

    if not ctx.get("checkin") and not ctx.get("checkout"):
        if ctx.get("dates_skipped"):
            warnings.append("⚠️ Дати: не вказано — оновіть вручну")

    return warnings
