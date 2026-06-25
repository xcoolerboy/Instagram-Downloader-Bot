"""ساخت دکمه‌های این‌لاین و کیبوردهای ساجست (reply) — دوزبانه (فارسی/انگلیسی)."""
from __future__ import annotations

import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from InstaDownloadBot import localization as t
from InstaDownloadBot.database import Channel

CHECK_JOIN = "check_join"
NOOP = "noop"
# پیشوندِ callback_data دکمه‌ی فشرده‌سازی. به‌جای file_id بلند (که از سقفِ ۶۴ بایتِ
# تلگرام رد می‌شه) فقط shortcode رو می‌فرستیم و file_id رو از کش می‌خونیم.
COMPRESS_PREFIX = "cmp"
# پیشوندِ callback_data دکمه‌ی دریافتِ صدا (مثلِ فشرده‌سازی فقط shortcode رو می‌فرسته)
AUDIO_PREFIX = "aud"
# دکمه‌ی خریدِ اشتراکِ VIP (فاکتورِ Stars رو می‌سازه)
BUY_VIP = "buy_vip"
# دکمه‌ی این‌لاینِ «ارتباط با پشتیبانی» (زیرِ پیامِ خطای دانلود میاد)
SUPPORT_CB = "supcontact"
# پیشوندِ callback_data دکمه‌های انتخابِ زبان (setlang:fa / setlang:en)
SETLANG_PREFIX = "setlang"
# پیشوندِ callback_data دکمه‌های حذفِ منبعِ زنده (srcdel:c:<id> کوکی / srcdel:p:<id> پروکسی)
SRC_DEL_PREFIX = "srcdel"

# ---------- متنِ دکمه‌های کیبوردِ ساجست (reply) — دوزبانه ----------
# هر دکمه یک dictِ {"fa":.., "en":..}ـه. لیبل با label(BTN, lang) ساخته می‌شه و
# در هندلرها با btn_regex(BTN) (که هر دو زبان رو می‌گیره) تطبیق داده می‌شه.
BTN_HELP = {"fa": "📖 راهنما", "en": "📖 Help"}
BTN_VIP = {"fa": "💎 اشتراک ویژه", "en": "💎 Premium"}
BTN_SUPPORT = {"fa": "💬 پشتیبانی", "en": "💬 Support"}
BTN_TERMS = {"fa": "📜 شرایط استفاده", "en": "📜 Terms"}
BTN_ADMIN = {"fa": "🛠 پنل مدیریت", "en": "🛠 Admin panel"}
BTN_CANCEL = {"fa": "❌ لغو", "en": "❌ Cancel"}
BTN_SKIP = {"fa": "➖ رد کردن", "en": "➖ Skip"}
BTN_BACK = {"fa": "🔙 بازگشت", "en": "🔙 Back"}
# دکمه‌ی همیشه‌حاضرِ تغییرِ زبان
BTN_LANG = {"fa": "🌐 زبان", "en": "🌐 Language"}
# دکمه‌های منوی ادمین
BTN_ADD_CHANNEL = {"fa": "➕ افزودن کانال", "en": "➕ Add channel"}
BTN_REMOVE_CHANNEL = {"fa": "➖ حذف کانال", "en": "➖ Remove channel"}
BTN_CHANNELS = {"fa": "📋 کانال‌ها", "en": "📋 Channels"}
BTN_STATS = {"fa": "📊 آمار", "en": "📊 Stats"}
BTN_USERS = {"fa": "👥 کاربران", "en": "👥 Users"}
BTN_SET_PRICE = {"fa": "💰 قیمت اشتراک", "en": "💰 Sub price"}
BTN_SET_DURATION = {"fa": "⏳ مدت اشتراک", "en": "⏳ Sub duration"}
BTN_GROUP_HUB = {"fa": "📡 تنظیم گروه اطلاع‌رسانی", "en": "📡 Notify group setup"}
BTN_SOURCES = {"fa": "🔑 کوکی/پروکسی", "en": "🔑 Cookie/Proxy"}

# لیبلِ دکمه‌های انتخابِ زبان (خنثی: پرچم + نامِ بومی، نیازی به زبان نداره)
LANG_LABELS = {"fa": "🇮🇷 فارسی", "en": "🇬🇧 English"}


def label(btn: dict, lang: str = "fa") -> str:
    """لیبلِ یک دکمه را به زبانِ خواسته‌شده برمی‌گرداند (با تورِ امن به پیش‌فرض)."""
    return btn.get(t.normalize_lang(lang)) or btn[t.DEFAULT_LANG]


def btn_regex(btn: dict) -> str:
    """رجکسِ تطبیقِ یک دکمه برای همه‌ی زبان‌ها: ``^(فارسی|English)$``."""
    return "^(" + "|".join(re.escape(v) for v in btn.values()) + ")$"


def main_keyboard(is_admin: bool = False, lang: str = "fa") -> ReplyKeyboardMarkup:
    """کیبوردِ اصلیِ ثابتِ پایینِ صفحه برای کاربر (و ردیفِ ادمین در صورتِ ادمین‌بودن).

    دکمه‌ی «🌐 زبان» همیشه حاضره تا کاربر هر وقت خواست زبان رو عوض کنه.
    """
    rows = [
        [label(BTN_HELP, lang), label(BTN_VIP, lang)],
        [label(BTN_SUPPORT, lang), label(BTN_TERMS, lang)],
        [label(BTN_LANG, lang)],
    ]
    if is_admin:
        rows.append([label(BTN_ADMIN, lang)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_keyboard(lang: str = "fa") -> ReplyKeyboardMarkup:
    """فقط دکمه‌ی «لغو» — موقعِ گرفتنِ یک ورودی از کاربر."""
    return ReplyKeyboardMarkup([[label(BTN_CANCEL, lang)]], resize_keyboard=True)


def skip_cancel_keyboard(lang: str = "fa") -> ReplyKeyboardMarkup:
    """دکمه‌ی «رد کردن» + «لغو» — برای مرحله‌های اختیاریِ ویزاردِ تنظیمِ گروه."""
    return ReplyKeyboardMarkup(
        [[label(BTN_SKIP, lang)], [label(BTN_CANCEL, lang)]], resize_keyboard=True
    )


def admin_menu_keyboard(lang: str = "fa") -> ReplyKeyboardMarkup:
    """منوی ادمین به‌صورتِ کیبوردِ ساجست."""
    rows = [
        [label(BTN_ADD_CHANNEL, lang), label(BTN_REMOVE_CHANNEL, lang)],
        [label(BTN_CHANNELS, lang), label(BTN_USERS, lang)],
        [label(BTN_STATS, lang), label(BTN_GROUP_HUB, lang)],
        [label(BTN_SET_PRICE, lang), label(BTN_SET_DURATION, lang)],
        [label(BTN_SOURCES, lang)],
        [label(BTN_BACK, lang)],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def sources_remove_keyboard(
    cookies: list[tuple[int, str]],
    proxies: list[tuple[int, str]],
    lang: str = "fa",
) -> InlineKeyboardMarkup | None:
    """برای هر کوکی/پروکسیِ زنده یک دکمه‌ی حذف می‌سازه (لیبل‌ها از قبل ماسک شده‌ان).

    ``cookies`` و ``proxies`` لیستِ ``(id, masked_label)`` هستن. اگه هیچ‌کدوم موردی
    نداشته باشن None برمی‌گردونه (یعنی چیزی برای حذف نیست).
    """
    rows: list[list[InlineKeyboardButton]] = []
    for cid, masked in cookies:
        rows.append([InlineKeyboardButton(
            f"🗑 🍪 {masked}", callback_data=f"{SRC_DEL_PREFIX}:c:{cid}"
        )])
    for pid, masked in proxies:
        rows.append([InlineKeyboardButton(
            f"🗑 🌐 {masked}", callback_data=f"{SRC_DEL_PREFIX}:p:{pid}"
        )])
    return InlineKeyboardMarkup(rows) if rows else None


def language_inline_keyboard() -> InlineKeyboardMarkup:
    """دو دکمه‌ی این‌لاینِ انتخابِ زبان (فارسی / English) با callback_data ``setlang:xx``."""
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                LANG_LABELS["fa"], callback_data=f"{SETLANG_PREFIX}:fa"
            ),
            InlineKeyboardButton(
                LANG_LABELS["en"], callback_data=f"{SETLANG_PREFIX}:en"
            ),
        ]]
    )


def auth_fail_keyboard(url: str, lang: str = "fa") -> InlineKeyboardMarkup:
    """زیرِ پیامِ خطای دانلود: باز کردنِ لینک در اینستاگرام + ارتباط با پشتیبانی."""
    tr = t.L(lang)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(tr.OPEN_LINK_BUTTON, url=url)],
            [InlineKeyboardButton(tr.SUPPORT_INLINE_BUTTON, callback_data=SUPPORT_CB)],
        ]
    )


def alert_admin_keyboard(url: str, lang: str = "fa") -> InlineKeyboardMarkup:
    """زیرِ هشدارِ سیستمیِ ادمین: دکمه‌ی باز کردنِ لینکِ ناموفق برای بررسی."""
    tr = t.L(lang)
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(tr.OPEN_LINK_BUTTON, url=url)]]
    )


def buy_vip_keyboard(price: int, lang: str = "fa") -> InlineKeyboardMarkup:
    """دکمه‌ی شیشه‌ایِ «پرداخت با Stars» که فاکتورِ خریدِ VIP رو شروع می‌کنه."""
    tr = t.L(lang)
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            tr.VIP_BUY_BUTTON.format(price=price), callback_data=BUY_VIP
        )]]
    )


def reel_keyboard(
    shortcode: str, has_audio: bool = True, lang: str = "fa"
) -> InlineKeyboardMarkup:
    """دکمه‌های شیشه‌ایِ زیرِ هر ریلز: نسخه‌ی کم‌حجم + (در صورتِ صدا داشتن) دریافتِ موزیک/صدا.

    دکمه‌ها فقط ``shortcode`` رو می‌فرستن و file_id رو از کش می‌خونن (سقفِ ۶۴ بایتِ
    callback_data اجازه‌ی فرستادنِ file_id بلند رو نمی‌ده).
      * دکمه‌ی موزیک/صدا فقط وقتی ``has_audio`` درست باشه میاد (ویدیوی بی‌صدا → نمیاد).
        همین یه دکمه هم فایلِ صوتی رو می‌فرسته و هم — اگه روی سرور ممکن باشه — نامِ
        آهنگ رو شناسایی و توی عنوان/کپشنِ فایل می‌نویسه (شناساییِ آهنگ توی هندلر ادغام
        شده؛ دکمه‌ی جداگانه‌ی «این آهنگ چیه؟» دیگه لازم نیست).
    """
    tr = t.L(lang)
    rows = [
        [InlineKeyboardButton(
            tr.COMPRESS_BUTTON, callback_data=f"{COMPRESS_PREFIX}:{shortcode}"
        )],
    ]
    if has_audio:
        rows.append(
            [InlineKeyboardButton(
                tr.AUDIO_BUTTON, callback_data=f"{AUDIO_PREFIX}:{shortcode}"
            )]
        )
    return InlineKeyboardMarkup(rows)


def join_keyboard(channels: list[Channel], lang: str = "fa") -> InlineKeyboardMarkup:
    """برای هر کانال یک دکمه عضویت + یک دکمه «عضو شدم» می‌سازه."""
    tr = t.L(lang)
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        btn_label = f"📢 {ch.title}"
        if ch.url:
            rows.append([InlineKeyboardButton(btn_label, url=ch.url)])
        else:
            rows.append([InlineKeyboardButton(btn_label, callback_data=NOOP)])
    rows.append([InlineKeyboardButton(tr.JOIN_CHECK_BUTTON, callback_data=CHECK_JOIN)])
    return InlineKeyboardMarkup(rows)
