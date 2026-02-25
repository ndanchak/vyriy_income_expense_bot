"""
Telegram InlineKeyboard builders.

Replaces hardcoded JSON reply_markup strings from Make.com modules 7, 11, 14, 17, 19.
Emojis preserved for visual consistency with the existing Make.com bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ---------------------------------------------------------------------------
# Income keyboards
# ---------------------------------------------------------------------------

def property_keyboard() -> InlineKeyboardMarkup:
    """Property selection — Make.com module 7 (legacy single-select)."""
    return property_toggle_keyboard([])


# Property button definitions: (callback_data, default_emoji, label)
_PROPERTY_BUTTONS = [
    ("prop_gnizd", "🏠", "Гніздечко"),
    ("prop_chaika", "🐦", "Чайка"),
    ("prop_chaplia", "🦢", "Чапля"),
    ("prop_sup", "🏄", "SUP Rental"),
]


def property_toggle_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    """Multi-select property keyboard with toggle checkmarks.

    Tapping a property toggles ✅ on/off. When any property is selected,
    a "Підтвердити" button appears. SUP is exclusive (handled by the callback).
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
    """Expense category selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧹 Прибирання", callback_data="exp_cleaning"),
            InlineKeyboardButton("💡 Комунальні", callback_data="exp_utilities"),
        ],
        [
            InlineKeyboardButton("🔧 Обслуговування", callback_data="exp_maintenance"),
            InlineKeyboardButton("📦 Матеріали", callback_data="exp_materials"),
        ],
        [
            InlineKeyboardButton("📣 Маркетинг", callback_data="exp_marketing"),
            InlineKeyboardButton("📋 Інше", callback_data="exp_other"),
        ],
    ])


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
    """Expense payment method: cash or bank."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 Готівка", callback_data="method_cash"),
            InlineKeyboardButton("🏦 Рахунок", callback_data="method_account"),
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


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button — available at every step."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ])
