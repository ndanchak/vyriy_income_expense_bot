"""
Vyriy House Bot — Entry Point

FastAPI webhook server + python-telegram-bot Application.
Handles income (OCR + manual) and expense flows.

Local dev:   uvicorn main:api --host 0.0.0.0 --port 8000 --reload
Production:  Railway auto-deploys via Dockerfile
"""

import hmac
import json as _json
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET, DATABASE_URL
from database.connection import init_pool, close_pool, run_migration
from handlers.common import (
    is_authorized,
    handle_cancel,
    handle_photo_router,
    handle_callback_router,
    handle_text_router,
)
from handlers.income_manual import handle_dohid_command
from handlers.expense import handle_vitrata_command
from services.sheets_sync import setup_sync_scheduler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress httpx INFO logs — they contain the bot token in URLs
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Telegram bot application (global — initialized on startup)
# ---------------------------------------------------------------------------
bot_app: Application | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — replaces deprecated on_event startup/shutdown."""
    global bot_app

    # --- STARTUP ---
    # 1. Database
    pool = await init_pool(DATABASE_URL)

    # Run migration if tables don't exist
    migration_path = Path(__file__).parent / "database" / "migrations" / "001_initial.sql"
    await run_migration(pool, str(migration_path))

    # 2. Build bot application
    bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    bot_app.bot_data["db_pool"] = pool

    # 3. Register handlers (order matters — more specific first)
    # Commands (Telegram only allows Latin letters, digits, underscores)
    bot_app.add_handler(CommandHandler("income", handle_dohid_command))
    bot_app.add_handler(CommandHandler("expense", handle_vitrata_command))
    bot_app.add_handler(CommandHandler("cancel", handle_cancel))
    bot_app.add_handler(CommandHandler("start", handle_start))
    bot_app.add_handler(CommandHandler("help", handle_help))

    # Callbacks (inline keyboard button presses)
    bot_app.add_handler(CallbackQueryHandler(handle_callback_router))

    # Photos (income OCR or expense receipt)
    bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo_router))

    # Text (amounts, names, dates, notes)
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_router))

    # 4. Initialize and start bot
    await bot_app.initialize()
    await bot_app.start()

    # 5. Set webhook (production) or polling (local dev)
    if WEBHOOK_URL:
        if not WEBHOOK_URL.startswith("https://"):
            raise ValueError("WEBHOOK_URL must use HTTPS for security — got: %s" % WEBHOOK_URL[:30])
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await bot_app.bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
        )
        logger.info("Webhook set: %s", webhook_url)
    else:
        # Local dev: delete any old webhook and start polling
        await bot_app.bot.delete_webhook(drop_pending_updates=True)
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("No WEBHOOK_URL — running in polling mode (local dev)")

    # 6. Start Sheets sync scheduler
    setup_sync_scheduler(pool)

    logger.info("Vyriy House Bot started successfully")

    yield  # Application runs here

    # --- SHUTDOWN ---
    if bot_app:
        if bot_app.updater and bot_app.updater.running:
            await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
    await close_pool()
    logger.info("Vyriy House Bot shut down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
api = FastAPI(title="Vyriy House Bot", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Rate limiter (simple in-memory, per-IP)
# ---------------------------------------------------------------------------
_rate_limit_window = 60  # seconds
_rate_limit_max = 60     # max requests per window
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _is_rate_limited(client_ip: str) -> bool:
    """Check if a client IP has exceeded the rate limit."""
    now = time.monotonic()
    bucket = _rate_buckets[client_ip]
    # Remove expired entries
    _rate_buckets[client_ip] = [ts for ts in bucket if now - ts < _rate_limit_window]
    if len(_rate_buckets[client_ip]) >= _rate_limit_max:
        return True
    _rate_buckets[client_ip].append(now)
    return False


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@api.post("/webhook")
async def webhook(request: Request) -> Response:
    """Telegram webhook endpoint — receives updates from Telegram servers."""
    # Rate limiting (per client IP)
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip):
        logger.warning("Rate limited: %s", client_ip)
        return Response(status_code=429)

    # SECURITY: Reject if webhook secret is not configured
    if not WEBHOOK_SECRET:
        logger.error("WEBHOOK_SECRET not configured — rejecting all webhook requests")
        return Response(status_code=500)

    # Verify secret token (constant-time comparison to prevent timing attacks)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        logger.warning("Webhook secret mismatch from %s", client_ip)
        return Response(status_code=403)

    # Guard against bot_app not initialized
    if bot_app is None:
        logger.error("Bot application not initialized")
        return Response(status_code=503)

    # Limit request body size (1 MB — Telegram updates are typically < 100 KB)
    body = await request.body()
    if len(body) > 1_048_576:
        logger.warning("Webhook payload too large: %d bytes", len(body))
        return Response(status_code=413)

    data = _json.loads(body)
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return Response(status_code=200)


@api.get("/health")
async def health():
    """Health check endpoint for Railway. Minimal response to avoid leaking identity."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Utility commands
# ---------------------------------------------------------------------------

async def handle_start(update: Update, context) -> None:
    """Handle /start command."""
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "🏠 *Vyriy House Bot*\n"
        "\n"
        "Доступні команди:\n"
        "📸 Надішліть скріншот Monobank — автоматичний запис доходу\n"
        "💰 /income — ручне введення доходу\n"
        "💸 /expense — запис витрати\n"
        "❌ /cancel — скасувати поточну операцію\n"
        "❓ /help — довідка",
        parse_mode="Markdown",
    )


async def handle_help(update: Update, context) -> None:
    """Handle /help command."""
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "📖 *Довідка*\n"
        "\n"
        "*Запис доходу (скріншот):*\n"
        "Надішліть фото з Monobank → бот розпізнає суму, "
        "відправника, дату → запитає об'єкт, тип оплати, платформу, дати.\n"
        "\n"
        "*Запис доходу (вручну):*\n"
        "/income → бот запитає суму, ім'я гостя, об'єкт, тип оплати, платформу, дати.\n"
        "\n"
        "*Запис витрати:*\n"
        "/expense → категорія, сума, опис, спосіб оплати, хто оплатив, "
        "чек (необов'язково).\n"
        "Швидкий: `/expense Category;Amount;Description;Paid By`\n"
        "\n"
        "*Скасування:*\n"
        "/cancel — на будь-якому кроці скасує поточну операцію.\n"
        "\n"
        "Дані зберігаються в базу даних та дублюються в Google Sheets.",
        parse_mode="Markdown",
    )
