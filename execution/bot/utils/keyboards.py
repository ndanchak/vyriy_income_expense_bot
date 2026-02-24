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
    """Property selection — Make.com module 7."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Гніздечко", callback_data="prop_gnizd"),
            InlineKeyboardButton("🐦 Чайка", callback_data="prop_chaika"),
        ],
        [
            InlineKeyboardButton("🦢 Чапля", callback_data="prop_chaplia"),
            InlineKeyboardButton("🏄 SUP Rental", callback_data="prop_sup"),
        ],
        [InlineKeyboardButton("⏭ Пропустити", callback_data="prop_skip")],
    ])


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
            InlineKeyboardButton("📸 INST", callback_data="plat_inst"),
            InlineKeyboardButton("🏨 BC", callback_data="plat_bc"),
        ],
        [
            InlineKeyboardButton("✈️ Airbnb", callback_data="plat_airbnb"),
            InlineKeyboardButton("🔗 HutsHub", callback_data="plat_hutshub"),
        ],
        [
            InlineKeyboardButton("📞 Direct", callback_data="plat_direct"),
            InlineKeyboardButton("⏭ Пропустити", callback_data="plat_skip"),
        ],
    ])


def account_type_keyboard() -> InlineKeyboardMarkup:
    """Account type: bank transfer or cash."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏦 Рахунок", callback_data="acc_account"),
            InlineKeyboardButton("💵 Готівка", callback_data="acc_cash"),
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
