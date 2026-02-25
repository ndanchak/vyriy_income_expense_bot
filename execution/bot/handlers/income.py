"""
Income OCR flow handler.

Ports the entire Make.com blueprint (31 modules) into a Python state machine.
Photo → OCR → Parse → Property → Payment/Duration → Platform → Account → Dates → Save.
"""

import logging

import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    PROPERTY_MAP,
    PAYMENT_TYPE_MAP,
    PLATFORM_MAP,
    SUP_DURATION_MAP,
    ACCOUNT_TYPE_MAP,
)
from database.models import BotSession
from utils.state import get_session, set_session, update_context, clear_session
from utils.parsers import parse_monobank_ocr, parse_dates_input
from utils.keyboards import (
    property_keyboard,
    property_toggle_keyboard,
    sup_duration_keyboard,
    payment_type_keyboard,
    platform_keyboard,
    account_type_keyboard,
    dates_skip_keyboard,
)
from utils.formatters import (
    format_ocr_summary,
    format_income_confirmation,
    format_ask_payment_type,
    format_ask_platform,
    format_ask_account_type,
    format_ask_dates,
    format_ask_sup_duration,
    format_ask_property,
)
from handlers.common import finalize_income

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point: OCR text already extracted by photo router
# ---------------------------------------------------------------------------

async def handle_photo_with_ocr(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ocr_text: str
) -> None:
    """Handle Monobank screenshot — parse OCR text and start income flow.

    Called by handle_photo_router() in common.py after download + OCR + classification.
    Session existence is already checked by the router.

    Equivalent to Make.com modules 6b-7: parse → show summary → ask property.
    """
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Parse Monobank OCR text
    parsed = parse_monobank_ocr(ocr_text)
    logger.info("Parsed Monobank OCR: %s", parsed)

    # Save session
    session_ctx = {
        "ocr_sender": parsed["sender_name"],
        "ocr_amount": str(parsed["amount"]) if parsed["amount"] else "",
        "ocr_date": parsed["date"],
        "ocr_purpose": parsed["purpose"],
        "source": "ocr",
    }
    await set_session(pool, chat_id, user_id, "income:awaiting_property", session_ctx)

    # Send summary + property keyboard (Make.com module 7)
    await update.message.reply_text(
        format_ocr_summary(parsed),
        reply_markup=property_keyboard(),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Callback handler: state machine for income flow
# ---------------------------------------------------------------------------

async def handle_income_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle callback_query presses during income flow.

    Replaces Make.com modules 8-29: the chain of Wait→Answer→Route→Ask→Wait.
    """
    query = update.callback_query
    await query.answer()

    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    data = query.data
    ctx = dict(session.context)

    # --- Property selection (multi-select toggle) ---
    if state in ("income:awaiting_property", "income_manual:awaiting_property"):
        selected = ctx.get("properties", [])

        if data == "prop_confirm":
            # User confirmed selection → proceed to next step
            if "prop_sup" in selected:
                # SUP branch: ask duration (Make.com module 11)
                next_state = state.replace("awaiting_property", "awaiting_sup_duration")
                await update_context(pool, chat_id, next_state, ctx)
                await query.edit_message_text(
                    format_ask_sup_duration(),
                    reply_markup=sup_duration_keyboard(),
                    parse_mode="Markdown",
                )
            else:
                # Normal property: ask payment type
                next_state = state.replace("awaiting_property", "awaiting_payment_type")
                await update_context(pool, chat_id, next_state, ctx)
                await query.edit_message_text(
                    format_ask_payment_type(),
                    reply_markup=payment_type_keyboard(),
                    parse_mode="Markdown",
                )

        elif data == "prop_skip":
            # Skip: go to payment type with empty properties
            ctx["properties"] = []
            next_state = state.replace("awaiting_property", "awaiting_payment_type")
            await update_context(pool, chat_id, next_state, ctx)
            await query.edit_message_text(
                format_ask_payment_type(),
                reply_markup=payment_type_keyboard(),
                parse_mode="Markdown",
            )

        elif data == "prop_sup":
            # SUP is exclusive — clear all others, set only SUP
            selected = ["prop_sup"]
            ctx["properties"] = selected
            await update_context(pool, chat_id, state, ctx)
            await query.edit_message_text(
                format_ask_property(),
                reply_markup=property_toggle_keyboard(selected),
                parse_mode="Markdown",
            )

        elif data.startswith("prop_"):
            # Toggle property in/out of selected list
            if data in selected:
                selected.remove(data)
            else:
                # If SUP was selected, clear it when adding a normal property
                if "prop_sup" in selected:
                    selected.remove("prop_sup")
                selected.append(data)
            ctx["properties"] = selected
            await update_context(pool, chat_id, state, ctx)
            await query.edit_message_text(
                format_ask_property(),
                reply_markup=property_toggle_keyboard(selected),
                parse_mode="Markdown",
            )

    # --- SUP Duration ---
    elif state in ("income:awaiting_sup_duration", "income_manual:awaiting_sup_duration"):
        ctx["sup_duration"] = data
        ctx["payment_type"] = "Сапи"  # auto-set (Make.com module 30 logic)

        # Auto-detect cash for SUP (Make.com module 28)
        purpose = ctx.get("ocr_purpose", "")
        if "готівка" in purpose.lower():
            ctx["account_type"] = "acc_cash"
        else:
            ctx["account_type"] = "acc_account"

        # Skip payment type and account type, go to platform
        prefix = state.split(":")[0]
        next_state = f"{prefix}:awaiting_platform"
        await update_context(pool, chat_id, next_state, ctx)
        await query.edit_message_text(
            format_ask_platform(),
            reply_markup=platform_keyboard(),
            parse_mode="Markdown",
        )

    # --- Payment Type ---
    elif state in ("income:awaiting_payment_type", "income_manual:awaiting_payment_type"):
        ctx["payment_type"] = data
        prefix = state.split(":")[0]
        next_state = f"{prefix}:awaiting_platform"
        await update_context(pool, chat_id, next_state, ctx)
        await query.edit_message_text(
            format_ask_platform(),
            reply_markup=platform_keyboard(),
            parse_mode="Markdown",
        )

    # --- Platform ---
    elif state in ("income:awaiting_platform", "income_manual:awaiting_platform"):
        ctx["platform"] = data

        # If SUP, skip account type (already set)
        is_sup = "prop_sup" in ctx.get("properties", [])
        prefix = state.split(":")[0]

        if is_sup:
            next_state = f"{prefix}:awaiting_dates"
            await update_context(pool, chat_id, next_state, ctx)
            await query.edit_message_text(
                format_ask_dates(),
                reply_markup=dates_skip_keyboard(),
                parse_mode="Markdown",
            )
        else:
            next_state = f"{prefix}:awaiting_account_type"
            await update_context(pool, chat_id, next_state, ctx)
            await query.edit_message_text(
                format_ask_account_type(),
                reply_markup=account_type_keyboard(),
                parse_mode="Markdown",
            )

    # --- Account Type ---
    elif state in ("income:awaiting_account_type", "income_manual:awaiting_account_type"):
        ctx["account_type"] = data
        prefix = state.split(":")[0]
        next_state = f"{prefix}:awaiting_dates"
        await update_context(pool, chat_id, next_state, ctx)
        await query.edit_message_text(
            format_ask_dates(),
            reply_markup=dates_skip_keyboard(),
            parse_mode="Markdown",
        )

    # --- Dates skip ---
    elif state in ("income:awaiting_dates", "income_manual:awaiting_dates"):
        if data == "dates_skip":
            ctx["dates_skipped"] = True
            # Lock state to prevent duplicate writes on double-click/retry
            prefix = state.split(":")[0]
            await update_context(pool, chat_id, f"{prefix}:finalizing", ctx)
            # Finalize
            await _finalize_and_confirm(pool, chat_id, ctx, query)


async def _finalize_and_confirm(pool, chat_id, ctx, query) -> None:
    """Write transaction and send confirmation."""
    tx_id = await finalize_income(pool, chat_id, ctx)

    if tx_id:
        confirmation = format_income_confirmation(ctx)
        await query.edit_message_text(confirmation, parse_mode="Markdown")
    else:
        await query.edit_message_text("❌ Помилка збереження. Спробуйте ще раз.")

    await clear_session(pool, chat_id)


# ---------------------------------------------------------------------------
# Text handler: dates input
# ---------------------------------------------------------------------------

async def handle_income_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: BotSession,
) -> None:
    """Handle text input during income OCR flow (dates step)."""
    pool: asyncpg.Pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id
    state = session.state
    text = update.message.text.strip()

    if state == "income:awaiting_dates":
        ctx = dict(session.context)
        checkin, checkout = parse_dates_input(text)
        ctx["checkin"] = checkin
        ctx["checkout"] = checkout

        # Lock state to prevent duplicate writes
        await update_context(pool, chat_id, "income:finalizing", ctx)

        # Finalize
        tx_id = await finalize_income(pool, chat_id, ctx)

        if tx_id:
            confirmation = format_income_confirmation(ctx)
            await update.message.reply_text(confirmation, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Помилка збереження. Спробуйте ще раз.")

        await clear_session(pool, chat_id)
