"""بررسی عضویت اجباری کاربر در کانال‌ها."""
from __future__ import annotations

import logging

from telegram import Bot
from telegram.error import TelegramError

from InstaDownloadBot import database
from InstaDownloadBot.database import Channel

logger = logging.getLogger(__name__)

# وضعیت‌هایی که یعنی کاربر هنوز عضو نیست
_NOT_MEMBER = {"left", "kicked"}


async def channels_not_joined(bot: Bot, user_id: int) -> list[Channel]:
    """لیست کانال‌هایی که کاربر هنوز عضوشون نشده رو برمی‌گردونه.

    اگر ربات نتونه عضویت یک کانال رو بررسی کنه (مثلاً ادمین نیست) اون کانال
    نادیده گرفته می‌شه تا کاربرها به‌خاطر تنظیم اشتباه قفل نشن.
    """
    channels = await database.get_channels()
    if not channels:
        return []

    pending: list[Channel] = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.chat_id, user_id)
        except TelegramError as exc:
            logger.warning("Membership check failed for channel %s: %s", ch.chat_id, exc)
            continue
        if member.status in _NOT_MEMBER:
            pending.append(ch)
    return pending


async def is_member_everywhere(bot: Bot, user_id: int) -> bool:
    return not await channels_not_joined(bot, user_id)
