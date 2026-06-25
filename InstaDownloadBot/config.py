"""بارگذاری تنظیمات از فایل .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ریشه بسته (پوشه InstaDownloadBot)
BASE_DIR = Path(__file__).resolve().parent

# .env کنار همین فایل قرار داره
load_dotenv(BASE_DIR / ".env")


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    return ids


def _resolve_path(raw: str, default: str) -> Path:
    """مسیر نسبی رو نسبت به ریشه بسته حساب می‌کنه تا مستقل از محل اجرا باشه."""
    value = _clean(raw) or default
    p = Path(value)
    return p if p.is_absolute() else (BASE_DIR / p)


BOT_TOKEN: str = _clean(os.getenv("BOT_TOKEN"))
ADMIN_IDS: set[int] = _parse_admin_ids(_clean(os.getenv("ADMIN_IDS")))

DOWNLOAD_DIR: Path = _resolve_path(os.getenv("DOWNLOAD_DIR"), "downloads")
DB_PATH: Path = _resolve_path(os.getenv("DB_PATH"), "bot.db")

try:
    MAX_FILE_MB: int = int(_clean(os.getenv("MAX_FILE_MB")) or "50")
except ValueError:
    MAX_FILE_MB = 50

MAX_FILE_BYTES: int = MAX_FILE_MB * 1024 * 1024

# ضدفلود: حداقل فاصله (ثانیه) بین دو درخواست دانلودِ هر کاربر. ۰ یعنی غیرفعال
try:
    COOLDOWN_SECONDS: int = int(_clean(os.getenv("COOLDOWN_SECONDS")) or "60")
except ValueError:
    COOLDOWN_SECONDS = 60

# سقف تعداد دانلودهای هم‌زمان روی کل ربات تا منابع هاست ته نکشه. ۰ یعنی نامحدود
try:
    MAX_CONCURRENT_DOWNLOADS: int = int(_clean(os.getenv("MAX_CONCURRENT_DOWNLOADS")) or "3")
except ValueError:
    MAX_CONCURRENT_DOWNLOADS = 3

# عمرِ کشِ مدیا (روز): ریلزهای قدیمی‌تر از این از کش پاک می‌شن تا ربات «آرشیوِ
# دائمیِ محتوای دیگران» نشه. ۰ یعنی کش هیچ‌وقت منقضی نمی‌شه.
try:
    CACHE_TTL_DAYS: int = int(_clean(os.getenv("CACHE_TTL_DAYS")) or "30")
except ValueError:
    CACHE_TTL_DAYS = 30

# سهمیه‌ی دانلودِ روزانه (نصفه‌شبِ UTC ریست می‌شه). ۰ یعنی نامحدود.
try:
    FREE_DAILY_LIMIT: int = int(_clean(os.getenv("FREE_DAILY_LIMIT")) or "10")
except ValueError:
    FREE_DAILY_LIMIT = 10
try:
    VIP_DAILY_LIMIT: int = int(_clean(os.getenv("VIP_DAILY_LIMIT")) or "50")
except ValueError:
    VIP_DAILY_LIMIT = 50

# سهمیه‌ی روزانه‌ی گرفتنِ صدا/موزیک (جدا از سهمیه‌ی دانلود؛ نصفه‌شبِ UTC ریست می‌شه).
# ۰ یعنی نامحدود.
try:
    FREE_AUDIO_DAILY_LIMIT: int = int(_clean(os.getenv("FREE_AUDIO_DAILY_LIMIT")) or "2")
except ValueError:
    FREE_AUDIO_DAILY_LIMIT = 2
try:
    VIP_AUDIO_DAILY_LIMIT: int = int(_clean(os.getenv("VIP_AUDIO_DAILY_LIMIT")) or "50")
except ValueError:
    VIP_AUDIO_DAILY_LIMIT = 50

# سهمیه‌ی روزانه‌ی ساختنِ «نسخه‌ی کم‌حجم» (جدا از دانلود و صدا؛ نصفه‌شبِ UTC ریست می‌شه).
# ۰ یعنی نامحدود.
try:
    FREE_COMPRESS_DAILY_LIMIT: int = int(_clean(os.getenv("FREE_COMPRESS_DAILY_LIMIT")) or "2")
except ValueError:
    FREE_COMPRESS_DAILY_LIMIT = 2
try:
    VIP_COMPRESS_DAILY_LIMIT: int = int(_clean(os.getenv("VIP_COMPRESS_DAILY_LIMIT")) or "10")
except ValueError:
    VIP_COMPRESS_DAILY_LIMIT = 10

# قیمت و مدتِ پیش‌فرضِ اشتراکِ VIP. این‌ها فقط «مقدارِ اولیه»‌ان؛ ادمین در زمانِ اجرا
# با /setprice و /setduration عوضشون می‌کنه و مقدارِ زنده توی دیتابیس (جدولِ settings) می‌مونه.
try:
    VIP_PRICE_STARS: int = int(_clean(os.getenv("VIP_PRICE_STARS")) or "50")
except ValueError:
    VIP_PRICE_STARS = 50
try:
    VIP_DURATION_DAYS: int = int(_clean(os.getenv("VIP_DURATION_DAYS")) or "30")
except ValueError:
    VIP_DURATION_DAYS = 30


def _parse_cookie_list(raw: str) -> list[str]:
    """چند کوکی sessionid جداشده با کاما/خط‌جدید رو به لیستِ بدون‌تکرار تبدیل می‌کنه."""
    out: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").replace("\n", ",").split(","):
        cookie = part.strip()
        if cookie and cookie not in seen:
            seen.add(cookie)
            out.append(cookie)
    return out


# می‌تونی چند کوکی رو با کاما جدا کنی تا اگه یکی ریت‌لیمیت/منقضی شد بقیه استفاده بشن.
# هم INSTAGRAM_SESSIONIDS (جمع) و هم INSTAGRAM_SESSIONID (مفرد) خونده و ادغام می‌شن.
INSTAGRAM_SESSIONIDS: list[str] = _parse_cookie_list(
    (os.getenv("INSTAGRAM_SESSIONIDS") or "") + "," + (os.getenv("INSTAGRAM_SESSIONID") or "")
)

# پروکسی residential فقط برای «مرحله‌ی استخراج لینک» استفاده می‌شه (نه دانلود خود ویدیو).
# بایت‌های سنگینِ ویدیو مستقیم از CDN اینستا و با اینترنتِ خودِ هاست دانلود می‌شن تا
# سهمیه‌ی محدودِ پروکسی نسوزه. فرمت:
#   http://user:pass@host:port   یا   socks5://user:pass@host:port
# (برای socks5 باید بسته‌ی PySocks نصب باشه: pip install "requests[socks]")
INSTAGRAM_PROXY: str = _clean(os.getenv("INSTAGRAM_PROXY"))


def validate() -> None:
    """قبل از اجرا بررسی می‌کنه که تنظیمات حیاتی پر شده باشن."""
    problems: list[str] = []
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN خالیه — توکن رو از @BotFather بگیر و در .env بذار.")
    if not ADMIN_IDS:
        problems.append("ADMIN_IDS خالیه — حداقل یک آیدی عددی ادمین لازمه.")
    if problems:
        raise SystemExit("خطا در تنظیمات:\n  - " + "\n  - ".join(problems))

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
