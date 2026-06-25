"""پیامِ همگانی (فقط ادمین): /broadcast و /undobroadcast.

  • /broadcast <متن>            → متن رو به همه‌ی کاربرها می‌فرسته.
  • ریپلای روی هر پیام + /broadcast → همون پیام (متن/عکس/ویدیو/…) رو عیناً همگانی می‌کنه
    (با copy_message، بدونِ برچسبِ «فوروارد شده»).
  • /undobroadcast              → پیام‌های آخرین broadcast رو از چتِ کاربرها پاک می‌کنه
    (تلگرام تا ۴۸ ساعت اجازه‌ی delete_message می‌ده).

ارسال در پس‌زمینه انجام می‌شه (application.create_task) تا ربات حین broadcastِ طولانی
بلاک نشه؛ بینِ هر ارسال کمی مکث می‌کنیم و RetryAfterِ تلگرام رو محترم می‌شماریم.
"""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import ContextTypes

from InstaDownloadBot import config, database
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import _user_lang

logger = logging.getLogger(__name__)

# مکثِ کوتاه بینِ هر ارسال تا به محدودیتِ نرخِ تلگرام نخوریم (~۲۰ پیام در ثانیه سقفِ امن).
_SEND_DELAY = 0.05


async def _send_one(bot, uid: int, reply, payload_text: str | None) -> int:
    """پیامِ همگانی رو به یک کاربر می‌فرسته و message_idِ نتیجه رو برمی‌گردونه.

    اگه ``reply`` داده شده باشه پیامِ ریپلای‌شده رو عیناً کپی می‌کنه، وگرنه متن رو می‌فرسته.
    """
    if reply is not None:
        sent = await bot.copy_message(
            chat_id=uid,
            from_chat_id=reply.chat_id,
            message_id=reply.message_id,
        )
    else:
        sent = await bot.send_message(chat_id=uid, text=payload_text)
    return sent.message_id


async def _run_broadcast(
    context: ContextTypes.DEFAULT_TYPE,
    user_ids: list[int],
    reply,
    payload_text: str | None,
    admin_chat_id: int,
    lang: str,
) -> None:
    """تسکِ پس‌زمینه‌ی ارسالِ همگانی؛ message_idها رو برای undo ذخیره می‌کنه."""
    tr = t.L(lang)
    bot = context.bot
    await database.clear_last_broadcast()
    sent = failed = 0
    for uid in user_ids:
        # یک‌بار تلاش؛ اگه RetryAfter خوردیم یک‌بار دیگه (بعد از مکثِ خواسته‌شده) امتحان می‌کنیم.
        for attempt in range(2):
            try:
                mid = await _send_one(bot, uid, reply, payload_text)
                await database.add_broadcast_record(uid, mid)
                sent += 1
                break
            except RetryAfter as exc:
                if attempt == 0:
                    await asyncio.sleep(float(getattr(exc, "retry_after", 1)) + 0.5)
                    continue
                failed += 1
            except Forbidden:
                # کاربر ربات رو بلاک کرده یا حسابش پاک شده → غیرفعالش می‌کنیم تا
                # broadcastهای بعدی سراغش نرن (با تعاملِ بعدیِ خودش دوباره فعال می‌شه).
                failed += 1
                await database.deactivate_user(uid)
            except BadRequest:
                # مثلِ «chat not found» — چتِ مرده؛ طبیعیه، فقط می‌شماریم.
                failed += 1
            except TelegramError:
                failed += 1
            break
        await asyncio.sleep(_SEND_DELAY)

    logger.info("Broadcast finished: sent=%s failed=%s", sent, failed)
    try:
        await bot.send_message(
            admin_chat_id, tr.BROADCAST_DONE.format(sent=sent, failed=failed)
        )
    except TelegramError:
        pass


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/broadcast — ارسالِ متن یا پیامِ ریپلای‌شده به همه‌ی کاربرها (فقط ادمین)."""
    user = update.effective_user
    lang = await _user_lang(user.id)
    tr = t.L(lang)
    if not config.is_admin(user.id):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return

    msg = update.effective_message
    reply = msg.reply_to_message
    parts = (msg.text or "").split(maxsplit=1)
    payload_text = parts[1] if len(parts) > 1 else None

    # نه ریپلایی هست نه متنی → راهنما رو نشون بده.
    if reply is None and not payload_text:
        await msg.reply_text(tr.BROADCAST_USAGE)
        return

    user_ids = await database.get_all_user_ids()
    await msg.reply_text(tr.BROADCAST_STARTED.format(count=len(user_ids)))
    context.application.create_task(
        _run_broadcast(context, user_ids, reply, payload_text, msg.chat_id, lang)
    )


async def _run_undo(
    context: ContextTypes.DEFAULT_TYPE,
    records: list[tuple[int, int]],
    admin_chat_id: int,
    lang: str,
) -> None:
    """تسکِ پس‌زمینه‌ی حذفِ پیام‌های آخرین broadcast."""
    tr = t.L(lang)
    bot = context.bot
    deleted = failed = 0
    for uid, mid in records:
        try:
            await bot.delete_message(chat_id=uid, message_id=mid)
            deleted += 1
        except RetryAfter as exc:
            await asyncio.sleep(float(getattr(exc, "retry_after", 1)) + 0.5)
            try:
                await bot.delete_message(chat_id=uid, message_id=mid)
                deleted += 1
            except TelegramError:
                failed += 1
        except TelegramError:
            # پیام قبلاً پاک شده، خیلی قدیمیه (سقفِ ۴۸ ساعت) یا دسترسی نیست.
            failed += 1
        await asyncio.sleep(_SEND_DELAY)

    await database.clear_last_broadcast()
    logger.info("Undo broadcast finished: deleted=%s failed=%s", deleted, failed)
    try:
        await bot.send_message(
            admin_chat_id, tr.BROADCAST_UNDO_DONE.format(deleted=deleted, failed=failed)
        )
    except TelegramError:
        pass


async def undobroadcast_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/undobroadcast — پاک کردنِ پیام‌های آخرین broadcast از چتِ کاربرها (فقط ادمین)."""
    user = update.effective_user
    lang = await _user_lang(user.id)
    tr = t.L(lang)
    if not config.is_admin(user.id):
        await update.effective_message.reply_text(tr.ADMIN_ONLY)
        return

    records = await database.get_last_broadcast()
    if not records:
        await update.effective_message.reply_text(tr.BROADCAST_UNDO_NONE)
        return

    await update.effective_message.reply_text(
        tr.BROADCAST_UNDO_STARTED.format(count=len(records))
    )
    context.application.create_task(
        _run_undo(context, records, update.effective_message.chat_id, lang)
    )
