"""سیستمِ پشتیبانی (تیکت) + ریلیِ جوابِ ادمین + ویزاردِ تنظیمِ گروهِ اطلاع‌رسانی.

جریانِ کار (شبیهِ ربات نت‌ملی، ولی پورت‌شده به python-telegram-bot):
  • کاربر دکمه‌ی «💬 پشتیبانی» رو می‌زنه → پیامش رو می‌نویسه → تیکت ساخته و کارتش به
    تاپیکِ «تیکت‌ها»ی گروهِ پشتیبانی فرستاده می‌شه (اگه تنظیم نشده باشه، دایرکت به ادمین‌ها).
  • ادمین داخلِ همون تاپیک روی کارتِ تیکت «ریپلای» می‌کنه و جواب می‌نویسه → جواب مستقیم
    برای کاربر ریلی می‌شه. (ریپلای به پیامِ خودِ ربات حتی با privacy mode هم به ربات می‌رسه.)
  • تنظیمِ گروه/تاپیک‌ها بدونِ دست‌کاریِ .env انجام می‌شه: ادمین «لینکِ تاپیک» رو می‌فرسته،
    ربات آیدیِ گروه (-100…) و آیدیِ تاپیک رو از روی لینک درمیاره و در دیتابیس ذخیره می‌کنه.
"""
from __future__ import annotations

import html
import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from InstaDownloadBot import config, database, keyboards
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import _user_lang

logger = logging.getLogger(__name__)

# وضعیت‌های گفت‌وگو
SUPPORT_WAIT, GH_TICKETS, GH_ALERTS = range(3)

# سقفِ تیکتِ بازِ هم‌زمان برای هر کاربر (ضدِ اسپم)
_MAX_OPEN_TICKETS = 2


# ====================== پشتیبانی (کاربر → ادمین) ======================
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ورودیِ پشتیبانی: از دکمه‌ی reply، دستورِ /support یا دکمه‌ی این‌لاینِ زیرِ خطای دانلود."""
    if update.callback_query:
        await update.callback_query.answer()
    user = update.effective_user
    await database.upsert_user(user.id, user.first_name, user.username)
    lang = await _user_lang(user.id)
    tr = t.L(lang)

    if await database.count_open_tickets_for_user(user.id) >= _MAX_OPEN_TICKETS:
        await context.bot.send_message(
            update.effective_chat.id,
            tr.SUPPORT_TOO_MANY,
            reply_markup=keyboards.main_keyboard(config.is_admin(user.id), lang),
        )
        return ConversationHandler.END

    await context.bot.send_message(
        update.effective_chat.id,
        tr.SUPPORT_ASK,
        reply_markup=keyboards.cancel_keyboard(lang),
    )
    return SUPPORT_WAIT


async def support_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = await _user_lang(user.id)
    tr = t.L(lang)
    text = (update.effective_message.text or "").strip()
    if not text:
        await update.effective_message.reply_text(
            tr.SUPPORT_ASK, reply_markup=keyboards.cancel_keyboard(lang)
        )
        return SUPPORT_WAIT

    ticket_id = await database.create_ticket(user.id, user.first_name, user.username, text)
    await _post_ticket(context, ticket_id, user, text)
    await update.effective_message.reply_text(
        tr.SUPPORT_SENT,
        reply_markup=keyboards.main_keyboard(config.is_admin(user.id), lang),
    )
    return ConversationHandler.END


async def support_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = await _user_lang(user.id)
    tr = t.L(lang)
    await update.effective_message.reply_text(
        tr.SUPPORT_CANCELLED,
        reply_markup=keyboards.main_keyboard(config.is_admin(user.id), lang),
    )
    return ConversationHandler.END


async def _post_ticket(context: ContextTypes.DEFAULT_TYPE, ticket_id: int, user, message_text: str) -> None:
    """کارتِ تیکت رو به تاپیکِ گروه می‌فرسته؛ اگه گروه تنظیم نشده، دایرکت به ادمین‌ها.

    کارت برای ادمین‌ها/گروهه، پس به زبانِ پیش‌فرض (فارسی) می‌مونه.
    """
    name = html.escape(user.first_name or "—")
    handle = f" (@{html.escape(user.username)})" if user.username else ""
    card = t.SUPPORT_TICKET_CARD.format(
        ticket_id=ticket_id,
        name=name,
        handle=handle,
        user_id=user.id,
        message=html.escape(message_text),
    )

    group_id = await database.get_support_group_id()
    thread = await database.get_support_thread_tickets()
    if group_id and thread:
        try:
            sent = await context.bot.send_message(
                int(group_id),
                card,
                message_thread_id=thread,
                parse_mode=ParseMode.HTML,
            )
            await database.set_ticket_group_msg(ticket_id, int(group_id), sent.message_id)
            return
        except Exception:  # noqa: BLE001 - اگه ارسال به گروه نشد، می‌افتیم رو دایرکتِ ادمین
            logger.exception("Could not post ticket #%s to group; falling back to admin DMs", ticket_id)

    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, card, parse_mode=ParseMode.HTML)
        except Exception:  # noqa: BLE001
            logger.warning("Could not DM ticket #%s to admin %s", ticket_id, admin_id)


# ====================== ریلیِ جواب (ادمین → کاربر) ======================
async def group_reply_relay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """وقتی ادمین داخلِ گروهِ پشتیبانی روی کارتِ تیکت ریپلای می‌کنه، جواب رو به کاربر می‌رسونه."""
    msg = update.effective_message
    if not msg or not msg.reply_to_message:
        return

    group_id = await database.get_support_group_id()
    if not group_id or str(msg.chat_id) != group_id:
        return

    ticket = await database.get_ticket_by_group_msg(msg.reply_to_message.message_id)
    if not ticket:
        return  # ریپلای به پیامی که تیکت نیست — بی‌صدا نادیده بگیر

    reply_text = (msg.text or msg.caption or "").strip()
    if not reply_text:
        return

    # جواب برای خودِ کاربره؛ به زبانِ همون کاربر فرستاده می‌شه.
    owner_lang = await _user_lang(ticket.user_id)
    try:
        await context.bot.send_message(
            ticket.user_id,
            t.L(owner_lang).SUPPORT_REPLY_TO_USER.format(text=html.escape(reply_text)),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.main_keyboard(config.is_admin(ticket.user_id), owner_lang),
        )
        await database.mark_ticket_answered(ticket.id)
        await msg.reply_text(t.SUPPORT_REPLY_DONE)  # تأیید برای ادمین (در گروه) → فارسی
    except Exception:  # noqa: BLE001 - کاربر شاید ربات رو بلاک کرده باشه
        logger.exception("Could not relay support reply to user %s", ticket.user_id)
        await msg.reply_text(t.SUPPORT_REPLY_FAILED)


# ====================== ویزاردِ تنظیمِ گروهِ اطلاع‌رسانی ======================
async def _resolve_topic(context: ContextTypes.DEFAULT_TYPE, raw: str):
    """از «لینکِ تاپیک» آیدیِ گروه (-100…) و آیدیِ تاپیک رو درمیاره. (group_id_str, thread_int) یا (None, None)."""
    raw = (raw or "").strip()
    # گروهِ خصوصی: t.me/c/<عددِ داخلی>/<تاپیک>
    m = re.search(r"t\.me/c/(\d+)/(\d+)", raw)
    if m:
        return f"-100{m.group(1)}", int(m.group(2))
    # گروهِ عمومی با یوزرنیم: t.me/<username>/<تاپیک> → آیدیِ عددی رو با get_chat می‌گیریم
    m = re.search(r"t\.me/([A-Za-z0-9_]{4,})/(\d+)", raw)
    if m:
        try:
            chat = await context.bot.get_chat("@" + m.group(1))
            return str(chat.id), int(m.group(2))
        except Exception:  # noqa: BLE001
            return None, None
    return None, None


async def _status_lines():
    group = await database.get_support_group_id() or "—"
    tickets = await database.get_support_thread_tickets() or "—"
    alerts = await database.get_support_thread_alerts() or "—"
    return group, tickets, alerts


async def gh_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not (update.effective_user and config.is_admin(update.effective_user.id)):
        return ConversationHandler.END
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    group, tickets, alerts = await _status_lines()
    await update.effective_message.reply_text(
        tr.GROUP_HUB_INTRO.format(group=group, tickets=tickets, alerts=alerts),
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_message(
        update.effective_chat.id,
        tr.GROUP_HUB_ASK_TICKETS,
        reply_markup=keyboards.skip_cancel_keyboard(lang),
    )
    return GH_TICKETS


async def gh_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    text = (update.effective_message.text or "").strip()
    if text in keyboards.BTN_SKIP.values():
        await context.bot.send_message(
            update.effective_chat.id,
            tr.GROUP_HUB_ASK_ALERTS,
            reply_markup=keyboards.skip_cancel_keyboard(lang),
        )
        return GH_ALERTS

    group_id, thread = await _resolve_topic(context, text)
    if not group_id or not thread:
        await update.effective_message.reply_text(tr.GROUP_HUB_BAD_LINK)
        return GH_TICKETS

    await database.set_support_group_id(group_id)
    await database.set_support_thread_tickets(thread)
    try:
        await context.bot.send_message(int(group_id), tr.GROUP_HUB_TEST_TICKETS, message_thread_id=thread)
        await update.effective_message.reply_text(tr.GROUP_HUB_TICKETS_SET)
    except Exception:  # noqa: BLE001
        logger.exception("group-hub: cannot send to tickets topic")
        await update.effective_message.reply_text(tr.GROUP_HUB_SEND_FAILED, parse_mode=ParseMode.HTML)

    await context.bot.send_message(
        update.effective_chat.id,
        tr.GROUP_HUB_ASK_ALERTS,
        reply_markup=keyboards.skip_cancel_keyboard(lang),
    )
    return GH_ALERTS


async def gh_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    text = (update.effective_message.text or "").strip()
    if text not in keyboards.BTN_SKIP.values():
        group_id, thread = await _resolve_topic(context, text)
        if not group_id or not thread:
            await update.effective_message.reply_text(tr.GROUP_HUB_BAD_LINK)
            return GH_ALERTS
        await database.set_support_group_id(group_id)
        await database.set_support_thread_alerts(thread)
        try:
            await context.bot.send_message(int(group_id), tr.GROUP_HUB_TEST_ALERTS, message_thread_id=thread)
            await update.effective_message.reply_text(tr.GROUP_HUB_ALERTS_SET)
        except Exception:  # noqa: BLE001
            logger.exception("group-hub: cannot send to alerts topic")
            await update.effective_message.reply_text(tr.GROUP_HUB_SEND_FAILED, parse_mode=ParseMode.HTML)

    group, tickets, alerts = await _status_lines()
    await context.bot.send_message(
        update.effective_chat.id,
        tr.GROUP_HUB_DONE.format(group=group, tickets=tickets, alerts=alerts),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.main_keyboard(True, lang),
    )
    return ConversationHandler.END


async def gh_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    await update.effective_message.reply_text(
        tr.GROUP_HUB_CANCELLED, reply_markup=keyboards.main_keyboard(True, lang)
    )
    return ConversationHandler.END


# ====================== ثبتِ هندلرها ======================
def _cancel_re():
    # دکمه‌ی «لغو» به هر دو زبان (فارسی/انگلیسی)
    return filters.Regex(keyboards.btn_regex(keyboards.BTN_CANCEL))


def build_support_handlers() -> list:
    """همه‌ی هندلرهای پشتیبانی/ریلی/تنظیمِ گروه رو برای ثبت در اپلیکیشن برمی‌گردونه."""
    text_in_private = filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND

    support_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(keyboards.btn_regex(keyboards.BTN_SUPPORT)),
                support_start,
            ),
            CommandHandler("support", support_start, filters=filters.ChatType.PRIVATE),
            CallbackQueryHandler(support_start, pattern=f"^{keyboards.SUPPORT_CB}$"),
        ],
        states={
            SUPPORT_WAIT: [MessageHandler(text_in_private & ~_cancel_re(), support_receive)],
        },
        fallbacks=[
            MessageHandler(_cancel_re(), support_cancel),
            CommandHandler("cancel", support_cancel),
        ],
        allow_reentry=True,
        name="support_conv",
    )

    gh_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(keyboards.btn_regex(keyboards.BTN_GROUP_HUB)),
                gh_start,
            ),
        ],
        states={
            GH_TICKETS: [MessageHandler(text_in_private & ~_cancel_re(), gh_tickets)],
            GH_ALERTS: [MessageHandler(text_in_private & ~_cancel_re(), gh_alerts)],
        },
        fallbacks=[
            MessageHandler(_cancel_re(), gh_cancel),
            CommandHandler("cancel", gh_cancel),
        ],
        allow_reentry=True,
        name="group_hub_conv",
    )

    # ریلیِ جوابِ ادمین: فقط داخلِ گروه‌ها و فقط روی پیام‌هایی که «ریپلای» هستن
    relay = MessageHandler(
        filters.ChatType.GROUPS & filters.REPLY & ~filters.COMMAND,
        group_reply_relay,
    )

    return [support_conv, gh_conv, relay]
