"""دستورهای ادمین: مدیریت کانال‌های اجباری + آمار + نگه‌داری (backup/health/refund)."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from telegram import InputFile, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from InstaDownloadBot import config, database, keyboards
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import _user_lang
from InstaDownloadBot.utils import song, video

logger = logging.getLogger(__name__)

ADD_TITLE, ADD_WAIT, ADD_DAYS, REMOVE_WAIT, PRICE_WAIT, DURATION_WAIT = range(6)


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and config.is_admin(user.id))


def _normalize_identifier(text: str):
    """ورودی ادمین رو به @username یا آیدی عددی تبدیل می‌کنه."""
    text = (text or "").strip()
    link = re.search(r"(?:t\.me/|telegram\.me/)([A-Za-z0-9_]+)", text)
    if link:
        return "@" + link.group(1)
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text.startswith("@"):
        return text
    if re.fullmatch(r"[A-Za-z0-9_]{3,}", text):
        return "@" + text
    return text


# ---------- افزودن کانال (سه‌مرحله‌ای: عنوان → آدرس/لینک → مدتِ موندگاری) ----------
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return ConversationHandler.END
    context.user_data.pop("new_ch", None)
    await update.effective_message.reply_text(
        tr.ADD_CHANNEL_ASK_TITLE, reply_markup=keyboards.cancel_keyboard(lang)
    )
    return ADD_TITLE


async def add_title_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مرحله‌ی ۱: عنوانِ نمایشیِ کانال (همونی که روی دکمه‌ی «عضویت» دیده می‌شه)."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    title = (update.effective_message.text or "").strip()
    context.user_data["new_ch"] = {"title": title}
    await update.effective_message.reply_text(
        tr.ADD_CHANNEL_ASK, reply_markup=keyboards.cancel_keyboard(lang)
    )
    return ADD_WAIT


async def add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مرحله‌ی ۲: آدرس/لینکِ کانال رو می‌گیره، اعتبارسنجی می‌کنه و بعد مدت رو می‌پرسه."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    kb = keyboards.admin_menu_keyboard(lang)
    ident = _normalize_identifier(update.effective_message.text)
    try:
        chat = await context.bot.get_chat(ident)
    except Exception:  # noqa: BLE001
        await update.effective_message.reply_text(tr.ADD_CHANNEL_FAILED, reply_markup=kb)
        return ConversationHandler.END

    try:
        me = await context.bot.get_chat_member(chat.id, context.bot.id)
        if me.status not in ("administrator", "creator"):
            await update.effective_message.reply_text(
                tr.ADD_CHANNEL_BOT_NOT_ADMIN, reply_markup=kb
            )
            return ConversationHandler.END
    except Exception:  # noqa: BLE001
        await update.effective_message.reply_text(
            tr.ADD_CHANNEL_BOT_NOT_ADMIN, reply_markup=kb
        )
        return ConversationHandler.END

    invite_link = None
    if not chat.username:
        try:
            invite_link = await context.bot.export_chat_invite_link(chat.id)
        except Exception:  # noqa: BLE001
            invite_link = None

    data = context.user_data.get("new_ch") or {}
    if not data.get("title"):  # اگه ادمین عنوان نداده بود، از عنوانِ خودِ کانال استفاده کن
        data["title"] = chat.title or (chat.username and f"@{chat.username}") or str(chat.id)
    data.update(
        {"chat_id": chat.id, "username": chat.username, "invite_link": invite_link}
    )
    context.user_data["new_ch"] = data

    await update.effective_message.reply_text(
        tr.ADD_CHANNEL_ASK_DAYS, reply_markup=keyboards.cancel_keyboard(lang)
    )
    return ADD_DAYS


async def add_days_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مرحله‌ی ۳: مدتِ موندگاری به روز (۰ = نامحدود) و ثبتِ نهاییِ کانال."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    kb = keyboards.admin_menu_keyboard(lang)
    raw = (update.effective_message.text or "").strip()
    if not re.fullmatch(r"\d+", raw):  # \d و int() ارقامِ فارسی رو هم می‌پذیرن
        await update.effective_message.reply_text(
            tr.ADD_CHANNEL_BAD_DAYS, reply_markup=keyboards.cancel_keyboard(lang)
        )
        return ADD_DAYS
    days = int(raw)

    data = context.user_data.pop("new_ch", None) or {}
    chat_id = data.get("chat_id")
    if chat_id is None:  # نباید پیش بیاد، ولی محضِ احتیاط
        await update.effective_message.reply_text(tr.ADD_CHANNEL_FAILED, reply_markup=kb)
        return ConversationHandler.END

    added = await database.add_channel(
        chat_id, data.get("title"), data.get("username"), data.get("invite_link"), days=days
    )
    dur = tr.CH_DUR_DAYS.format(days=days) if days > 0 else tr.CH_DUR_UNLIMITED
    msg = tr.ADD_CHANNEL_OK if added else tr.ADD_CHANNEL_RENEWED
    await update.effective_message.reply_text(
        msg.format(title=data.get("title"), dur=dur), reply_markup=kb
    )
    return ConversationHandler.END


# ---------- حذف کانال ----------
async def remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return ConversationHandler.END
    if context.args:
        await _do_remove(update, context, " ".join(context.args), lang)
        return ConversationHandler.END
    await update.effective_message.reply_text(
        tr.REMOVE_CHANNEL_ASK, reply_markup=keyboards.cancel_keyboard(lang)
    )
    return REMOVE_WAIT


async def remove_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    await _do_remove(update, context, update.effective_message.text, lang)
    return ConversationHandler.END


async def _do_remove(
    update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str, lang: str = "fa"
) -> None:
    tr = t.L(lang)
    kb = keyboards.admin_menu_keyboard(lang)
    ident = _normalize_identifier(raw)
    chat_id: int | None = None

    if isinstance(ident, int):
        chat_id = ident
    else:
        uname = ident.lstrip("@").lower()
        for ch in await database.get_channels():
            if ch.username and ch.username.lower() == uname:
                chat_id = ch.chat_id
                break
        if chat_id is None:
            try:
                chat = await context.bot.get_chat(ident)
                chat_id = chat.id
            except Exception:  # noqa: BLE001
                chat_id = None

    if chat_id is not None and await database.remove_channel(chat_id):
        await update.effective_message.reply_text(tr.REMOVE_CHANNEL_OK, reply_markup=kb)
    else:
        await update.effective_message.reply_text(
            tr.REMOVE_CHANNEL_NOT_FOUND, reply_markup=kb
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    await update.effective_message.reply_text(
        tr.CANCELLED, reply_markup=keyboards.admin_menu_keyboard(lang)
    )
    return ConversationHandler.END


# ---------- دستورهای ساده ----------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    await update.effective_message.reply_text(
        tr.ADMIN_PANEL, reply_markup=keyboards.admin_menu_keyboard(lang)
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """از منوی ادمین برگرد به کیبوردِ اصلی."""
    if not _is_admin(update):
        return
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    await update.effective_message.reply_text(
        tr.MENU_MAIN, reply_markup=keyboards.main_keyboard(True, lang)
    )


async def channels_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    channels = await database.get_channels()
    if not channels:
        await update.effective_message.reply_text(tr.CHANNELS_EMPTY)
        return
    lines = [tr.CHANNELS_HEADER]
    for ch in channels:
        ref = f"@{ch.username}" if ch.username else (ch.url or str(ch.chat_id))
        dur = tr.CH_DUR_UNTIL.format(date=ch.expires_at.split(" ")[0]) if ch.expires_at else tr.CH_DUR_UNLIMITED
        lines.append(f"• {ch.title} — {ref}  ({dur})")
    await update.effective_message.reply_text("\n".join(lines))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    users = await database.count_users()
    vip = await database.count_vip()
    channels = await database.count_channels()
    await update.effective_message.reply_text(
        tr.STATS.format(users=users, vip=vip, channels=channels)
    )


# ---------- نگه‌داری: بکاپ، سلامت، بازپرداخت ----------
def _private_only(update: Update) -> bool:
    """آیا چت خصوصیه؟ دستورهای حساس (بکاپ/رفاند) نباید توی گروه اجرا شن."""
    chat = update.effective_chat
    return chat is None or chat.type == "private"


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/backup — فایلِ کاملِ دیتابیس رو (بعد از ادغامِ WAL) برای ادمین می‌فرسته (فقط چتِ خصوصی)."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    if not _private_only(update):
        await update.effective_message.reply_text(tr.SOURCE_PRIVATE_ONLY)
        return
    await update.effective_message.reply_text(tr.BACKUP_WORKING)
    try:
        await database.checkpoint_wal()
        size_kb = config.DB_PATH.stat().st_size / 1024
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(config.DB_PATH, "rb") as fh:
            await update.effective_message.reply_document(
                document=InputFile(fh, filename=f"backup-{ts}.db"),
                caption=tr.BACKUP_CAPTION.format(size=f"{size_kb:.0f}"),
            )
    except Exception as exc:  # noqa: BLE001 - هر خطایی موقعِ بکاپ به ادمین گزارش می‌شه
        logger.warning("Backup failed: %s", exc)
        await update.effective_message.reply_text(tr.BACKUP_FAILED.format(error=exc))


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/health — وضعیتِ منابع و سلامتِ ربات (کوکی/پروکسی/ffmpeg/شناساییِ آهنگ/کش/دیتابیس)."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    cookies = len(await database.get_all_cookies())
    proxies = len(await database.get_all_proxies())
    cache = await database.count_cache()
    users = await database.count_users()
    vip = await database.count_vip()
    try:
        db_size = f"{config.DB_PATH.stat().st_size / 1024:.0f} KB"
    except OSError:
        db_size = "—"
    ffmpeg_ok = "✅" if video.ffmpeg_available() else "❌"
    shazam_ok = "✅" if song.recognition_available() else "❌"
    await update.effective_message.reply_text(
        tr.HEALTH.format(
            users=users, vip=vip, cookies=cookies, proxies=proxies,
            ffmpeg=ffmpeg_ok, shazam=shazam_ok, cache=cache, db_size=db_size,
        )
    )


async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/refund <charge_id|آیدی/یوزرنیم> — بازپرداختِ Telegram Stars (فقط ادمین، چتِ خصوصی).

    آرگومان می‌تونه خودِ charge_id باشه، یا کاربر (آیدیِ عددی/@یوزرنیم) که اون‌وقت
    آخرین پرداختِ بازپرداخت‌نشده‌اش رفاند می‌شه.
    """
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    if not _private_only(update):
        await update.effective_message.reply_text(tr.SOURCE_PRIVATE_ONLY)
        return
    if not context.args:
        await update.effective_message.reply_text(tr.REFUND_USAGE)
        return

    arg = context.args[0].strip()
    payment = await database.get_payment(arg)  # اول به‌عنوانِ charge_id امتحان کن
    if payment is None:
        uid = await _resolve_user_id(arg)       # وگرنه به‌عنوانِ کاربر
        if uid is not None:
            payment = await database.get_latest_refundable_payment(uid)
    if payment is None:
        await update.effective_message.reply_text(tr.REFUND_NOT_FOUND)
        return
    if payment.refunded_at:
        await update.effective_message.reply_text(tr.REFUND_ALREADY)
        return

    try:
        await context.bot.refund_star_payment(payment.user_id, payment.charge_id)
    except Exception as exc:  # noqa: BLE001 - خطای تلگرام به ادمین نشون داده می‌شه
        logger.warning("Refund failed for %s: %s", payment.charge_id, exc)
        await update.effective_message.reply_text(tr.REFUND_FAILED.format(error=exc))
        return

    await database.mark_payment_refunded(payment.charge_id)
    await update.effective_message.reply_text(
        tr.REFUND_OK.format(user=payment.user_id, amount=payment.amount, days=payment.days)
    )
    # به خودِ کاربر هم خبر بده (به زبانِ خودش)
    try:
        target = t.L(await _user_lang(payment.user_id))
        await context.bot.send_message(payment.user_id, target.REFUND_USER_NOTIFY)
    except Exception:  # noqa: BLE001 - اگه کاربر در دسترس نبود مهم نیست
        pass


# ---------- VIP و قیمت‌گذاری ----------
def _fmt_until(dt: str | None) -> str:
    """انقضای VIP رو برای نمایش به فقط بخشِ تاریخ کوتاه می‌کنه."""
    return (dt or "").split(" ")[0] or "—"


async def _resolve_user_id(raw: str) -> int | None:
    """ورودیِ ادمین (آیدیِ عددی یا @یوزرنیم) رو به آیدیِ عددیِ کاربر تبدیل می‌کنه."""
    raw = (raw or "").strip()
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    return await database.find_user_by_username(raw)


# قیمت و مدت هم با دستور (با آرگومان) کار می‌کنن و هم با دکمه‌ی منوی ادمین (پرسش‌وپاسخ).
async def price_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return ConversationHandler.END
    if context.args and re.fullmatch(r"\d+", context.args[0]):
        price = int(context.args[0])
        await database.set_vip_price(price)
        await update.effective_message.reply_text(tr.ADMIN_PRICE_OK.format(price=price))
        return ConversationHandler.END
    await update.effective_message.reply_text(
        tr.ADMIN_PRICE_USAGE, reply_markup=keyboards.cancel_keyboard(lang)
    )
    return PRICE_WAIT


async def price_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    raw = (update.effective_message.text or "").strip()
    if not re.fullmatch(r"\d+", raw):
        await update.effective_message.reply_text(
            tr.ADMIN_PRICE_USAGE, reply_markup=keyboards.cancel_keyboard(lang)
        )
        return PRICE_WAIT
    price = int(raw)
    await database.set_vip_price(price)
    await update.effective_message.reply_text(
        tr.ADMIN_PRICE_OK.format(price=price),
        reply_markup=keyboards.admin_menu_keyboard(lang),
    )
    return ConversationHandler.END


async def duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return ConversationHandler.END
    if context.args and re.fullmatch(r"\d+", context.args[0]):
        days = int(context.args[0])
        await database.set_vip_duration(days)
        await update.effective_message.reply_text(tr.ADMIN_DURATION_OK.format(days=days))
        return ConversationHandler.END
    await update.effective_message.reply_text(
        tr.ADMIN_DURATION_USAGE, reply_markup=keyboards.cancel_keyboard(lang)
    )
    return DURATION_WAIT


async def duration_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    raw = (update.effective_message.text or "").strip()
    if not re.fullmatch(r"\d+", raw):
        await update.effective_message.reply_text(
            tr.ADMIN_DURATION_USAGE, reply_markup=keyboards.cancel_keyboard(lang)
        )
        return DURATION_WAIT
    days = int(raw)
    await database.set_vip_duration(days)
    await update.effective_message.reply_text(
        tr.ADMIN_DURATION_OK.format(days=days),
        reply_markup=keyboards.admin_menu_keyboard(lang),
    )
    return ConversationHandler.END


async def vip_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    default_days = await database.get_vip_duration()
    if not context.args:
        await update.effective_message.reply_text(
            tr.ADMIN_VIPADD_USAGE.format(days=default_days)
        )
        return
    uid = await _resolve_user_id(context.args[0])
    if uid is None:
        await update.effective_message.reply_text(tr.ADMIN_USER_NOT_FOUND)
        return
    days = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else default_days
    until = await database.grant_vip(uid, days)
    await update.effective_message.reply_text(
        tr.ADMIN_VIPADD_OK.format(user=uid, until=_fmt_until(until))
    )
    # به خودِ کاربر هم خبر بده (به زبانِ خودش، اگه ربات رو استارت کرده باشه)
    try:
        target = t.L(await _user_lang(uid))
        await context.bot.send_message(
            uid,
            target.VIP_GRANTED_NOTIFY.format(
                until=_fmt_until(until), limit=config.VIP_DAILY_LIMIT
            ),
        )
    except Exception:  # noqa: BLE001 - اگه کاربر ربات رو استارت نکرده باشه مهم نیست
        pass


async def vip_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    if not context.args:
        await update.effective_message.reply_text(tr.ADMIN_VIPREMOVE_USAGE)
        return
    uid = await _resolve_user_id(context.args[0])
    if uid is None:
        await update.effective_message.reply_text(tr.ADMIN_USER_NOT_FOUND)
        return
    removed = await database.revoke_vip(uid)
    if not removed:
        await update.effective_message.reply_text(tr.ADMIN_VIPREMOVE_NOT_VIP)
        return
    await update.effective_message.reply_text(tr.ADMIN_VIPREMOVE_OK.format(user=uid))
    try:
        target = t.L(await _user_lang(uid))
        await context.bot.send_message(uid, target.VIP_REVOKED_NOTIFY)
    except Exception:  # noqa: BLE001
        pass


async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not _is_admin(update):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return
    total = await database.count_users()
    if total == 0:
        await update.effective_message.reply_text(tr.ADMIN_USERS_EMPTY)
        return
    vip = await database.count_vip()
    rows = await database.list_users(limit=50)
    lines = [tr.ADMIN_USERS_HEADER.format(total=total, vip=vip)]
    for u in rows:
        tag = "💎" if u.is_vip else "🆓"
        name = (u.first_name or "—").strip()
        handle = f" @{u.username}" if u.username else ""
        line = f"{tag} {name}{handle} (id: {u.user_id})"
        if u.is_vip and u.vip_until:
            line += tr.ADMIN_USERS_VIP_UNTIL.format(until=_fmt_until(u.vip_until))
        lines.append(line)
    if total > len(rows):
        lines.append(tr.ADMIN_USERS_MORE.format(n=total - len(rows), shown=len(rows)))
    await update.effective_message.reply_text("\n".join(lines))


def _btn_filter(btn: dict):
    """فیلترِ تطبیقِ یک دکمه‌ی کیبوردِ ساجست (هر دو زبان) در چتِ خصوصی."""
    return filters.ChatType.PRIVATE & filters.Regex(keyboards.btn_regex(btn))


def build_admin_handlers() -> list:
    """همه هندلرهای ادمین رو برای ثبت در اپلیکیشن برمی‌گردونه."""
    cancel_re = filters.Regex(keyboards.btn_regex(keyboards.BTN_CANCEL))
    # ورودیِ متنیِ مرحله‌ها: هر متنی به‌جز دستور و دکمه‌ی لغو (لغو باید به fallback برسه)
    step_text = filters.TEXT & ~filters.COMMAND & ~cancel_re

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("addchannel", add_start),
            CommandHandler("removechannel", remove_start),
            CommandHandler("setprice", price_start),
            CommandHandler("setduration", duration_start),
            MessageHandler(_btn_filter(keyboards.BTN_ADD_CHANNEL), add_start),
            MessageHandler(_btn_filter(keyboards.BTN_REMOVE_CHANNEL), remove_start),
            MessageHandler(_btn_filter(keyboards.BTN_SET_PRICE), price_start),
            MessageHandler(_btn_filter(keyboards.BTN_SET_DURATION), duration_start),
        ],
        states={
            ADD_TITLE: [MessageHandler(step_text, add_title_receive)],
            ADD_WAIT: [MessageHandler(step_text, add_receive)],
            ADD_DAYS: [MessageHandler(step_text, add_days_receive)],
            REMOVE_WAIT: [MessageHandler(step_text, remove_receive)],
            PRICE_WAIT: [MessageHandler(step_text, price_receive)],
            DURATION_WAIT: [MessageHandler(step_text, duration_receive)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(cancel_re, cancel),
        ],
        allow_reentry=True,
    )
    return [
        conv,
        CommandHandler("admin", admin_panel),
        CommandHandler("channels", channels_list),
        CommandHandler("stats", stats),
        CommandHandler("backup", backup_command),
        CommandHandler("health", health_command),
        CommandHandler("refund", refund_command),
        CommandHandler("vipadd", vip_add),
        CommandHandler("vipremove", vip_remove),
        CommandHandler("users", users_list),
        # دکمه‌های منوی ادمین که خودشون مرحله‌ای نیستن
        MessageHandler(_btn_filter(keyboards.BTN_ADMIN), admin_panel),
        MessageHandler(_btn_filter(keyboards.BTN_CHANNELS), channels_list),
        MessageHandler(_btn_filter(keyboards.BTN_STATS), stats),
        MessageHandler(_btn_filter(keyboards.BTN_USERS), users_list),
        MessageHandler(_btn_filter(keyboards.BTN_BACK), back_to_main),
    ]
