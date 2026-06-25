"""دستور /start، /help، /terms، انتخابِ زبان و دروازه عضویت اجباری."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from InstaDownloadBot import config, database, keyboards
from InstaDownloadBot import localization as t
from InstaDownloadBot.services.membership import channels_not_joined


async def _user_lang(user_id: int) -> str:
    """زبانِ کاربر رو می‌خونه و نرمالایز می‌کنه (اگه تنظیم نشده باشه پیش‌فرض = فارسی)."""
    return t.normalize_lang(await database.get_user_lang(user_id))


async def gate_passed(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None
) -> bool:
    """اگر کاربر عضو همه کانال‌های اجباری باشه True، وگرنه پیام عضویت رو می‌فرسته.

    کاربرانِ VIP و ادمین‌ها از عضویتِ اجباری معاف‌اند.
    """
    user = update.effective_user
    if lang is None:
        lang = await _user_lang(user.id)
    if config.is_admin(user.id) or await database.is_vip(user.id):
        return True
    pending = await channels_not_joined(context.bot, user.id)
    if not pending:
        return True
    tr = t.L(lang)
    await update.effective_message.reply_text(
        tr.JOIN_REQUIRED, reply_markup=keyboards.join_keyboard(pending, lang)
    )
    return False


async def _send_welcome(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str
) -> None:
    """پیامِ خوش‌آمد + کیبوردِ اصلی (و سلبِ مسئولیتِ بارِ اول) رو به زبانِ انتخابی می‌فرسته."""
    user = update.effective_user
    if not await gate_passed(update, context, lang):
        return
    tr = t.L(lang)
    await update.effective_message.reply_text(
        tr.START.format(name=user.first_name or ""),
        reply_markup=keyboards.main_keyboard(config.is_admin(user.id), lang),
    )
    # سلبِ مسئولیت فقط بارِ اول برای هر کاربر نشون داده می‌شه
    if await database.should_show_terms(user.id):
        await update.effective_message.reply_text(tr.TERMS)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await database.upsert_user(user.id, user.first_name, user.username)
    lang = await database.get_user_lang(user.id)
    # بارِ اول (زبان هنوز انتخاب نشده): اول زبان رو می‌پرسیم و بقیه رو می‌سپریم به کال‌بک
    if lang is None:
        await update.effective_message.reply_text(
            t.CHOOSE_LANG_PROMPT, reply_markup=keyboards.language_inline_keyboard()
        )
        return
    await _send_welcome(update, context, lang)


async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی همیشه‌حاضرِ «🌐 زبان»: پیکرِ انتخابِ زبان رو دوباره باز می‌کنه."""
    await update.effective_message.reply_text(
        t.CHOOSE_LANG_PROMPT, reply_markup=keyboards.language_inline_keyboard()
    )


async def setlang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """انتخابِ زبان از پیکرِ این‌لاین (callback_data: ``setlang:fa`` / ``setlang:en``)."""
    query = update.callback_query
    user = query.from_user
    _, _, raw = query.data.partition(":")
    lang = t.normalize_lang(raw)
    # آیا کاربر از قبل زبان داشت؟ (تشخیصِ بارِ اول از تغییرِ بعدی)
    had_lang = await database.get_user_lang(user.id) is not None
    await database.upsert_user(user.id, user.first_name, user.username)
    await database.set_user_lang(user.id, lang)
    tr = t.L(lang)
    await query.answer()
    try:
        await query.edit_message_text(tr.LANG_SET)
    except Exception:  # noqa: BLE001 - اگه متن عوض نشده باشه تلگرام خطا می‌ده
        pass
    if not had_lang:
        # بارِ اول: حالا که زبان مشخص شد، خوش‌آمد + دروازه‌ی عضویت رو نشون بده
        await _send_welcome(update, context, lang)
    else:
        # تغییرِ زبان در میانه‌ی کار: فقط منوی اصلی رو با کیبوردِ زبانِ جدید تازه کن
        await query.message.reply_text(
            tr.MENU_MAIN,
            reply_markup=keyboards.main_keyboard(config.is_admin(user.id), lang),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tr = t.L(await _user_lang(update.effective_user.id))
    await update.effective_message.reply_text(tr.HELP)


async def terms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tr = t.L(await _user_lang(update.effective_user.id))
    await update.effective_message.reply_text(tr.TERMS)


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = await _user_lang(query.from_user.id)
    tr = t.L(lang)
    pending = await channels_not_joined(context.bot, query.from_user.id)
    if pending:
        await query.answer(tr.JOIN_NOT_YET, show_alert=True)
        try:
            await query.edit_message_reply_markup(keyboards.join_keyboard(pending, lang))
        except Exception:  # noqa: BLE001 - اگر مارک‌آپ عوض نشده باشه تلگرام خطا می‌ده
            pass
        return
    await query.answer()
    await query.edit_message_text(tr.JOIN_DONE)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
