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
    EXPENSE_SUBCATEGORY_MAP,
    EXPENSE_PROPERTY_MAP,
    PAYMENT_METHOD_MAP,
    PAID_BY_MAP,
)


def format_ocr_summary(parsed: dict) -> str:
    """Format the initial OCR result message — Make.com module 7.

    Shows extracted payment data and asks for property selection.
    Detects returns (negative amounts) and adjusts header/labels.
    """
    amount_str = _format_amount(parsed.get("amount"))
    sender = _escape_md(parsed.get("sender_name", "—"))
    date = _escape_md(parsed.get("date", "—"))
    purpose = _escape_md(parsed.get("purpose", "—"))

    # Detect return (negative amount)
    is_return = parsed.get("amount") is not None and parsed["amount"] < 0
    header = "↩️ *Повернення коштів*" if is_return else "💳 *Отримано платіж*"
    sender_label = "👤 Кому:" if is_return else "👤 Від:"

    return (
        f"{header}\n"
        "\n"
        f"{sender_label} {sender}\n"
        f"💰 Сума: {amount_str} ₴\n"
        f"📅 Дата: {date}\n"
        f"📝 Призначення: {purpose}\n"
        "\n"
        "🏠 *До якого об'єкту відноситься?*"
    )


def format_income_confirmation(ctx: dict) -> str:
    """Format income confirmation — Make.com module 31.

    Different format for SUP vs property bookings.
    All dynamic content is escaped to prevent Markdown parsing errors.
    """
    # Support multi-select properties and legacy single property
    properties = ctx.get("properties", [])
    if not properties:
        single = ctx.get("property", "")
        properties = [single] if single and single != "prop_skip" else []
    is_sup = properties == ["prop_sup"]

    prop_labels = [PROPERTY_MAP.get(p, p) for p in properties if p]
    property_label = _escape_md(" + ".join(prop_labels)) if prop_labels else "—"
    amount_str = _format_amount(ctx.get("amount") or ctx.get("ocr_amount"))
    sender = _escape_md(ctx.get("guest_name") or ctx.get("ocr_sender", "—"))
    date_str = _escape_md(ctx.get("date") or ctx.get("ocr_date", "—"))

    if is_sup:
        dur_cb = ctx.get("sup_duration", "")
        duration_label = _escape_md(SUP_DURATION_MAP.get(dur_cb, dur_cb))
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
    # Fix: show "—" for skipped fields instead of raw callback values like "pay_skip"
    pay_cb = ctx.get("payment_type", "")
    payment_label = _escape_md(PAYMENT_TYPE_MAP.get(pay_cb, "")) if pay_cb and pay_cb != "pay_skip" else "—"
    plat_cb = ctx.get("platform", "")
    platform_label = _escape_md(PLATFORM_MAP.get(plat_cb, "")) if plat_cb and plat_cb != "plat_skip" else "—"
    acc_cb = ctx.get("account_type", "")
    account_label = _escape_md(ACCOUNT_TYPE_MAP.get(acc_cb, "")) if acc_cb else "—"
    month = _escape_md(ctx.get("month", ""))

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

    checkin = _escape_md(ctx.get("checkin"))
    checkout = _escape_md(ctx.get("checkout"))
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
    category_label = _escape_md(EXPENSE_CATEGORY_MAP.get(cat_cb, cat_cb))

    # Subcategory: look it up in the parent category's submap
    sub_cb = ctx.get("subcategory", "")
    subcat_label = ""
    if sub_cb and cat_cb in EXPENSE_SUBCATEGORY_MAP:
        subcat_label = _escape_md(EXPENSE_SUBCATEGORY_MAP[cat_cb].get(sub_cb, sub_cb))

    amount_str = _format_amount(ctx.get("amount"))
    description = _escape_md(ctx.get("description", "—"))
    method_cb = ctx.get("payment_method", "")
    method_label = _escape_md(PAYMENT_METHOD_MAP.get(method_cb, method_cb))
    paidby_cb = ctx.get("paid_by", "")
    paidby_label = _escape_md(PAID_BY_MAP.get(paidby_cb, paidby_cb))
    receipt_url = _escape_md(ctx.get("receipt_url", ""))

    # Show "Category / Subcategory" when subcategory exists
    cat_display = f"{category_label} / {subcat_label}" if subcat_label else category_label

    lines = [
        "✅ *Витрату записано*",
        "",
        f"📂 Категорія: {cat_display}",
        f"💰 Сума: {amount_str} ₴",
        f"📝 Опис: {description}",
        f"💳 Оплата: {method_label}",
        f"👤 Оплатив: {paidby_label}",
    ]

    if receipt_url:
        lines.append(f"📎 Чек: {receipt_url}")

    return "\n".join(lines)


def format_negative_payment_summary(parsed: dict) -> str:
    """Format summary for a negative (outgoing) Monobank payment.

    Shown before asking whether it's an expense or a return to a guest.
    """
    amount_str = _format_amount(parsed.get("amount"))
    recipient = _escape_md(parsed.get("sender_name", "—"))
    date = _escape_md(parsed.get("date", "—"))
    purpose = _escape_md(parsed.get("purpose", ""))

    lines = [
        "💳 *Вихідний платіж*",
        "",
        f"👤 Кому: {recipient}",
        f"💰 Сума: {amount_str} ₴",
        f"📅 Дата: {date}",
    ]

    if purpose:
        lines.append(f"📝 Призначення: {purpose}")

    lines.append("")
    lines.append("❓ *Що це?*")

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


def format_ask_expense_subcategory(category_label: str) -> str:
    """Prompt for expense subcategory after a parent category is selected."""
    return f"📂 *{_escape_md(category_label)}* — оберіть підкатегорію:"


def format_ask_expense_property() -> str:
    """Prompt for expense property."""
    return "🏠 *Об'єкт:*"


def format_ask_expense_amount() -> str:
    """Prompt for expense amount."""
    return "💰 *Введіть суму (в грн):*"


def format_ask_expense_vendor() -> str:
    """Prompt for vendor name."""
    return "🏪 *Назва постачальника/виконавця:*"


def format_ask_expense_description() -> str:
    """Prompt for expense description."""
    return "📝 *Введіть опис витрати:*"


def format_ask_expense_payment_method() -> str:
    """Prompt for payment method."""
    return "💳 *Спосіб оплати:*"


def format_ask_expense_paid_by() -> str:
    """Prompt for who paid."""
    return "👤 *Хто оплатив?*"


def format_ask_expense_receipt() -> str:
    """Prompt for receipt link (manual upload to Drive)."""
    return (
        "📎 *Чек (необов'язково):*\n"
        "\n"
        "Завантажте фото чеку на Google Drive та надішліть посилання.\n"
        "Або натисніть Пропустити."
    )


def format_ask_expense_notes() -> str:
    """Prompt for expense notes."""
    return "📝 *Додайте нотатку (або натисніть Пропустити):*"


def format_duplicate_warning(ctx: dict) -> str:
    """Warning that a similar income already exists."""
    amount_str = _format_amount(ctx.get("amount") or ctx.get("ocr_amount"))
    sender = _escape_md(ctx.get("guest_name") or ctx.get("ocr_sender", ""))
    date_str = _escape_md(ctx.get("date") or ctx.get("ocr_date", ""))
    return (
        "⚠️ *Можливий дублікат*\n"
        "\n"
        f"Запис з тією ж датою ({date_str}), сумою ({amount_str} ₴) "
        f"та гостем ({sender}) вже існує.\n"
        "\n"
        "Зберегти все одно?"
    )


def format_receipt_uploaded() -> str:
    """Confirm receipt was uploaded."""
    return "📎 Чек завантажено!"


def format_receipt_ocr_summary(parsed: dict) -> str:
    """Format receipt OCR result — shows parsed data and asks for category.

    Used when a non-Monobank photo is auto-detected as an expense receipt.
    """
    vendor = _escape_md(parsed.get("vendor", "—"))
    amount_str = _format_amount(parsed.get("amount"))
    date_str = _escape_md(parsed.get("date", ""))

    lines = [
        "🧾 *Розпізнано чек*",
        "",
        f"🏪 Магазин: {vendor}",
        f"💰 Сума: {amount_str} ₴",
    ]

    if date_str:
        lines.append(f"📅 Дата: {date_str}")

    lines.append("")
    lines.append("📂 *Оберіть категорію:*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape_md(text: str) -> str:
    """Escape Telegram Markdown special characters in dynamic content.

    Prevents OCR text or user input from breaking parse_mode='Markdown'.
    Telegram legacy Markdown treats * _ ` [ as formatting characters.
    """
    if not text:
        return text
    for char in ("*", "_", "`", "["):
        text = text.replace(char, "\\" + char)
    return text


def _format_amount(amount) -> str:
    """Format amount for display: 2400 → '2 400,00', -6200 → '−6 200,00'."""
    if amount is None:
        return "—"
    try:
        num = float(amount)
        is_negative = num < 0
        num = abs(num)
        # Ukrainian locale: space as thousands separator, comma as decimal
        integer_part = int(num)
        decimal_part = int(round((num - integer_part) * 100))
        int_str = f"{integer_part:,}".replace(",", " ")
        formatted = f"{int_str},{decimal_part:02d}"
        return f"\u2212{formatted}" if is_negative else formatted
    except (ValueError, TypeError):
        return str(amount)


def _get_skip_warnings(ctx: dict) -> list[str]:
    """Generate warning messages for skipped fields."""
    warnings = []

    # Property: check new multi-select format (empty list = skipped)
    properties = ctx.get("properties", [])
    if not properties and ctx.get("property", "") in ("prop_skip", ""):
        warnings.append("⚠️ Об'єкт: не вказано — оновіть вручну")

    skip_checks = [
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
