"""کارهای دوره‌ای (JobQueue): پاک‌سازیِ کش/فایل‌های موقت + یادآوریِ انقضای VIP.

این کارها وقتی ثبت می‌شن که JobQueue در دسترس باشه (یعنی ``python-telegram-bot[job-queue]``
نصب شده باشه). اگه اکسترای job-queue نصب نشده باشه، ``bot.py`` از خیرِ زمان‌بندی می‌گذره و
بقیه‌ی ربات سالم کار می‌کنه — این فایل هیچ وابستگیِ سختی به APScheduler نداره.
"""
from __future__ import annotations

import logging
import shutil
import time

from telegram.ext import ContextTypes

from InstaDownloadBot import config, database, keyboards
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import _user_lang

logger = logging.getLogger(__name__)

# پوشه‌ی موقتِ قدیمی‌تر از این (ثانیه) یعنی از یک دانلودِ نیمه‌کاره/کرش‌کرده جا مونده.
# دانلودهای عادی چند ثانیه/دقیقه‌ان، پس ۱ ساعت کاملاً امنه و چیزی که در حالِ کاره پاک نمی‌شه.
_ORPHAN_AGE_SECONDS = 3600
# چند روز مونده به انقضای VIP یادآوریِ تمدید بفرستیم.
_VIP_REMIND_WITHIN_DAYS = 3


async def cleanup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """کشِ منقضی رو پاک می‌کنه و پوشه‌های موقتِ یتیم (از کرشِ قبلی) رو حذف می‌کنه."""
    try:
        purged = await database.purge_expired_cache()
        if purged:
            logger.info("Cleanup: purged %s expired cache row(s).", purged)
    except Exception as exc:  # noqa: BLE001 - کارِ دوره‌ای نباید با خطا بمیره
        logger.warning("Cleanup: purging cache failed: %s", exc)

    try:
        gone = await database.purge_expired_channels()
        if gone:
            logger.info("Cleanup: removed %s expired required-channel(s).", gone)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cleanup: purging expired channels failed: %s", exc)

    removed = 0
    cutoff = time.time() - _ORPHAN_AGE_SECONDS
    try:
        base = config.DOWNLOAD_DIR
        if base.exists():
            for child in base.iterdir():
                if not child.is_dir():
                    continue
                try:
                    if child.stat().st_mtime < cutoff:
                        shutil.rmtree(child, ignore_errors=True)
                        removed += 1
                except OSError:
                    continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cleanup: sweeping temp dirs failed: %s", exc)
    if removed:
        logger.info("Cleanup: removed %s orphaned temp dir(s).", removed)


async def vip_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """به VIPهایی که انقضاشون نزدیکه (و هنوز یادآوری نگرفتن) پیامِ تمدید می‌فرسته.

    هر دوره فقط یک‌بار (به‌خاطرِ شرطِ ``vip_reminded_at IS NULL`` در دیتابیس)؛ بعد از
    تمدیدِ VIP اون فیلد دوباره NULL می‌شه تا نزدیکِ انقضای جدید باز هم یادآوری بره.
    """
    try:
        due = await database.get_vips_needing_reminder(_VIP_REMIND_WITHIN_DAYS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("VIP reminder: query failed: %s", exc)
        return
    if not due:
        return

    price = await database.get_vip_price()
    sent = 0
    for uid, vip_until in due:
        lang = await _user_lang(uid)
        tr = t.L(lang)
        until = (vip_until or "").split(" ")[0]
        try:
            await context.bot.send_message(
                uid,
                tr.VIP_EXPIRING_SOON.format(until=until, price=price),
                reply_markup=keyboards.buy_vip_keyboard(price, lang),
            )
            await database.mark_vip_reminded(uid)
            sent += 1
        except Exception as exc:  # noqa: BLE001 - کاربر بلاک کرده یا در دسترس نیست
            logger.info("VIP reminder: couldn't notify %s: %s", uid, exc)
    if sent:
        logger.info("VIP reminder: notified %s user(s).", sent)
