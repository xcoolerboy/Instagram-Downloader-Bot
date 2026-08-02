"""مدیریتِ زنده‌ی منابعِ دانلود (فقط ادمین): کوکی‌های sessionid و پروکسی‌های رزیدنشال.

هدف: ادمین بتونه بدونِ خاموش/روشنِ ربات، کوکی یا پروکسی اضافه/حذف کنه و بلافاصله اعمال بشه.
چون ``services.instagram.download`` هر بار منابع رو تازه از دیتابیس (+ .env) می‌خونه، هر
تغییری اینجا روی دانلودِ بعدی اثر می‌ذاره.

  • /addcookie <sessionid>     → یک یا چند کوکی (جداشده با کاما/فاصله/خطِ جدید) اضافه می‌کنه.
  • /addproxy  <proxy>         → یک یا چند پروکسی اضافه می‌کنه (http/https/socks5).
  • /sources                   → نمای منابع + دکمه‌های حذفِ تک‌تکِ موردهای زنده.

این دستورها فقط در چتِ خصوصی کار می‌کنن تا مقادیرِ حساس توی گروه لو نره.
"""
from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from InstaDownloadBot import config, database, keyboards
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import _user_lang

logger = logging.getLogger(__name__)

# جداکننده‌ی ورودیِ چندتایی: فاصله/کاما/خطِ جدید (هیچ‌کدوم داخلِ یک sessionid یا proxy نمیان)
_SPLIT_RE = re.compile(r"[\s,]+")
# مخفی‌کردنِ رمزِ عبورِ پروکسی ولی نگه‌داشتنِ host:port برای شناسایی
_PROXY_PW_RE = re.compile(r"(://[^:/@]+:)[^@/]+(@)")


def _mask_cookie(sid: str) -> str:
    """کوکی رو برای نمایشِ امن کوتاه/ماسک می‌کنه (مقدارِ کامل هیچ‌وقت نشون داده نمی‌شه)."""
    sid = sid or ""
    if len(sid) <= 10:
        return (sid[:3] + "…") if sid else "—"
    return f"{sid[:6]}…{sid[-4:]}"


def _mask_proxy(proxy: str) -> str:
    """رمزِ عبورِ پروکسی رو با *** جایگزین می‌کنه؛ host:port برای شناسایی می‌مونه."""
    return _PROXY_PW_RE.sub(r"\1***\2", proxy or "") or "—"


def _admin_private_ok(update: Update, tr) -> str | None:
    """نگهبانِ مشترک: اگه مجاز بود None، وگرنه متنِ خطا برمی‌گردونه."""
    user = update.effective_user
    if not user or not config.is_admin(user.id):
        return tr.ADMIN_ONLY
    chat = update.effective_chat
    if chat is not None and chat.type != "private":
        return tr.SOURCE_PRIVATE_ONLY
    return None


async def _render_sources(lang: str):
    """متنِ نمای منابع + کیبوردِ حذف (با لیبل‌های ماسک‌شده) رو می‌سازه."""
    tr = t.L(lang)
    cookies = await database.list_cookies()
    proxies = await database.list_proxies()
    text = tr.SOURCES_VIEW.format(
        env_c=len(config.INSTAGRAM_SESSIONIDS),
        db_c=len(cookies),
        env_p=1 if config.INSTAGRAM_PROXY else 0,
        db_p=len(proxies),
    )
    kb = keyboards.sources_remove_keyboard(
        [(cid, _mask_cookie(v)) for cid, v in cookies],
        [(pid, _mask_proxy(v)) for pid, v in proxies],
        lang,
    )
    if kb is None:
        text += "\n\n" + tr.SOURCES_EMPTY_HINT
    return text, kb


def _payload(update: Update) -> str:
    """متنِ بعد از خودِ دستور رو برمی‌گردونه (همه‌چیز جز اولین توکن)."""
    parts = (update.effective_message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


async def addcookie_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/addcookie — افزودنِ یک یا چند کوکیِ sessionidِ زنده (فقط ادمین، چتِ خصوصی)."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    err = _admin_private_ok(update, tr)
    if err is not None:
        await update.effective_message.reply_text(err)
        return

    value = _payload(update)
    if not value:
        await update.effective_message.reply_text(tr.ADDCOOKIE_USAGE)
        return

    added = 0
    for tok in (x for x in _SPLIT_RE.split(value) if x):
        if await database.add_cookie(tok):
            added += 1
    total = len(await database.get_all_cookies())
    if added == 0:
        await update.effective_message.reply_text(tr.ADDCOOKIE_DUP)
    else:
        await update.effective_message.reply_text(
            tr.ADDCOOKIE_OK.format(added=added, total=total)
        )


async def addproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/addproxy — افزودنِ یک یا چند پروکسیِ رزیدنشالِ زنده (فقط ادمین، چتِ خصوصی)."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    err = _admin_private_ok(update, tr)
    if err is not None:
        await update.effective_message.reply_text(err)
        return

    value = _payload(update)
    if not value:
        await update.effective_message.reply_text(tr.ADDPROXY_USAGE)
        return

    added = 0
    for tok in (x for x in _SPLIT_RE.split(value) if x):
        if await database.add_proxy(tok):
            added += 1
    total = len(await database.get_all_proxies())
    if added == 0:
        await update.effective_message.reply_text(tr.ADDPROXY_DUP)
    else:
        await update.effective_message.reply_text(
            tr.ADDPROXY_OK.format(added=added, total=total)
        )


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/sources یا دکمه‌ی «🔑 کوکی/پروکسی» — نمای منابع با دکمه‌های حذف (فقط ادمین)."""
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    err = _admin_private_ok(update, tr)
    if err is not None:
        await update.effective_message.reply_text(err)
        return
    text, kb = await _render_sources(lang)
    await update.effective_message.reply_text(text, reply_markup=kb)


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی حذفِ یک منبعِ زنده (srcdel:c:<id> کوکی / srcdel:p:<id> پروکسی)."""
    query = update.callback_query
    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    if not config.is_admin(update.effective_user.id):
        await query.answer(tr.ADMIN_ONLY, show_alert=True)
        return

    try:
        _, kind, raw_id = (query.data or "").split(":")
        item_id = int(raw_id)
    except (ValueError, AttributeError):
        await query.answer()
        return

    if kind == "c":
        ok = await database.remove_cookie(item_id)
    elif kind == "p":
        ok = await database.remove_proxy(item_id)
    else:
        await query.answer()
        return

    await query.answer(tr.SRC_REMOVED if ok else tr.SRC_REMOVE_FAILED)
    text, kb = await _render_sources(lang)
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except Exception:  # noqa: BLE001 - اگه پیام عوض نشده یا قابلِ ویرایش نبود، مهم نیست
        pass


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/login یا /addaccount — ورود با نام کاربری و رمز عبور اینستاگرام و استخراج کوکی (فقط ادمین، چت خصوصی)."""
    import asyncio
    from InstaDownloadBot.services.instagram import login_and_get_sessionid

    lang = await _user_lang(update.effective_user.id)
    tr = t.L(lang)
    err = _admin_private_ok(update, tr)
    if err is not None:
        await update.effective_message.reply_text(err)
        return

    parts = (update.effective_message.text or "").split()
    if len(parts) < 3:
        await update.effective_message.reply_text(tr.LOGIN_USAGE)
        return

    username = parts[1]
    password = parts[2]
    proxy = parts[3] if len(parts) > 3 else ""

    status_msg = await update.effective_message.reply_text(tr.LOGIN_START)

    try:
        sessionid = await asyncio.to_thread(
            login_and_get_sessionid, username, password, proxy
        )
        await database.add_cookie(sessionid)
        total = len(await database.get_all_cookies())
        masked = _mask_cookie(sessionid)
        await status_msg.edit_text(tr.LOGIN_OK.format(cookie=masked, total=total))
    except Exception as exc:
        logger.error("Login command failed for %s: %s", username, exc)
        await status_msg.edit_text(tr.LOGIN_FAIL.format(error=str(exc)))

