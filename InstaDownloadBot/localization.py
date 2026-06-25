"""تمام متن‌های ربات (فارسی + انگلیسی) یک‌جا، تا تغییر و ترجمه‌شون راحت باشه.

طرزِ استفاده در هندلرها:
    from InstaDownloadBot import localization as t
    tr = t.L(lang)                 # lang = "fa" یا "en"
    await msg.reply_text(tr.START.format(name=name))

هر مقدار یا یک ``dict`` دو‌زبانه ``{"fa": ..., "en": ...}`` است یا یک رشته‌ی خنثی
(مثلِ «—») که به هر دو زبان یکی‌ست. دسترسیِ ساده‌ی ``t.NAME`` (بدونِ L) هم کار می‌کنه و
نسخه‌ی زبانِ پیش‌فرض (فارسی) رو برمی‌گردونه — یک تورِ امن برای جاهایی که زبان نخ نشده.
"""
from __future__ import annotations

DEFAULT_LANG = "fa"
SUPPORTED_LANGS = ("fa", "en")


def normalize_lang(lang: str | None) -> str:
    """ورودیِ نامعتبر/None رو به زبانِ پیش‌فرض برمی‌گردونه."""
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


# هر کلید: یا dictِ {"fa":..,"en":..} (دوزبانه) یا یک رشته‌ی خنثی.
_S: dict[str, object] = {
    # ---------------------------------------------------------------- عمومی
    "START": {
        "fa": (
            "سلام {name} 👋\n\n"
            "به ربات دانلود ریلز اینستاگرام خوش اومدی.\n"
            "کافیه لینک ریلز یا پست عمومی اینستاگرام رو برام بفرستی تا ویدیو همراه با کپشن"
            " برات ارسال بشه. ✨\n\n"
            "🔗 فقط لینک رو پیست کن و بفرست."
        ),
        "en": (
            "Hi {name} 👋\n\n"
            "Welcome to the Instagram Reels downloader bot.\n"
            "Just send me a link to a public Instagram reel or post and I'll send you the"
            " video together with its caption. ✨\n\n"
            "🔗 Simply paste the link and send it."
        ),
    },
    "HELP": {
        "fa": (
            "📖 راهنما\n\n"
            "۱) لینک ریلز یا پست عمومی اینستاگرام رو کپی کن.\n"
            "۲) همینجا برام بفرست.\n"
            "۳) چند لحظه صبر کن تا ویدیو و کپشن برات ارسال بشه.\n\n"
            "نمونه لینک‌های پشتیبانی‌شده:\n"
            "• https://www.instagram.com/reel/XXXX/\n"
            "• https://www.instagram.com/p/XXXX/\n"
            "• https://www.instagram.com/tv/XXXX/\n\n"
            "💎 برای اشتراکِ ویژه و دانلودِ بیشتر: /vip\n"
            "📜 برای دیدنِ شرایط استفاده: /terms"
        ),
        "en": (
            "📖 Help\n\n"
            "1) Copy the link to a public Instagram reel or post.\n"
            "2) Send it to me here.\n"
            "3) Wait a moment for the video and caption to arrive.\n\n"
            "Supported link examples:\n"
            "• https://www.instagram.com/reel/XXXX/\n"
            "• https://www.instagram.com/p/XXXX/\n"
            "• https://www.instagram.com/tv/XXXX/\n\n"
            "💎 For premium and more downloads: /vip\n"
            "📜 To read the terms of use: /terms"
        ),
    },
    # ------------------------------------ شرایط استفاده / سلب مسئولیت
    "TERMS": {
        "fa": (
            "📜 شرایط استفاده و سلبِ مسئولیت\n\n"
            "🤖 این ربات فقط یه ابزارِ کمکی برای دانلودِ محتوای عمومیِ اینستاگرامه.\n\n"
            "👤 حقِ همه‌ی ویدیوها و عکس‌ها متعلق به سازنده‌ی اصلی‌شونه و لینکِ منبع همیشه"
            " همراهِ فایل ارسال می‌شه. 🔗\n\n"
            "📌 استفاده فقط برای مصارفِ شخصیه؛ مسئولیتِ هر استفاده‌ی دیگه (انتشارِ مجدد،"
            " استفاده‌ی تجاری و ...) کاملاً با خودِ کاربره.\n\n"
            "🚫 لطفاً به کپی‌رایت و حقِ سازنده‌ها احترام بذار.\n\n"
            "✅ با ادامه‌ی استفاده از ربات، این شرایط رو می‌پذیری. 🙏"
        ),
        "en": (
            "📜 Terms of use & disclaimer\n\n"
            "🤖 This bot is only a helper tool for downloading public Instagram content.\n\n"
            "👤 All videos and photos belong to their original creators, and the source"
            " link is always attached to the file. 🔗\n\n"
            "📌 Use is for personal purposes only; responsibility for any other use"
            " (re-posting, commercial use, etc.) is entirely on the user.\n\n"
            "🚫 Please respect copyright and creators' rights.\n\n"
            "✅ By continuing to use the bot, you accept these terms. 🙏"
        ),
    },
    # ------------------------------------------------- عضویت اجباری
    "JOIN_REQUIRED": {
        "fa": (
            "🔒 برای استفاده از ربات اول باید عضو کانال‌(های) زیر بشی.\n"
            "بعد از عضویت روی «✅ عضو شدم» بزن."
        ),
        "en": (
            "🔒 To use the bot you must first join the channel(s) below.\n"
            "After joining, tap «✅ I joined»."
        ),
    },
    "JOIN_CHECK_BUTTON": {"fa": "✅ عضو شدم", "en": "✅ I joined"},
    "JOIN_NOT_YET": {
        "fa": "❌ هنوز عضو همه کانال‌ها نشدی. بعد از عضویت دوباره روی «✅ عضو شدم» بزن.",
        "en": "❌ You haven't joined all channels yet. After joining, tap «✅ I joined» again.",
    },
    "JOIN_DONE": {
        "fa": "✅ عالی! حالا می‌تونی لینک ریلز رو برام بفرستی.",
        "en": "✅ Great! Now you can send me a reel link.",
    },
    # --------------------------------------------------- پردازش لینک
    "INVALID_LINK": {
        "fa": (
            "🤔 این یه لینک معتبر اینستاگرام نیست.\n"
            "یه لینک ریلز یا پست عمومی مثل https://www.instagram.com/reel/XXXX/ بفرست."
        ),
        "en": (
            "🤔 That's not a valid Instagram link.\n"
            "Send a reel or public post link like https://www.instagram.com/reel/XXXX/"
        ),
    },
    "PROCESSING": {
        "fa": "⏳ در حال دریافت محتوا... چند لحظه صبر کن.",
        "en": "⏳ Fetching the content... please wait a moment.",
    },
    "DOWNLOAD_FAILED": {
        "fa": (
            "😕 نتونستم این محتوا رو دانلود کنم.\n"
            "ممکنه پست خصوصی باشه، حذف شده باشه، یا اینستاگرام موقتاً محدودش کرده باشه.\n"
            "لطفاً لینک رو چک کن یا کمی بعد دوباره امتحان کن."
        ),
        "en": (
            "😕 I couldn't download this content.\n"
            "It may be private, deleted, or temporarily restricted by Instagram.\n"
            "Please check the link or try again a little later."
        ),
    },
    "FILE_TOO_LARGE": {
        "fa": "📦 حجم این ویدیو از حد مجاز تلگرام برای ربات بیشتره و نمی‌تونم ارسالش کنم.",
        "en": "📦 This video exceeds Telegram's size limit for bots, so I can't send it.",
    },
    # ------------------------------------- محدودسازی نرخ / ضدفلود
    "COOLDOWN_WAIT": {
        "fa": "⏳ یه کم آروم‌تر! لطفاً {seconds} ثانیه دیگه دوباره امتحان کن.",
        "en": "⏳ Slow down a bit! Please try again in {seconds} seconds.",
    },
    "TOO_BUSY": {
        "fa": (
            "🚦 ربات الان شلوغه و چند دانلود هم‌زمان در حال انجامه.\n"
            "چند لحظه دیگه دوباره لینک رو بفرست."
        ),
        "en": (
            "🚦 The bot is busy right now with several downloads in progress.\n"
            "Please send the link again in a moment."
        ),
    },
    "NO_CAPTION": "—",
    # تبلیغ پای هر فایل ارسالی؛ {username} با آیدی خودِ ربات پر می‌شه (برندینگ)
    "CAPTION_FOOTER": {
        "fa": "📥 دانلود شده با @{username}",
        "en": "📥 Downloaded with @{username}",
    },
    # اعتباردهی به سازنده‌ی اصلی — پای هر فایل میاد تا معلوم باشه محتوا مالِ کیه.
    "SOURCE_AUTHOR": {
        "fa": '👤 سازنده: <a href="{url}">{author}</a>',
        "en": '👤 Creator: <a href="{url}">{author}</a>',
    },
    "SOURCE_LINK": {
        "fa": '🔗 <a href="{url}">لینکِ اصلی</a>',
        "en": '🔗 <a href="{url}">Original link</a>',
    },
    # ----------------------------- دکمه‌ی نسخه‌ی کم‌حجم (فشرده‌سازی)
    "COMPRESS_BUTTON": {"fa": "🪶 ارسال نسخه کم‌حجم", "en": "🪶 Send lighter version"},
    "COMPRESS_WORKING": {
        "fa": "⏳ دارم نسخه‌ی کم‌حجم رو می‌سازم...",
        "en": "⏳ Building the lighter version...",
    },
    "COMPRESS_FAILED": {
        "fa": "😕 نتونستم نسخه‌ی کم‌حجم بسازم. کمی بعد دوباره امتحان کن.",
        "en": "😕 I couldn't make a lighter version. Try again a little later.",
    },
    "COMPRESS_TOO_LARGE": {
        "fa": (
            "📦 این ویدیو برای فشرده‌سازی بزرگ‌تر از حد مجازه (ربات فقط ویدیوهای تا ۲۰ مگ"
            " رو می‌تونه دوباره پردازش کنه)."
        ),
        "en": (
            "📦 This video is too large to compress (the bot can only re-process videos"
            " up to 20 MB)."
        ),
    },
    "COMPRESS_UNAVAILABLE": {
        "fa": "🛠 قابلیت فشرده‌سازی روی سرور فعال نیست (ffmpeg نصب نشده).",
        "en": "🛠 Compression isn't available on the server (ffmpeg is not installed).",
    },
    "COMPRESS_BUSY": {
        "fa": "🚦 ربات الان شلوغه. چند لحظه دیگه دوباره روی دکمه بزن.",
        "en": "🚦 The bot is busy right now. Tap the button again in a moment.",
    },
    "COMPRESS_NOT_FOUND": {
        "fa": "🤔 این ویدیو دیگه در دسترس نیست. دوباره لینکش رو بفرست.",
        "en": "🤔 This video is no longer available. Send its link again.",
    },
    # ---------------------------------- دکمه‌ی دریافت موزیک / صدا
    "AUDIO_BUTTON": {"fa": "🎵 دریافت موزیک / صدا", "en": "🎵 Get music / audio"},
    "AUDIO_TITLE": {"fa": "صدای ریلز", "en": "Reel audio"},
    "AUDIO_SONG_LINE": {
        "fa": (
            "🎵 آهنگِ شناسایی‌شده:\n"
            "<code>{name}</code>\n\n"
            "👆 روی نامِ آهنگ بزن تا کپی بشه."
        ),
        "en": (
            "🎵 Identified track:\n"
            "<code>{name}</code>\n\n"
            "👆 Tap the track name to copy it."
        ),
    },
    "AUDIO_WORKING": {
        "fa": "⏳ دارم صدای ریلز رو جدا می‌کنم...",
        "en": "⏳ Extracting the reel's audio...",
    },
    "AUDIO_FAILED": {
        "fa": "😕 نتونستم صدای این ویدیو رو جدا کنم. کمی بعد دوباره امتحان کن.",
        "en": "😕 I couldn't extract this video's audio. Try again a little later.",
    },
    "AUDIO_NO_TRACK": {
        "fa": "🔇 این ویدیو اصلاً صدا نداره؛ چیزی برای استخراج نیست.",
        "en": "🔇 This video has no audio at all; there's nothing to extract.",
    },
    "AUDIO_TOO_LARGE": {
        "fa": (
            "📦 این ویدیو برای جدا کردنِ صدا بزرگ‌تر از حد مجازه (ربات فقط ویدیوهای تا ۲۰ مگ"
            " رو می‌تونه پردازش کنه)."
        ),
        "en": (
            "📦 This video is too large to extract audio from (the bot can only process"
            " videos up to 20 MB)."
        ),
    },
    "AUDIO_UNAVAILABLE": {
        "fa": "🛠 قابلیت جدا کردنِ صدا روی سرور فعال نیست (ffmpeg نصب نشده).",
        "en": "🛠 Audio extraction isn't available on the server (ffmpeg is not installed).",
    },
    "AUDIO_BUSY": {
        "fa": "🚦 ربات الان شلوغه. چند لحظه دیگه دوباره روی دکمه بزن.",
        "en": "🚦 The bot is busy right now. Tap the button again in a moment.",
    },
    "AUDIO_NOT_FOUND": {
        "fa": "🤔 این ویدیو دیگه در دسترس نیست. دوباره لینکش رو بفرست.",
        "en": "🤔 This video is no longer available. Send its link again.",
    },
    # ------------------------------------------- سهمیه‌ی روزانه
    "QUOTA_REACHED_FREE": {
        "fa": (
            "🚫 سهمیه‌ی امروزت تموم شد!\n\n"
            "🆓 کاربرای عادی روزانه {limit} تا دانلود دارن.\n"
            "💎 با اشتراکِ VIP روزی {vip_limit} تا دانلود کن، اون‌هم بدونِ عضویتِ اجباری در کانال‌ها!\n\n"
            "👇 برای تهیه‌ی اشتراک بزن:"
        ),
        "en": (
            "🚫 You've used up today's quota!\n\n"
            "🆓 Free users get {limit} downloads per day.\n"
            "💎 With a VIP subscription, download {vip_limit} per day — and with no forced channel membership!\n\n"
            "👇 Tap to get a subscription:"
        ),
    },
    "QUOTA_REACHED_VIP": {
        "fa": (
            "🚫 سهمیه‌ی امروزت تموم شد!\n\n"
            "💎 تو الان VIP هستی و روزانه {limit} دانلود داری.\n"
            "⏳ سهمیه‌ت فردا دوباره شارژ می‌شه. 🙏"
        ),
        "en": (
            "🚫 You've used up today's quota!\n\n"
            "💎 You're currently VIP with {limit} downloads per day.\n"
            "⏳ Your quota recharges tomorrow. 🙏"
        ),
    },
    "AUDIO_QUOTA_FREE": {
        "fa": (
            "🚫 سهمیه‌ی امروزِ گرفتنِ صدا تموم شد!\n\n"
            "🆓 کاربرای عادی روزانه {limit} تا صدا می‌تونن بگیرن.\n"
            "💎 با اشتراکِ VIP روزی {vip_limit} تا صدا بگیر!\n\n"
            "👇 برای تهیه‌ی اشتراک بزن:"
        ),
        "en": (
            "🚫 You've used up today's audio quota!\n\n"
            "🆓 Free users can grab {limit} audios per day.\n"
            "💎 With a VIP subscription, grab {vip_limit} audios per day!\n\n"
            "👇 Tap to get a subscription:"
        ),
    },
    "AUDIO_QUOTA_VIP": {
        "fa": (
            "🚫 سهمیه‌ی امروزِ گرفتنِ صدا تموم شد!\n\n"
            "💎 تو الان VIP هستی و روزانه {limit} تا صدا می‌تونی بگیری.\n"
            "⏳ سهمیه‌ت فردا دوباره شارژ می‌شه. 🙏"
        ),
        "en": (
            "🚫 You've used up today's audio quota!\n\n"
            "💎 You're currently VIP and can grab {limit} audios per day.\n"
            "⏳ Your quota recharges tomorrow. 🙏"
        ),
    },
    "COMPRESS_QUOTA_FREE": {
        "fa": (
            "🚫 سهمیه‌ی امروزِ نسخه‌ی کم‌حجم تموم شد!\n\n"
            "🆓 کاربرای عادی روزانه {limit} تا نسخه‌ی کم‌حجم می‌تونن بگیرن.\n"
            "💎 با اشتراکِ VIP روزی {vip_limit} تا!\n\n"
            "👇 برای تهیه‌ی اشتراک بزن:"
        ),
        "en": (
            "🚫 You've used up today's lighter-version quota!\n\n"
            "🆓 Free users can grab {limit} lighter versions per day.\n"
            "💎 With a VIP subscription, {vip_limit} per day!\n\n"
            "👇 Tap to get a subscription:"
        ),
    },
    "COMPRESS_QUOTA_VIP": {
        "fa": (
            "🚫 سهمیه‌ی امروزِ نسخه‌ی کم‌حجم تموم شد!\n\n"
            "💎 تو الان VIP هستی و روزانه {limit} تا نسخه‌ی کم‌حجم می‌تونی بگیری.\n"
            "⏳ سهمیه‌ت فردا دوباره شارژ می‌شه. 🙏"
        ),
        "en": (
            "🚫 You've used up today's lighter-version quota!\n\n"
            "💎 You're currently VIP and can grab {limit} lighter versions per day.\n"
            "⏳ Your quota recharges tomorrow. 🙏"
        ),
    },
    # ---------------------------------------- اشتراکِ ویژه (VIP)
    "VIP_INFO": {
        "fa": (
            "💎 اشتراکِ ویژه (VIP)\n\n"
            "✨ مزایا:\n"
            "• 📥 روزانه {vip_limit} دانلود (به‌جای {free_limit} تا)\n"
            "• 🚪 بدونِ عضویتِ اجباری در هیچ کانالی\n"
            "• ⚡️ پشتیبانی و اولویتِ بیشتر\n\n"
            "💰 قیمت: {price} ⭐️  برای {days} روز\n\n"
            "👇 برای پرداخت با Stars بزن:"
        ),
        "en": (
            "💎 Premium subscription (VIP)\n\n"
            "✨ Benefits:\n"
            "• 📥 {vip_limit} downloads per day (instead of {free_limit})\n"
            "• 🚪 No forced membership in any channel\n"
            "• ⚡️ Priority support\n\n"
            "💰 Price: {price} ⭐️  for {days} days\n\n"
            "👇 Tap to pay with Stars:"
        ),
    },
    "VIP_ALREADY": {
        "fa": (
            "💎 تو هم‌اکنون VIP هستی! 🎉\n\n"
            "⏳ اعتبار تا: {until}\n"
            "📥 سهمیه‌ی امروزت: {used} از {limit}"
        ),
        "en": (
            "💎 You're already VIP! 🎉\n\n"
            "⏳ Valid until: {until}\n"
            "📥 Today's quota: {used} of {limit}"
        ),
    },
    "VIP_STATUS_FREE": {
        "fa": (
            "🆓 حسابِ تو عادیه.\n"
            "📥 سهمیه‌ی امروزت: {used} از {limit}\n\n"
            "💎 برای دانلودِ بیشتر و حذفِ عضویتِ اجباری، دستورِ /vip رو بزن."
        ),
        "en": (
            "🆓 Your account is a free account.\n"
            "📥 Today's quota: {used} of {limit}\n\n"
            "💎 For more downloads and no forced membership, use /vip."
        ),
    },
    "VIP_BUY_BUTTON": {"fa": "💎 پرداخت {price} ⭐️", "en": "💎 Pay {price} ⭐️"},
    "VIP_INVOICE_TITLE": {"fa": "اشتراک ویژه (VIP)", "en": "Premium subscription (VIP)"},
    "VIP_INVOICE_DESC": {
        "fa": "📥 روزانه {vip_limit} دانلود + بدونِ عضویتِ اجباری — برای {days} روز.",
        "en": "📥 {vip_limit} downloads per day + no forced membership — for {days} days.",
    },
    "VIP_PAYMENT_OK": {
        "fa": (
            "🎉 پرداخت موفق بود! خیلی ممنون بابتِ حمایتت 🙏\n\n"
            "💎 اشتراکِ VIP فعال شد.\n"
            "⏳ اعتبار تا: {until}\n"
            "📥 از الان روزانه {limit} دانلود داری و عضویتِ اجباری برات لازم نیست. ✨"
        ),
        "en": (
            "🎉 Payment successful! Thank you so much for your support 🙏\n\n"
            "💎 Your VIP subscription is active.\n"
            "⏳ Valid until: {until}\n"
            "📥 You now have {limit} downloads per day and no forced membership. ✨"
        ),
    },
    "VIP_PAYMENT_FAILED": {
        "fa": "😕 پرداخت کامل نشد. اگه ⭐️ ازت کم شده ولی اشتراک فعال نشد به ادمین خبر بده.",
        "en": "😕 The payment didn't complete. If ⭐️ were deducted but VIP isn't active, contact the admin.",
    },
    "VIP_INVALID_INVOICE": {
        "fa": "فاکتور نامعتبر است.",
        "en": "Invalid invoice.",
    },
    "VIP_GRANTED_NOTIFY": {
        "fa": (
            "🎁 یه ادمین بهت اشتراکِ VIP داد! 🎉\n\n"
            "⏳ اعتبار تا: {until}\n"
            "📥 روزانه {limit} دانلود + بدونِ عضویتِ اجباری. ✨"
        ),
        "en": (
            "🎁 An admin granted you a VIP subscription! 🎉\n\n"
            "⏳ Valid until: {until}\n"
            "📥 {limit} downloads per day + no forced membership. ✨"
        ),
    },
    "VIP_REVOKED_NOTIFY": {
        "fa": "ℹ️ اشتراکِ VIP حسابت توسط ادمین لغو شد.",
        "en": "ℹ️ Your VIP subscription was revoked by an admin.",
    },
    # ------------------------------------------------ پنل ادمین
    "ADMIN_ONLY": {
        "fa": "⛔️ این دستور فقط مخصوص ادمینه.",
        "en": "⛔️ This command is for admins only.",
    },
    "MENU_MAIN": {"fa": "🏠 منوی اصلی.", "en": "🏠 Main menu."},
    "ADMIN_PANEL": {
        "fa": (
            "🛠 پنل مدیریت\n\n"
            "👇 از دکمه‌های پایین استفاده کن:\n"
            "• ➕ افزودن کانال / ➖ حذف کانال / 📋 کانال‌ها\n"
            "• 📊 آمار / 👥 کاربران\n"
            "• 💰 قیمت اشتراک / ⏳ مدت اشتراک\n"
            "• 📡 تنظیم گروه اطلاع‌رسانی (تیکت‌ها و هشدارها)\n\n"
            "💎 دادن/گرفتنِ دستیِ VIP (با آیدی یا یوزرنیم):\n"
            "• /vipadd — دادنِ VIP به کاربر\n"
            "• /vipremove — گرفتنِ VIP از کاربر\n\n"
            "📣 پیامِ همگانی:\n"
            "• /broadcast — ارسالِ پیام به همه‌ی کاربرها\n"
            "• /undobroadcast — حذفِ آخرین پیامِ همگانی\n\n"
            "🔙 برای برگشت به منوی اصلی «بازگشت» رو بزن."
        ),
        "en": (
            "🛠 Admin panel\n\n"
            "👇 Use the buttons below:\n"
            "• ➕ Add channel / ➖ Remove channel / 📋 Channels\n"
            "• 📊 Stats / 👥 Users\n"
            "• 💰 Sub price / ⏳ Sub duration\n"
            "• 📡 Notify group setup (tickets & alerts)\n\n"
            "💎 Grant/revoke VIP manually (by ID or username):\n"
            "• /vipadd — grant VIP to a user\n"
            "• /vipremove — revoke VIP from a user\n\n"
            "📣 Broadcast:\n"
            "• /broadcast — send a message to all users\n"
            "• /undobroadcast — delete the last broadcast\n\n"
            "🔙 Tap «Back» to return to the main menu."
        ),
    },
    # --------------------------------- ادمین: قیمت/مدت/VIP
    "ADMIN_PRICE_USAGE": {
        "fa": "🔧 طرزِ استفاده: /setprice <تعدادِ ⭐️>\nمثال: /setprice 50",
        "en": "🔧 Usage: /setprice <number of ⭐️>\nExample: /setprice 50",
    },
    "ADMIN_PRICE_OK": {
        "fa": "✅ قیمتِ اشتراکِ VIP روی {price} ⭐️ تنظیم شد.",
        "en": "✅ VIP price set to {price} ⭐️.",
    },
    "ADMIN_DURATION_USAGE": {
        "fa": "🔧 طرزِ استفاده: /setduration <تعدادِ روز>\nمثال: /setduration 30",
        "en": "🔧 Usage: /setduration <number of days>\nExample: /setduration 30",
    },
    "ADMIN_DURATION_OK": {
        "fa": "✅ مدتِ اشتراکِ VIP روی {days} روز تنظیم شد.",
        "en": "✅ VIP duration set to {days} days.",
    },
    "ADMIN_VIPADD_USAGE": {
        "fa": (
            "🔧 طرزِ استفاده: /vipadd <آیدیِ عددی یا @یوزرنیم> [تعدادِ روز]\n"
            "مثال: /vipadd 123456789 30\n"
            "اگه تعدادِ روز رو ننویسی، پیش‌فرضِ {days} روز اعمال می‌شه."
        ),
        "en": (
            "🔧 Usage: /vipadd <numeric ID or @username> [number of days]\n"
            "Example: /vipadd 123456789 30\n"
            "If you omit the days, the default of {days} days is applied."
        ),
    },
    "ADMIN_VIPADD_OK": {
        "fa": "✅ به کاربرِ {user} اشتراکِ VIP داده شد.\n⏳ اعتبار تا: {until}",
        "en": "✅ VIP granted to user {user}.\n⏳ Valid until: {until}",
    },
    "ADMIN_VIPREMOVE_USAGE": {
        "fa": "🔧 طرزِ استفاده: /vipremove <آیدیِ عددی یا @یوزرنیم>",
        "en": "🔧 Usage: /vipremove <numeric ID or @username>",
    },
    "ADMIN_VIPREMOVE_OK": {
        "fa": "🗑 اشتراکِ VIP کاربرِ {user} لغو شد.",
        "en": "🗑 VIP revoked from user {user}.",
    },
    "ADMIN_VIPREMOVE_NOT_VIP": {
        "fa": "ℹ️ این کاربر اشتراکِ VIP فعالی نداشت.",
        "en": "ℹ️ This user didn't have an active VIP subscription.",
    },
    "ADMIN_USER_NOT_FOUND": {
        "fa": (
            "🤔 کاربری با این مشخصات پیدا نشد.\n"
            "(کاربر باید حداقل یه‌بار ربات رو /start کرده باشه تا با یوزرنیم پیدا بشه؛ "
            "وگرنه آیدیِ عددیش رو بده.)"
        ),
        "en": (
            "🤔 No user found with those details.\n"
            "(The user must have /start-ed the bot at least once to be found by username; "
            "otherwise provide their numeric ID.)"
        ),
    },
    "ADMIN_USERS_HEADER": {
        "fa": "👥 کاربران — کل: {total}  |  💎 VIP: {vip}\n",
        "en": "👥 Users — total: {total}  |  💎 VIP: {vip}\n",
    },
    "ADMIN_USERS_EMPTY": {
        "fa": "📭 هنوز هیچ کاربری ثبت نشده.",
        "en": "📭 No users registered yet.",
    },
    "ADMIN_USERS_MORE": {
        "fa": "\n… و {n} کاربرِ دیگه (فقط {shown} تای اول نشون داده شد).",
        "en": "\n… and {n} more users (only the first {shown} are shown).",
    },
    "ADMIN_USERS_VIP_UNTIL": {"fa": " — تا {until}", "en": " — until {until}"},
    "ADD_CHANNEL_ASK_TITLE": {
        "fa": (
            "📝 یه عنوان برای این کانال بفرست (همونی که روی دکمه‌ی «عضویت» نشون داده می‌شه).\n"
            "مثال: کانال اصلی ما 🔥\n\n"
            "برای لغو /cancel رو بزن."
        ),
        "en": (
            "📝 Send a title for this channel (shown on the «Join» button).\n"
            "Example: Our Main Channel 🔥\n\n"
            "Tap /cancel to abort."
        ),
    },
    "ADD_CHANNEL_ASK_DAYS": {
        "fa": (
            "⏳ چند روز این کانال توی لیستِ اجباری بمونه؟\n"
            "یه عدد بفرست — «0» یعنی نامحدود (همیشگی)."
        ),
        "en": (
            "⏳ For how many days should this channel stay required?\n"
            "Send a number — «0» means unlimited (permanent)."
        ),
    },
    "ADD_CHANNEL_BAD_DAYS": {
        "fa": "لطفاً فقط یه عددِ صحیح بفرست (مثلاً 30، یا 0 برای نامحدود).",
        "en": "Please send a whole number only (e.g. 30, or 0 for unlimited).",
    },
    "CH_DUR_UNLIMITED": {"fa": "نامحدود ♾", "en": "unlimited ♾"},
    "CH_DUR_DAYS": {"fa": "{days} روز", "en": "{days} days"},
    "CH_DUR_UNTIL": {"fa": "تا {date}", "en": "until {date}"},
    "ADD_CHANNEL_ASK": {
        "fa": (
            "یوزرنیم یا آیدی کانال رو بفرست.\n"
            "مثال: @mychannel یا -1001234567890\n\n"
            "⚠️ ربات حتماً باید توی اون کانال ادمین باشه، وگرنه نمی‌تونه عضویت رو بررسی کنه.\n\n"
            "برای لغو /cancel رو بزن."
        ),
        "en": (
            "Send the channel's username or ID.\n"
            "Example: @mychannel or -1001234567890\n\n"
            "⚠️ The bot must be an admin in that channel, otherwise it can't check membership.\n\n"
            "Tap /cancel to abort."
        ),
    },
    "ADD_CHANNEL_OK": {
        "fa": "✅ کانال «{title}» به لیست اجباری اضافه شد.\n⏳ موندگاری: {dur}",
        "en": "✅ Channel «{title}» was added to the required list.\n⏳ Duration: {dur}",
    },
    "ADD_CHANNEL_RENEWED": {
        "fa": "♻️ کانال «{title}» قبلاً بود؛ عنوان و موندگاریش به‌روز شد.\n⏳ موندگاری: {dur}",
        "en": "♻️ Channel «{title}» already existed; its title and duration were updated.\n⏳ Duration: {dur}",
    },
    "ADD_CHANNEL_EXISTS": {
        "fa": "ℹ️ این کانال از قبل توی لیست اجباری هست.",
        "en": "ℹ️ This channel is already in the required list.",
    },
    "ADD_CHANNEL_BOT_NOT_ADMIN": {
        "fa": "⚠️ من توی این کانال ادمین نیستم. اول من رو ادمین کن بعد دوباره اضافه کن.",
        "en": "⚠️ I'm not an admin in that channel. Make me an admin first, then add it again.",
    },
    "ADD_CHANNEL_FAILED": {
        "fa": (
            "❌ نتونستم به این کانال دسترسی پیدا کنم.\n"
            "مطمئن شو یوزرنیم/آیدی درسته و ربات داخل کانال ادمینه."
        ),
        "en": (
            "❌ I couldn't access that channel.\n"
            "Make sure the username/ID is correct and the bot is an admin in the channel."
        ),
    },
    "REMOVE_CHANNEL_ASK": {
        "fa": "یوزرنیم یا آیدی کانالی که می‌خوای حذف بشه رو بفرست.\nبرای لغو /cancel رو بزن.",
        "en": "Send the username or ID of the channel you want to remove.\nTap /cancel to abort.",
    },
    "REMOVE_CHANNEL_OK": {
        "fa": "🗑 کانال از لیست اجباری حذف شد.",
        "en": "🗑 The channel was removed from the required list.",
    },
    "REMOVE_CHANNEL_NOT_FOUND": {
        "fa": "🤔 همچین کانالی توی لیست اجباری نبود.",
        "en": "🤔 No such channel in the required list.",
    },
    "CHANNELS_EMPTY": {
        "fa": "📭 فعلاً هیچ کانال اجباری‌ای تنظیم نشده.",
        "en": "📭 No required channels configured yet.",
    },
    "CHANNELS_HEADER": {"fa": "📋 کانال‌های اجباری:\n", "en": "📋 Required channels:\n"},
    "CANCELLED": {"fa": "لغو شد.", "en": "Cancelled."},
    "STATS": {
        "fa": (
            "📊 آمار ربات\n\n"
            "👥 تعداد کاربران: {users}\n"
            "💎 کاربرانِ VIP: {vip}\n"
            "📢 کانال‌های اجباری: {channels}"
        ),
        "en": (
            "📊 Bot stats\n\n"
            "👥 Users: {users}\n"
            "💎 VIP users: {vip}\n"
            "📢 Required channels: {channels}"
        ),
    },
    # هشدار خودکار به ادمین وقتی کوکی لاگین می‌سوزه/ریت‌لیمیت می‌خوریم
    "COOKIE_EXPIRED_ADMIN": {
        "fa": (
            "⚠️ هشدار سیستمی\n\n"
            "ربات نتونست از اینستاگرام دانلود کنه و خطاها نشون می‌دن که کوکی لاگین "
            "(sessionid) منقضی شده، نامعتبره یا اصلاً تنظیم نشده.\n\n"
            "🔧 یه sessionid تازه از مرورگر بگیر، توی فایل .env مقدار "
            "INSTAGRAM_SESSIONID رو به‌روز کن و بعد ربات رو ری‌استارت کن."
        ),
        "en": (
            "⚠️ System alert\n\n"
            "The bot couldn't download from Instagram, and the errors indicate the login "
            "cookie (sessionid) is expired, invalid, or not set at all.\n\n"
            "🔧 Grab a fresh sessionid from your browser, update INSTAGRAM_SESSIONID in the "
            ".env file, and then restart the bot."
        ),
    },
    "ALERT_FAILING_LINK": {
        "fa": "\n\n🔗 لینکِ ناموفق (برای بررسی):\n<code>{url}</code>",
        "en": "\n\n🔗 Failing link (for review):\n<code>{url}</code>",
    },
    "DOWNLOAD_FAILED_AUTH": {
        "fa": (
            "😕 نتونستم این محتوا رو بگیرم.\n\n"
            "ممکنه پست خصوصی، حذف‌شده یا موقتاً محدود شده باشه. اول خودت لینک رو باز کن و"
            " مطمئن شو باز می‌شه. اگه فکر می‌کنی مشکل از رباته، از دکمه‌ی پشتیبانی برامون بنویس. 🙏"
        ),
        "en": (
            "😕 I couldn't fetch this content.\n\n"
            "It may be private, deleted, or temporarily restricted. First open the link"
            " yourself and make sure it works. If you think the bot is at fault, message us"
            " via the support button. 🙏"
        ),
    },
    # ------------------------------- دکمه‌های این‌لاینِ متن‌دار
    "OPEN_LINK_BUTTON": {"fa": "🔗 باز کردن لینک", "en": "🔗 Open link"},
    "SUPPORT_INLINE_BUTTON": {"fa": "💬 ارتباط با پشتیبانی", "en": "💬 Contact support"},
    # --------------------------------------- پشتیبانی (تیکت)
    "SUPPORT_ASK": {
        "fa": (
            "✍️ پیامت رو برای پشتیبانی بنویس و بفرست.\n"
            "تیمِ پشتیبانی در اولین فرصت همین‌جا جوابت رو می‌ده.\n\n"
            "برای انصراف «❌ لغو» رو بزن."
        ),
        "en": (
            "✍️ Write your message for support and send it.\n"
            "The support team will reply here as soon as possible.\n\n"
            "Tap «❌ Cancel» to abort."
        ),
    },
    "SUPPORT_SENT": {
        "fa": "✅ پیامت برای پشتیبانی ثبت و ارسال شد. به‌زودی جوابت رو همین‌جا می‌گیری. 🙏",
        "en": "✅ Your message was sent to support. You'll get a reply here soon. 🙏",
    },
    "SUPPORT_TOO_MANY": {
        "fa": (
            "⏳ تو چند تا پیامِ بی‌پاسخ نزدِ پشتیبانی داری.\n"
            "لطفاً تا رسیدنِ جوابِ اون‌ها کمی صبر کن."
        ),
        "en": (
            "⏳ You have a few unanswered messages with support.\n"
            "Please wait until they're answered."
        ),
    },
    "SUPPORT_CANCELLED": {
        "fa": "باشه، از پشتیبانی خارج شدی.",
        "en": "Okay, you've left support.",
    },
    "SUPPORT_TICKET_CARD": {
        "fa": (
            "🎫 <b>تیکتِ جدیدِ پشتیبانی</b>  #{ticket_id}\n\n"
            "👤 کاربر: {name}{handle}\n"
            "🆔 <code>{user_id}</code>\n\n"
            "💬 پیام:\n{message}\n\n"
            "↩️ برای پاسخ، روی همین پیام <b>ریپلای</b> کن و جوابت رو بنویس."
        ),
        "en": (
            "🎫 <b>New support ticket</b>  #{ticket_id}\n\n"
            "👤 User: {name}{handle}\n"
            "🆔 <code>{user_id}</code>\n\n"
            "💬 Message:\n{message}\n\n"
            "↩️ To reply, <b>reply</b> to this message and write your answer."
        ),
    },
    "SUPPORT_REPLY_TO_USER": {
        "fa": "💬 <b>پاسخِ پشتیبانی:</b>\n\n{text}",
        "en": "💬 <b>Support reply:</b>\n\n{text}",
    },
    "SUPPORT_REPLY_DONE": {
        "fa": "✅ پاسخت برای کاربر ارسال شد.",
        "en": "✅ Your reply was sent to the user.",
    },
    "SUPPORT_REPLY_FAILED": {
        "fa": "⚠️ نتونستم پیام رو به کاربر برسونم (شاید ربات رو بلاک کرده).",
        "en": "⚠️ I couldn't deliver the message to the user (they may have blocked the bot).",
    },
    # ---------------- تنظیمِ گروهِ اطلاع‌رسانی/پشتیبانی (ادمین لینکِ تاپیک می‌ده)
    "GROUP_HUB_INTRO": {
        "fa": (
            "📡 <b>تنظیمِ گروهِ اطلاع‌رسانی و پشتیبانی</b>\n\n"
            "وضعیتِ فعلی:\n"
            "• گروه: {group}\n"
            "• تاپیکِ تیکت‌های پشتیبانی: {tickets}\n"
            "• تاپیکِ هشدارها/اطلاع‌رسانی: {alerts}\n\n"
            "📝 راهنما:\n"
            "۱) یه سوپرگروه بساز و قابلیتِ «تاپیک‌ها (Topics)» رو روشن کن.\n"
            "۲) رباتو عضوِ گروه کن و <b>ادمینش</b> کن.\n"
            "۳) دو تا تاپیک بساز: یکی برای «تیکت‌های پشتیبانی» و یکی برای «هشدارها».\n"
            "۴) داخلِ هر تاپیک، از منو روی «Copy Link / کپیِ لینک» بزن و لینکش رو همین‌جا بفرست."
        ),
        "en": (
            "📡 <b>Notification & support group setup</b>\n\n"
            "Current status:\n"
            "• Group: {group}\n"
            "• Support tickets topic: {tickets}\n"
            "• Alerts/notifications topic: {alerts}\n\n"
            "📝 Guide:\n"
            "1) Create a supergroup and enable «Topics».\n"
            "2) Add the bot to the group and make it an <b>admin</b>.\n"
            "3) Create two topics: one for «support tickets» and one for «alerts».\n"
            "4) In each topic, tap «Copy Link» from the menu and send the link here."
        ),
    },
    "GROUP_HUB_ASK_TICKETS": {
        "fa": (
            "1️⃣ لینکِ تاپیکِ «تیکت‌های پشتیبانی» رو بفرست.\n"
            "مثال: https://t.me/c/1234567890/12\n\n"
            "اگه نمی‌خوای الان تنظیمش کنی «➖ رد کردن» و برای انصراف «❌ لغو» رو بزن."
        ),
        "en": (
            "1️⃣ Send the link to the «support tickets» topic.\n"
            "Example: https://t.me/c/1234567890/12\n\n"
            "If you don't want to set it now, tap «➖ Skip», or «❌ Cancel» to abort."
        ),
    },
    "GROUP_HUB_ASK_ALERTS": {
        "fa": (
            "2️⃣ حالا لینکِ تاپیکِ «هشدارها/اطلاع‌رسانی» رو بفرست.\n"
            "مثال: https://t.me/c/1234567890/34\n\n"
            "برای پرش «➖ رد کردن» و برای انصراف «❌ لغو» رو بزن."
        ),
        "en": (
            "2️⃣ Now send the link to the «alerts/notifications» topic.\n"
            "Example: https://t.me/c/1234567890/34\n\n"
            "Tap «➖ Skip» to skip, or «❌ Cancel» to abort."
        ),
    },
    "GROUP_HUB_BAD_LINK": {
        "fa": (
            "🤔 این لینکِ تاپیک معتبر نبود.\n"
            "از داخلِ تاپیک، گزینه‌ی «Copy Link» رو بزن؛ لینک باید مثلِ "
            "https://t.me/c/1234567890/12 باشه. دوباره بفرست یا «❌ لغو» رو بزن."
        ),
        "en": (
            "🤔 That topic link wasn't valid.\n"
            "Inside the topic, tap «Copy Link»; the link should look like "
            "https://t.me/c/1234567890/12. Send it again or tap «❌ Cancel»."
        ),
    },
    "GROUP_HUB_TICKETS_SET": {
        "fa": "✅ تاپیکِ تیکت‌های پشتیبانی ثبت شد.",
        "en": "✅ The support tickets topic was saved.",
    },
    "GROUP_HUB_ALERTS_SET": {
        "fa": "✅ تاپیکِ هشدارها/اطلاع‌رسانی ثبت شد.",
        "en": "✅ The alerts/notifications topic was saved.",
    },
    "GROUP_HUB_DONE": {
        "fa": (
            "🎉 <b>تنظیمِ گروه تموم شد.</b>\n\n"
            "• گروه: {group}\n"
            "• تاپیکِ تیکت‌ها: {tickets}\n"
            "• تاپیکِ هشدارها: {alerts}\n\n"
            "از این به بعد تیکت‌های کاربرا و هشدارهای سیستمی به همین تاپیک‌ها می‌رن."
        ),
        "en": (
            "🎉 <b>Group setup complete.</b>\n\n"
            "• Group: {group}\n"
            "• Tickets topic: {tickets}\n"
            "• Alerts topic: {alerts}\n\n"
            "From now on, user tickets and system alerts go to these topics."
        ),
    },
    "GROUP_HUB_CANCELLED": {
        "fa": "تنظیمِ گروه لغو شد.",
        "en": "Group setup cancelled.",
    },
    "GROUP_HUB_TEST_TICKETS": {
        "fa": "✅ این تاپیک به‌عنوانِ «تیکت‌های پشتیبانی» تنظیم شد.",
        "en": "✅ This topic was set as «support tickets».",
    },
    "GROUP_HUB_TEST_ALERTS": {
        "fa": "✅ این تاپیک به‌عنوانِ «هشدارها/اطلاع‌رسانی» تنظیم شد.",
        "en": "✅ This topic was set as «alerts/notifications».",
    },
    "GROUP_HUB_SEND_FAILED": {
        "fa": (
            "⚠️ لینک ثبت شد ولی نتونستم به تاپیک پیام بفرستم.\n"
            "مطمئن شو ربات توی گروه <b>ادمینه</b> و توی همون تاپیک اجازه‌ی ارسال داره."
        ),
        "en": (
            "⚠️ The link was saved but I couldn't send a message to the topic.\n"
            "Make sure the bot is an <b>admin</b> in the group and is allowed to post in that topic."
        ),
    },
    # ------------------------------------------- انتخابِ زبان
    # هنگامِ پرسش هنوز زبانِ کاربر رو نمی‌دونیم، پس متن دوزبانه‌ست (خنثی).
    "CHOOSE_LANG_PROMPT": (
        "🌐 لطفاً زبانِ ربات را انتخاب کن:\n"
        "Please choose the bot language:"
    ),
    "LANG_SET": {
        "fa": "✅ زبان روی «فارسی» تنظیم شد.",
        "en": "✅ Language set to «English».",
    },
    # ----------------------------------- پیامِ همگانی (ادمین)
    "BROADCAST_USAGE": {
        "fa": (
            "🔧 طرزِ استفاده:\n"
            "• /broadcast <متن> — ارسالِ متن به همه‌ی کاربرها\n"
            "• یا روی هر پیامی (حتی عکس/ویدیو) ریپلای کن و /broadcast بزن تا همون عیناً همگانی بشه."
        ),
        "en": (
            "🔧 Usage:\n"
            "• /broadcast <text> — send text to all users\n"
            "• or reply to any message (even a photo/video) with /broadcast to broadcast it as-is."
        ),
    },
    "BROADCAST_STARTED": {
        "fa": "📣 شروعِ ارسالِ همگانی به {count} کاربر... وقتی تموم شد خبر می‌دم.",
        "en": "📣 Broadcasting to {count} users... I'll let you know when it's done.",
    },
    "BROADCAST_DONE": {
        "fa": "✅ ارسالِ همگانی تموم شد.\n📤 موفق: {sent}\n⚠️ ناموفق: {failed}",
        "en": "✅ Broadcast complete.\n📤 Sent: {sent}\n⚠️ Failed: {failed}",
    },
    "BROADCAST_UNDO_NONE": {
        "fa": "📭 هیچ پیامِ همگانیِ قبلی‌ای برای حذف نیست.",
        "en": "📭 There's no previous broadcast to delete.",
    },
    "BROADCAST_UNDO_STARTED": {
        "fa": "🗑 در حال حذفِ {count} پیامِ همگانیِ قبلی...",
        "en": "🗑 Deleting {count} messages from the previous broadcast...",
    },
    "BROADCAST_UNDO_DONE": {
        "fa": "✅ حذفِ پیامِ همگانیِ قبلی تموم شد.\n🗑 حذف‌شده: {deleted}\n⚠️ ناموفق: {failed}",
        "en": "✅ Previous broadcast removed.\n🗑 Deleted: {deleted}\n⚠️ Failed: {failed}",
    },
    # ------------------------- منابعِ زنده: کوکی/پروکسی (ادمین، بدونِ ری‌استارت)
    "SOURCE_PRIVATE_ONLY": {
        "fa": "🔒 این دستور به‌خاطرِ امنیت فقط در چتِ خصوصی با ربات کار می‌کنه.",
        "en": "🔒 For security, this command only works in a private chat with the bot.",
    },
    "ADDCOOKIE_USAGE": {
        "fa": (
            "🍪 افزودنِ کوکی (sessionid) — بدونِ خاموش/روشنِ ربات:\n"
            "/addcookie [sessionid]\n\n"
            "می‌تونی چند کوکی رو با کاما یا خطِ جدید پشتِ‌سرِ هم هم بفرستی.\n"
            "🔒 بعد از افزودن، پیامِ حاویِ کوکی رو پاک کن."
        ),
        "en": (
            "🍪 Add a cookie (sessionid) — no bot restart needed:\n"
            "/addcookie [sessionid]\n\n"
            "You can add several at once, separated by commas or new lines.\n"
            "🔒 After adding, delete the message that contained the cookie."
        ),
    },
    "ADDCOOKIE_OK": {
        "fa": (
            "✅ {added} کوکیِ جدید اضافه شد. الان {total} کوکیِ فعال داری.\n"
            "🔒 برای امنیت، پیامِ حاویِ کوکی رو پاک کن."
        ),
        "en": (
            "✅ Added {added} new cookie(s). You now have {total} active cookie(s).\n"
            "🔒 For security, please delete the message that contained the cookie."
        ),
    },
    "ADDCOOKIE_DUP": {
        "fa": "ℹ️ چیزی اضافه نشد (کوکی خالی بود یا از قبل ثبت شده).",
        "en": "ℹ️ Nothing added (the cookie was empty or already registered).",
    },
    "ADDPROXY_USAGE": {
        "fa": (
            "🌐 افزودنِ پروکسیِ رزیدنشال — بدونِ خاموش/روشنِ ربات:\n"
            "/addproxy http://user:pass@host:port\n"
            "یا socks5://user:pass@host:port\n\n"
            "می‌تونی چند پروکسی رو هرکدوم توی یه خط پشتِ‌سرِ هم بفرستی."
        ),
        "en": (
            "🌐 Add a residential proxy — no bot restart needed:\n"
            "/addproxy http://user:pass@host:port\n"
            "or socks5://user:pass@host:port\n\n"
            "You can add several at once, one per line."
        ),
    },
    "ADDPROXY_OK": {
        "fa": "✅ {added} پروکسیِ جدید اضافه شد. الان استخر {total} پروکسیِ فعال داره.",
        "en": "✅ Added {added} new proxy(ies). The pool now has {total} active proxy(ies).",
    },
    "ADDPROXY_DUP": {
        "fa": "ℹ️ چیزی اضافه نشد (پروکسی خالی بود یا از قبل ثبت شده).",
        "en": "ℹ️ Nothing added (the proxy was empty or already registered).",
    },
    "SOURCES_VIEW": {
        "fa": (
            "🔑 منابعِ زنده‌ی دانلود\n"
            "(تغییرات بلافاصله و بدونِ ری‌استارت اعمال می‌شن)\n\n"
            "🍪 کوکی‌ها — از .env: {env_c} • زنده: {db_c}\n"
            "🌐 پروکسی‌ها — از .env: {env_p} • زنده: {db_p}\n\n"
            "➕ افزودن: /addcookie • /addproxy\n"
            "🗑 برای حذفِ هر موردِ زنده، روی دکمه‌اش بزن 👇"
        ),
        "en": (
            "🔑 Live download sources\n"
            "(changes apply instantly, no restart)\n\n"
            "🍪 Cookies — from .env: {env_c} • live: {db_c}\n"
            "🌐 Proxies — from .env: {env_p} • live: {db_p}\n\n"
            "➕ Add: /addcookie • /addproxy\n"
            "🗑 Tap a button below to remove a live item 👇"
        ),
    },
    "SOURCES_EMPTY_HINT": {
        "fa": "— هنوز موردِ زنده‌ای برای حذف نیست. با /addcookie یا /addproxy اضافه کن.",
        "en": "— No live items to remove yet. Add one with /addcookie or /addproxy.",
    },
    "SRC_REMOVED": {"fa": "🗑 حذف شد", "en": "🗑 Removed"},
    "SRC_REMOVE_FAILED": {"fa": "قبلاً حذف شده بود", "en": "Already removed"},
    # ------------------------- نگه‌داری: بکاپ، سلامت، بازپرداخت (ادمین)
    "BACKUP_WORKING": {
        "fa": "💾 در حالِ تهیه‌ی نسخه‌ی پشتیبانِ دیتابیس…",
        "en": "💾 Preparing a database backup…",
    },
    "BACKUP_CAPTION": {
        "fa": "✅ نسخه‌ی پشتیبانِ دیتابیس ({size} کیلوبایت).\n🔒 جای امنی نگهش دار.",
        "en": "✅ Database backup ({size} KB).\n🔒 Keep it somewhere safe.",
    },
    "BACKUP_FAILED": {
        "fa": "⚠️ تهیه‌ی بکاپ ناموفق بود:\n{error}",
        "en": "⚠️ Backup failed:\n{error}",
    },
    "HEALTH": {
        "fa": (
            "🩺 وضعیتِ ربات\n\n"
            "👥 کاربران: {users} (💎 VIP: {vip})\n"
            "🍪 کوکی‌های فعال: {cookies}\n"
            "🌐 پروکسی‌های فعال: {proxies}\n"
            "🎞 ffmpeg (فشرده/صدا): {ffmpeg}\n"
            "🎵 شناساییِ آهنگ: {shazam}\n"
            "🗂 کشِ مدیا: {cache} ردیف\n"
            "💾 حجمِ دیتابیس: {db_size}"
        ),
        "en": (
            "🩺 Bot health\n\n"
            "👥 Users: {users} (💎 VIP: {vip})\n"
            "🍪 Active cookies: {cookies}\n"
            "🌐 Active proxies: {proxies}\n"
            "🎞 ffmpeg (compress/audio): {ffmpeg}\n"
            "🎵 Song recognition: {shazam}\n"
            "🗂 Media cache: {cache} rows\n"
            "💾 Database size: {db_size}"
        ),
    },
    "REFUND_USAGE": {
        "fa": (
            "↩️ بازپرداختِ Telegram Stars:\n"
            "/refund [charge_id]\n"
            "یا /refund [آیدیِ عددی یا @یوزرنیم]\n\n"
            "با دادنِ کاربر، آخرین پرداختِ بازپرداخت‌نشده‌اش رفاند می‌شه."
        ),
        "en": (
            "↩️ Refund Telegram Stars:\n"
            "/refund [charge_id]\n"
            "or /refund [numeric id or @username]\n\n"
            "Given a user, their latest non-refunded payment is refunded."
        ),
    },
    "REFUND_OK": {
        "fa": "✅ بازپرداخت انجام شد.\n👤 کاربر: {user}\n⭐ مبلغ: {amount}\n📆 روزها: {days}",
        "en": "✅ Refund completed.\n👤 User: {user}\n⭐ Amount: {amount}\n📆 Days: {days}",
    },
    "REFUND_FAILED": {
        "fa": "⚠️ بازپرداخت ناموفق بود:\n{error}",
        "en": "⚠️ Refund failed:\n{error}",
    },
    "REFUND_NOT_FOUND": {
        "fa": "❌ پرداختی پیدا نشد (نه با این charge_id و نه برای این کاربر).",
        "en": "❌ No payment found (neither by that charge_id nor for that user).",
    },
    "REFUND_ALREADY": {
        "fa": "ℹ️ این پرداخت قبلاً بازپرداخت شده.",
        "en": "ℹ️ This payment has already been refunded.",
    },
    "REFUND_USER_NOTIFY": {
        "fa": "↩️ مبلغِ اشتراکِ ویژه‌ات بازپرداخت شد. ستاره‌ها به حسابت برگشتن.",
        "en": "↩️ Your premium payment has been refunded. The Stars are back in your account.",
    },
    # ------------------------- یادآوریِ انقضای VIP (کارِ روزانه) + سهمیه‌ی باقی‌مانده
    "VIP_EXPIRING_SOON": {
        "fa": (
            "⏰ اشتراکِ ویژه‌ات داره تموم می‌شه!\n"
            "📆 انقضا: {until}\n\n"
            "برای اینکه محدودیتِ دانلودت برنگرده، همین حالا با {price} ⭐ تمدید کن 👇"
        ),
        "en": (
            "⏰ Your premium is about to expire!\n"
            "📆 Expires: {until}\n\n"
            "Renew now for {price} ⭐ so your higher limits don't lapse 👇"
        ),
    },
    "REMAINING_TODAY": {
        "fa": "📊 سهمیه‌ی امروزت: {remaining} دانلودِ دیگه باقی مونده.",
        "en": "📊 Today's quota: {remaining} download(s) remaining.",
    },
}


class _Lang:
    """پروکسیِ زبان: ``tr = t.L(lang); tr.START`` رشته‌ی همون زبان رو می‌ده."""

    __slots__ = ("_lang",)

    def __init__(self, lang: str | None) -> None:
        object.__setattr__(self, "_lang", normalize_lang(lang))

    def __getattr__(self, name: str):
        try:
            val = _S[name]
        except KeyError as exc:  # نامِ ناشناخته → مثلِ خطای attribute معمولی
            raise AttributeError(name) from exc
        if isinstance(val, dict):
            return val.get(self._lang) or val.get(DEFAULT_LANG)
        return val


def L(lang: str | None) -> _Lang:
    """پروکسیِ زبان رو می‌سازه؛ ``lang`` نامعتبر به پیش‌فرض برمی‌گرده."""
    return _Lang(lang)


def __getattr__(name: str):
    """تورِ امن (PEP 562): ``t.NAME`` بدونِ L، نسخه‌ی زبانِ پیش‌فرض (فارسی) رو می‌ده.

    این باعث می‌شه هر جایی که زبان هنوز نخ نشده، به‌جای کرش، فارسیِ فعلی نشون داده بشه.
    """
    try:
        val = _S[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    if isinstance(val, dict):
        return val.get(DEFAULT_LANG)
    return val


def caption_block(caption: str | None) -> str:
    """کپشن ریلز رو برای نمایش آماده می‌کنه."""
    caption = (caption or "").strip()
    return caption if caption else _S["NO_CAPTION"]
