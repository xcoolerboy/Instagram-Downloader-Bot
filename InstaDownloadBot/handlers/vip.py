"""اشتراکِ VIP: نمایشِ اطلاعات، ساختِ فاکتورِ Telegram Stars، و فعال‌سازی پس از پرداخت.

پرداخت با Stars (واحدِ XTR) هیچ provider_token‌ای لازم نداره — کافیه currency="XTR"
و provider_token خالی باشه. جریان کار:
  /vip → نمایشِ مزایا + دکمه‌ی پرداخت → فاکتور → PreCheckout (تأیید) → SuccessfulPayment (فعال‌سازی)
"""
from __future__ import annotations

import logging

from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes

from InstaDownloadBot import config, database, keyboards
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import _user_lang

logger = logging.getLogger(__name__)

# نشانه‌ی فاکتورِ ما؛ تعدادِ روزِ خریداری‌شده هم داخلش می‌مونه تا اگه ادمین بینِ
# ساختِ فاکتور و پرداخت مدت رو عوض کرد، همون چیزی که کاربر خریده اعمال شه.
_PAYLOAD_PREFIX = "vip_sub"


def fmt_until(dt: str | None) -> str:
    """تاریخِ انقضای ذخیره‌شده (UTC) رو برای نمایش به فقط بخشِ تاریخ کوتاه می‌کنه."""
    if not dt:
        return "—"
    return dt.split(" ")[0]


async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await database.upsert_user(user.id, user.first_name, user.username)
    lang = await _user_lang(user.id)
    tr = t.L(lang)

    quota = await database.get_quota(
        user.id, config.FREE_DAILY_LIMIT, config.VIP_DAILY_LIMIT
    )
    if quota.is_vip:
        await update.effective_message.reply_text(
            tr.VIP_ALREADY.format(
                until=fmt_until(quota.vip_until), used=quota.used, limit=quota.limit
            )
        )
        return

    price = await database.get_vip_price()
    days = await database.get_vip_duration()
    await update.effective_message.reply_text(
        tr.VIP_INFO.format(
            vip_limit=config.VIP_DAILY_LIMIT,
            free_limit=config.FREE_DAILY_LIMIT,
            price=price,
            days=days,
        ),
        reply_markup=keyboards.buy_vip_keyboard(price, lang),
    )


async def buy_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی «پرداخت با Stars» → فاکتور رو می‌فرسته."""
    query = update.callback_query
    lang = await _user_lang(query.from_user.id)
    await query.answer()
    await _send_invoice(context, query.message.chat_id, lang)


async def _send_invoice(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, lang: str = "fa"
) -> None:
    tr = t.L(lang)
    price = await database.get_vip_price()
    days = await database.get_vip_duration()
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=tr.VIP_INVOICE_TITLE,
        description=tr.VIP_INVOICE_DESC.format(vip_limit=config.VIP_DAILY_LIMIT, days=days),
        payload=f"{_PAYLOAD_PREFIX}:{days}",
        provider_token="",            # برای Stars باید خالی باشه
        currency="XTR",               # واحدِ Telegram Stars
        prices=[LabeledPrice(tr.VIP_INVOICE_TITLE, price)],
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """آخرین تأیید قبل از کسرِ Stars — فقط فاکتورهای خودمون رو OK می‌کنیم."""
    query = update.pre_checkout_query
    if (query.invoice_payload or "").startswith(_PAYLOAD_PREFIX):
        await query.answer(ok=True)
    else:
        tr = t.L(await _user_lang(query.from_user.id))
        await query.answer(ok=False, error_message=tr.VIP_INVALID_INVOICE)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بعد از پرداختِ موفق، اشتراکِ VIP رو فعال/تمدید می‌کنه."""
    user = update.effective_user
    tr = t.L(await _user_lang(user.id))
    payment = update.effective_message.successful_payment
    try:
        days = int((payment.invoice_payload or "").split(":", 1)[1])
    except (IndexError, ValueError):
        days = await database.get_vip_duration()

    until = await database.grant_vip(user.id, days)
    # charge_id رو ذخیره می‌کنیم تا ادمین بتونه بعداً با /refund بازپرداخت کنه.
    await database.record_payment(
        getattr(payment, "telegram_payment_charge_id", "") or "",
        user.id,
        getattr(payment, "total_amount", 0) or 0,
        days,
    )
    await update.effective_message.reply_text(
        tr.VIP_PAYMENT_OK.format(until=fmt_until(until), limit=config.VIP_DAILY_LIMIT)
    )
    logger.info(
        "VIP activated via Stars for user %s (%s days, %s XTR)",
        user.id,
        days,
        getattr(payment, "total_amount", "?"),
    )
