"""
Telegram InlineKeyboard builders.

Replaces hardcoded JSON reply_markup strings from Make.com modules 7, 11, 14, 17, 19.
Emojis preserved for visual consistency with the existing Make.com bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import EXPENSE_SUBCATEGORY_MAP


# ---------------------------------------------------------------------------
# Income keyboards
# ---------------------------------------------------------------------------

def property_keyboard(show_save_minimal: bool = True) -> InlineKeyboardMarkup:
    """Property selection — Make.com module 7 (legacy single-select)."""
    return property_toggle_keyboard([], show_save_minimal=show_save_minimal)


# Property button definitions: (callback_data, default_emoji, label)
_PROPERTY_BUTTONS = [
    ("prop_gnizd", "🏠", "Гніздечко"),
    ("prop_chaika", "🐦", "Чайка"),
    ("prop_chaplia", "🦢", "Чапля"),
    ("prop_sup", "🏄", "SUP Rental"),
]


def property_toggle_keyboard(
    selected: list[str],
    show_save_minimal: bool = True,
) -> InlineKeyboardMarkup:
    """Multi-select property keyboard with toggle checkmarks.

    Tapping a property toggles ✅ on/off. When any property is selected,
    a "Підтвердити" button appears. SUP is exclusive (handled by the callback).
    show_save_minimal adds a "Зберегти без деталей" quick-save button.
    """
    rows = []
    for i in range(0, len(_PROPERTY_BUTTONS), 2):
        row = []
        for cb, emoji, label in _PROPERTY_BUTTONS[i:i + 2]:
            if cb in selected:
                row.append(InlineKeyboardButton(f"✅ {label}", callback_data=cb))
            else:
                row.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=cb))
        rows.append(row)

    # Confirm button (only if something is selected)
    if selected:
        count = len(selected)
        rows.append([InlineKeyboardButton(
            f"✅ Підтвердити ({count})", callback_data="prop_confirm"
        )])

    # Quick-save button: skip all details, save with OCR data only
    if show_save_minimal:
        rows.append([InlineKeyboardButton("💾 Зберегти без деталей", callback_data="save_minimal")])

    # Skip button always available
    rows.append([InlineKeyboardButton("⏭ Пропустити", callback_data="prop_skip")])

    return InlineKeyboardMarkup(rows)


def sup_duration_keyboard() -> InlineKeyboardMarkup:
    """SUP rental duration — Make.com module 11."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱ 1 година", callback_data="dur_1h"),
            InlineKeyboardButton("⏱ 2 години", callback_data="dur_2h"),
        ],
        [
            InlineKeyboardButton("⏱ 3 години", callback_data="dur_3h"),
            InlineKeyboardButton("🌅 Пів дня (4г)", callback_data="dur_halfday"),
        ],
        [
            InlineKeyboardButton("☀️ Весь день", callback_data="dur_fullday"),
            InlineKeyboardButton("⏭ Пропустити", callback_data="dur_skip"),
        ],
    ])


def payment_type_keyboard() -> InlineKeyboardMarkup:
    """Payment type — Make.com module 14."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Передоплата", callback_data="pay_prepay"),
            InlineKeyboardButton("💵 Доплата", callback_data="pay_balance"),
        ],
        [
            InlineKeyboardButton("✅ Оплата (повна)", callback_data="pay_full"),
            InlineKeyboardButton("⏭ Пропустити", callback_data="pay_skip"),
        ],
    ])


def platform_keyboard() -> InlineKeyboardMarkup:
    """Booking platform — Make.com module 19."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 Website", callback_data="plat_website"),
            InlineKeyboardButton("📸 Instagram", callback_data="plat_instagram"),
        ],
        [
            InlineKeyboardButton("🏨 Booking", callback_data="plat_booking"),
            InlineKeyboardButton("🔗 HutsHub", callback_data="plat_hutshub"),
        ],
        [
            InlineKeyboardButton("✈️ AirBnB", callback_data="plat_airbnb"),
            InlineKeyboardButton("📞 Phone", callback_data="plat_phone"),
        ],
        [
            InlineKeyboardButton("↩️ Return", callback_data="plat_return"),
            InlineKeyboardButton("⏭ Пропустити", callback_data="plat_skip"),
        ],
    ])


def account_type_keyboard() -> InlineKeyboardMarkup:
    """Account type: bank transfer, cash, or Nestor's personal account."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏦 Рахунок", callback_data="acc_account"),
            InlineKeyboardButton("💵 Готівка", callback_data="acc_cash"),
        ],
        [
            InlineKeyboardButton("👤 Nestor Account", callback_data="acc_nestor"),
        ],
    ])


def dates_skip_keyboard() -> InlineKeyboardMarkup:
    """Skip button for dates step — Make.com module 17."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустити дати", callback_data="dates_skip")],
    ])


# ---------------------------------------------------------------------------
# Expense keyboards
# ---------------------------------------------------------------------------

def expense_category_keyboard() -> InlineKeyboardMarkup:
    """Expense category selection (12 categories).

    Categories with subcategories (Rent & Utilities, Salary, Taxes) will
    trigger a second keyboard after selection.
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Rent & Utilities", callback_data="exp_rent_utilities"),
            InlineKeyboardButton("👷 Salary", callback_data="exp_salary"),
        ],
        [
            InlineKeyboardButton("📋 Taxes", callback_data="exp_taxes"),
            InlineKeyboardButton("🧪 Chemicals", callback_data="exp_chemicals"),
        ],
        [
            InlineKeyboardButton("💄 Cosmetics etc", callback_data="exp_cosmetics"),
            InlineKeyboardButton("🛁 Guest Amenities", callback_data="exp_guest_amenities"),
        ],
        [
            InlineKeyboardButton("💻 Software", callback_data="exp_software"),
            InlineKeyboardButton("📦 Other", callback_data="exp_other"),
        ],
        [
            InlineKeyboardButton("🏦 Depreciation fund", callback_data="exp_depreciation"),
            InlineKeyboardButton("📣 Advertisement", callback_data="exp_advertisement"),
        ],
        [
            InlineKeyboardButton("💸 Commissions", callback_data="exp_commissions"),
            InlineKeyboardButton("🧺 Laundry", callback_data="exp_laundry"),
        ],
    ])


def expense_subcategory_keyboard(category_key: str) -> InlineKeyboardMarkup:
    """Subcategory keyboard for categories that require a second selection.

    Builds buttons from EXPENSE_SUBCATEGORY_MAP[category_key].
    Returns None if the category has no subcategories.
    """
    subcats = EXPENSE_SUBCATEGORY_MAP.get(category_key, {})
    items = list(subcats.items())  # [(callback, label), ...]

    rows = []
    # Pair buttons into rows of 2
    for i in range(0, len(items), 2):
        row = []
        for cb, label in items[i:i + 2]:
            row.append(InlineKeyboardButton(label, callback_data=cb))
        rows.append(row)

    return InlineKeyboardMarkup(rows)


def expense_property_keyboard() -> InlineKeyboardMarkup:
    """Property for expense (includes 'Всі' = all properties)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Гніздечко", callback_data="prop_gnizd"),
            InlineKeyboardButton("🐦 Чайка", callback_data="prop_chaika"),
        ],
        [
            InlineKeyboardButton("🦢 Чапля", callback_data="prop_chaplia"),
            InlineKeyboardButton("🏘 Всі", callback_data="prop_all"),
        ],
        [InlineKeyboardButton("⏭ Пропустити", callback_data="prop_skip")],
    ])


def payment_method_keyboard() -> InlineKeyboardMarkup:
    """Expense payment method: Cash or Bank Transfer."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 Cash", callback_data="method_cash"),
            InlineKeyboardButton("🏦 Bank Transfer", callback_data="method_transfer"),
        ],
    ])


def paid_by_keyboard() -> InlineKeyboardMarkup:
    """Who paid for this expense."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Nestor", callback_data="paidby_nestor"),
            InlineKeyboardButton("👤 Ihor", callback_data="paidby_ihor"),
        ],
        [
            InlineKeyboardButton("👤 Ira", callback_data="paidby_ira"),
            InlineKeyboardButton("👤 Other", callback_data="paidby_other"),
        ],
        [
            InlineKeyboardButton("🏦 Account", callback_data="paidby_account"),
        ],
    ])


def receipt_skip_keyboard() -> InlineKeyboardMarkup:
    """Skip button for receipt photo step."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустити", callback_data="receipt_skip")],
    ])


def notes_skip_keyboard() -> InlineKeyboardMarkup:
    """Skip button for notes step."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустити", callback_data="notes_skip")],
    ])


def duplicate_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirm or cancel when duplicate income detected."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Так, зберегти", callback_data="dup_confirm"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cancel"),
        ],
    ])


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button — available at every step."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ])
