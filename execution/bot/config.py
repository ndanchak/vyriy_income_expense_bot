"""
Configuration module — loads environment variables and defines constant mappings.

All callback_data → display label dictionaries live here, replacing the
switch() calls in Make.com modules 22-29.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from execution/bot/)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

# --- Telegram ---
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_GROUP_CHAT_ID: int = int(os.environ.get("TELEGRAM_GROUP_CHAT_ID", "0"))
TELEGRAM_OWNER_CHAT_ID: int = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", "0"))

# --- Database ---
DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/vyriy_dev")

# --- Google Vision OCR ---
GOOGLE_VISION_API_KEY: str = os.environ.get("GOOGLE_VISION_API_KEY", "")

# --- Google Sheets ---
GOOGLE_SHEETS_CREDS_JSON: str = os.environ.get("GOOGLE_SHEETS_CREDS_JSON", "")  # base64
GOOGLE_SHEETS_ID: str = os.environ.get("GOOGLE_SHEETS_ID", "")

# --- Google Drive (receipt uploads) ---
GOOGLE_DRIVE_FOLDER_ID: str = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

# --- Webhook ---
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")
WEBHOOK_URL: str = os.environ.get("WEBHOOK_URL", "")

# ---------------------------------------------------------------------------
# Callback data → display label mappings
# ---------------------------------------------------------------------------

# Property selection (Make.com module 22 switch)
PROPERTY_MAP = {
    "prop_gnizd": "Гніздечко",
    "prop_chaika": "Чайка",
    "prop_chaplia": "Чапля",
    "prop_sup": "SUP Rental",
}

# Payment type (Make.com module 23 switch)
PAYMENT_TYPE_MAP = {
    "pay_prepay": "Передоплата",
    "pay_balance": "Доплата",
    "pay_full": "Оплата",
}

# Platform (Make.com module 24 switch)
PLATFORM_MAP = {
    "plat_inst": "INST",
    "plat_bc": "BC",
    "plat_airbnb": "Airbnb",
    "plat_hutshub": "HutsHub",
    "plat_direct": "Direct",
}

# SUP duration (Make.com module 25 switch)
SUP_DURATION_MAP = {
    "dur_1h": "1 година",
    "dur_2h": "2 години",
    "dur_3h": "3 години",
    "dur_halfday": "Пів дня (4г)",
    "dur_fullday": "Весь день",
}

# Account type
ACCOUNT_TYPE_MAP = {
    "acc_account": "Account",
    "acc_cash": "Cash",
}

# Expense categories
EXPENSE_CATEGORY_MAP = {
    "exp_cleaning": "Прибирання",
    "exp_utilities": "Комунальні",
    "exp_maintenance": "Обслуговування",
    "exp_materials": "Матеріали",
    "exp_marketing": "Маркетинг",
    "exp_other": "Інше",
}

# Expense property (includes "Всі" option)
EXPENSE_PROPERTY_MAP = {
    "prop_gnizd": "Гніздечко",
    "prop_chaika": "Чайка",
    "prop_chaplia": "Чапля",
    "prop_all": "Всі",
}

# Expense payment method
PAYMENT_METHOD_MAP = {
    "method_cash": "Готівка",
    "method_account": "Рахунок",
}
