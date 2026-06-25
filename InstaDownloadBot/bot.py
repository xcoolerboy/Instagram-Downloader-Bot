"""ساخت اپلیکیشن تلگرام، ثبت هندلرها و اجرای ربات."""
from __future__ import annotations

import asyncio
import logging
from datetime import time as dtime

from telegram import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from InstaDownloadBot import config, database, jobs
from InstaDownloadBot.handlers import (
    admin,
    broadcast,
    download,
    sources,
    start,
    support,
    vip,
)
from InstaDownloadBot.keyboards import (
    AUDIO_PREFIX,
    BTN_HELP,
    BTN_LANG,
    BTN_SOURCES,
    BTN_TERMS,
    BTN_VIP,
    BUY_VIP,
    CHECK_JOIN,
    COMPRESS_PREFIX,
    NOOP,
    SETLANG_PREFIX,
    SRC_DEL_PREFIX,
    btn_regex,
)

logger = logging.getLogger(__name__)


# منوی دستورها دو زبانه‌ست: نسخه‌ی فارسی پیش‌فرضه و نسخه‌ی انگلیسی با language_code="en"
# برای کلاینت‌هایی که زبانشون انگلیسیه نشون داده می‌شه.
_PUBLIC_COMMANDS_FA = [
    BotCommand("start", "شروع کار با ربات"),
    BotCommand("help", "راهنمای استفاده"),
    BotCommand("vip", "اشتراک ویژه و دانلود بیشتر"),
    BotCommand("terms", "شرایط استفاده و سلب مسئولیت"),
    BotCommand("support", "ارتباط با پشتیبانی"),
]
_PUBLIC_COMMANDS_EN = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "How to use"),
    BotCommand("vip", "Premium & higher limits"),
    BotCommand("terms", "Terms & disclaimer"),
    BotCommand("support", "Contact support"),
]
_ADMIN_COMMANDS_FA = _PUBLIC_COMMANDS_FA + [
    BotCommand("admin", "پنل مدیریت"),
    BotCommand("addchannel", "افزودن کانال اجباری"),
    BotCommand("removechannel", "حذف کانال اجباری"),
    BotCommand("channels", "لیست کانال‌های اجباری"),
    BotCommand("users", "لیست کاربران و وضعیت VIP"),
    BotCommand("setprice", "تغییر قیمت اشتراک (Stars)"),
    BotCommand("setduration", "تغییر مدت اشتراک (روز)"),
    BotCommand("vipadd", "دادن VIP به کاربر"),
    BotCommand("vipremove", "گرفتن VIP از کاربر"),
    BotCommand("broadcast", "ارسال پیام همگانی"),
    BotCommand("undobroadcast", "حذف آخرین پیام همگانی"),
    BotCommand("addcookie", "افزودن کوکی (بدون ری‌استارت)"),
    BotCommand("addproxy", "افزودن پروکسی رزیدنشال"),
    BotCommand("sources", "مدیریت کوکی/پروکسی زنده"),
    BotCommand("stats", "آمار ربات"),
    BotCommand("health", "سلامت و وضعیتِ ربات"),
    BotCommand("backup", "تهیه‌ی نسخه‌ی پشتیبانِ دیتابیس"),
    BotCommand("refund", "بازپرداختِ اشتراک (Stars)"),
]
_ADMIN_COMMANDS_EN = _PUBLIC_COMMANDS_EN + [
    BotCommand("admin", "Admin panel"),
    BotCommand("addchannel", "Add required channel"),
    BotCommand("removechannel", "Remove required channel"),
    BotCommand("channels", "List required channels"),
    BotCommand("users", "List users & VIP status"),
    BotCommand("setprice", "Set subscription price (Stars)"),
    BotCommand("setduration", "Set subscription duration (days)"),
    BotCommand("vipadd", "Grant VIP to a user"),
    BotCommand("vipremove", "Revoke VIP from a user"),
    BotCommand("broadcast", "Send a broadcast message"),
    BotCommand("undobroadcast", "Delete the last broadcast"),
    BotCommand("addcookie", "Add a cookie (no restart)"),
    BotCommand("addproxy", "Add a residential proxy"),
    BotCommand("sources", "Manage live cookies/proxies"),
    BotCommand("stats", "Bot statistics"),
    BotCommand("health", "Bot health & status"),
    BotCommand("backup", "Back up the database"),
    BotCommand("refund", "Refund a subscription (Stars)"),
]


async def _post_init(app) -> None:
    await database.init_db()

    # منوی «/» برای همه: نسخه‌ی فارسی (پیش‌فرض) + نسخه‌ی انگلیسی برای کلاینت‌های انگلیسی
    await app.bot.set_my_commands(_PUBLIC_COMMANDS_FA, scope=BotCommandScopeDefault())
    await app.bot.set_my_commands(
        _PUBLIC_COMMANDS_EN, scope=BotCommandScopeDefault(), language_code="en"
    )

    # منوی «/» مخصوص هر ادمین: دستورهای مدیریتی هم اضافه می‌شن (فارسی + انگلیسی)
    for admin_id in config.ADMIN_IDS:
        try:
            await app.bot.set_my_commands(
                _ADMIN_COMMANDS_FA, scope=BotCommandScopeChat(chat_id=admin_id)
            )
            await app.bot.set_my_commands(
                _ADMIN_COMMANDS_EN,
                scope=BotCommandScopeChat(chat_id=admin_id),
                language_code="en",
            )
        except Exception as exc:  # noqa: BLE001 - شکست برای یک ادمین نباید استارت رو خراب کنه
            logger.warning("Failed to set admin commands for %s: %s", admin_id, exc)

    me = await app.bot.get_me()
    logger.info("Bot @%s is ready.", me.username)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Error while handling update", exc_info=context.error)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[InstaDownloader] %(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # httpx لاگ هر درخواست رو با توکن داخل URL چاپ می‌کنه؛ ساکتش می‌کنیم
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config.validate()

    app = ApplicationBuilder().token(config.BOT_TOKEN).post_init(_post_init).build()

    # دستورهای عمومی
    app.add_handler(CommandHandler("start", start.start_command))
    app.add_handler(CommandHandler("help", start.help_command))
    app.add_handler(CommandHandler("terms", start.terms_command))

    # انتخابِ زبان از پیکرِ این‌لاین (بارِ اول و هر تغییرِ بعدی)
    app.add_handler(
        CallbackQueryHandler(start.setlang_callback, pattern=f"^{SETLANG_PREFIX}:")
    )

    # دکمه‌های عضویت
    app.add_handler(CallbackQueryHandler(start.check_join_callback, pattern=f"^{CHECK_JOIN}$"))
    app.add_handler(CallbackQueryHandler(start.noop_callback, pattern=f"^{NOOP}$"))

    # دکمه‌ی «نسخه‌ی کم‌حجم» زیرِ هر ریلز
    app.add_handler(
        CallbackQueryHandler(download.handle_compress, pattern=f"^{COMPRESS_PREFIX}:")
    )

    # دکمه‌ی «دریافت موزیک / صدا» زیرِ هر ریلز
    app.add_handler(
        CallbackQueryHandler(download.handle_audio, pattern=f"^{AUDIO_PREFIX}:")
    )

    # هندلرهای ادمین (قبل از هندلر لینک ثبت می‌شن)
    for handler in admin.build_admin_handlers():
        app.add_handler(handler)

    # پیامِ همگانی (فقط ادمین) — /broadcast و /undobroadcast
    app.add_handler(CommandHandler("broadcast", broadcast.broadcast_command))
    app.add_handler(CommandHandler("undobroadcast", broadcast.undobroadcast_command))

    # مدیریتِ زنده‌ی منابعِ دانلود (کوکی/پروکسی) — فقط ادمین، بدونِ ری‌استارتِ ربات
    app.add_handler(CommandHandler("addcookie", sources.addcookie_command))
    app.add_handler(CommandHandler("addproxy", sources.addproxy_command))
    app.add_handler(CommandHandler("sources", sources.sources_command))
    app.add_handler(
        CallbackQueryHandler(sources.delete_callback, pattern=f"^{SRC_DEL_PREFIX}:")
    )

    # سیستمِ پشتیبانی: تیکت‌ها + ویزاردِ تنظیمِ گروه + رله‌ی پاسخِ ادمین در گروه
    # (قبل از دکمه‌های ساده و هندلر لینک ثبت می‌شن تا گفتگوهای فعال ورودی رو بگیرن)
    for handler in support.build_support_handlers():
        app.add_handler(handler)

    # اشتراکِ VIP و پرداخت با Telegram Stars
    app.add_handler(CommandHandler("vip", vip.vip_command))
    app.add_handler(CallbackQueryHandler(vip.buy_vip_callback, pattern=f"^{BUY_VIP}$"))
    app.add_handler(PreCheckoutQueryHandler(vip.precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, vip.successful_payment))

    # دکمه‌های کیبوردِ اصلی (راهنما / اشتراک ویژه / شرایط / زبان) — معادلِ دستورهاشون،
    # هر دو زبان را با btn_regex می‌گیرن.
    _private = filters.ChatType.PRIVATE
    app.add_handler(
        MessageHandler(_private & filters.Regex(btn_regex(BTN_HELP)), start.help_command)
    )
    app.add_handler(
        MessageHandler(_private & filters.Regex(btn_regex(BTN_VIP)), vip.vip_command)
    )
    app.add_handler(
        MessageHandler(_private & filters.Regex(btn_regex(BTN_TERMS)), start.terms_command)
    )
    # دکمه‌ی همیشه‌حاضرِ «🌐 زبان» → باز کردنِ دوباره‌ی پیکرِ انتخابِ زبان
    app.add_handler(
        MessageHandler(_private & filters.Regex(btn_regex(BTN_LANG)), start.change_language)
    )
    # دکمه‌ی منوی ادمینِ «🔑 کوکی/پروکسی» → نمای مدیریتِ منابعِ زنده
    app.add_handler(
        MessageHandler(_private & filters.Regex(btn_regex(BTN_SOURCES)), sources.sources_command)
    )

    # دریافت لینک‌های اینستاگرام (فقط چتِ خصوصی — تا با پیام‌های گروهِ پشتیبانی تداخل نکنه)
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            download.handle_link,
        )
    )

    app.add_error_handler(_on_error)

    # کارهای دوره‌ای فقط وقتی ثبت می‌شن که اکسترای [job-queue] نصب باشه؛ وگرنه ربات بدونِ
    # این‌ها سالم بالا میاد (نصبِ ناقص نباید استارت رو بخوابونه).
    if app.job_queue is not None:
        # پاک‌سازیِ کشِ منقضی + پوشه‌های موقتِ یتیم — هر ۶ ساعت، ۵ دقیقه بعد از بالا اومدن.
        app.job_queue.run_repeating(jobs.cleanup_job, interval=6 * 3600, first=300)
        # یادآوریِ انقضای VIP — روزانه ساعتِ ۹ صبحِ UTC.
        app.job_queue.run_daily(jobs.vip_reminder_job, time=dtime(hour=9, minute=0))
        logger.info("Periodic jobs scheduled (cleanup + VIP reminder).")
    else:
        logger.warning(
            "JobQueue unavailable — install python-telegram-bot[job-queue] to enable "
            "periodic cleanup and VIP reminders."
        )

    # روی پایتون ۳.۱۲+/۳.۱۴ متد run_polling داخلاً asyncio.get_event_loop() صدا می‌زنه
    # که دیگه خودکار loop نمی‌سازه. اینجا دستی یک event loop می‌سازیم.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    logger.info("Starting polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
