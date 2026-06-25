"""لایه دیتابیس SQLite (async) — کاربران و کانال‌های اجباری."""
from __future__ import annotations

import json
from dataclasses import dataclass

import aiosqlite

from InstaDownloadBot import config

_DB = str(config.DB_PATH)


@dataclass
class Channel:
    chat_id: int
    title: str
    username: str | None
    invite_link: str | None
    expires_at: str | None = None  # None یعنی موندگاریِ نامحدود (همیشگی)

    @property
    def url(self) -> str | None:
        """لینکی که توی دکمه «عضویت» نشون داده می‌شه."""
        if self.username:
            return f"https://t.me/{self.username}"
        return self.invite_link


async def init_db() -> None:
    async with aiosqlite.connect(_DB) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_name TEXT,
                username   TEXT,
                joined_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS required_channels (
                chat_id     INTEGER PRIMARY KEY,
                title       TEXT,
                username    TEXT,
                invite_link TEXT,
                added_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # کشِ file_id تلگرام: ریلزی که یه‌بار دانلود و فرستاده شده، دفعه‌ی بعد مستقیم از
        # تلگرام دوباره فرستاده می‌شه (نه اینستا، نه پروکسی) — صفر بایت مصرف و خیلی سریع.
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS media_cache (
                shortcode  TEXT PRIMARY KEY,
                file_id    TEXT NOT NULL,
                media_type TEXT NOT NULL,
                caption    TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # جدولِ تنظیماتِ زمانِ اجرا (کلید/مقدار) — قیمت و مدتِ VIP که ادمین عوضشون می‌کنه
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        # تیکت‌های پشتیبانی: هر پیامِ کاربر به پشتیبانی یه تیکت می‌شه. کارتِ تیکت توی
        # تاپیکِ گروهِ پشتیبانی فرستاده می‌شه و ادمین با ریپلای به همون کارت جواب می‌ده؛
        # group_msg_id همون message_id کارت توی گروهه که از روش کاربرِ مقصد پیدا می‌شه.
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                user_name     TEXT,
                username      TEXT,
                message       TEXT,
                group_chat_id INTEGER,
                group_msg_id  INTEGER,
                status        TEXT DEFAULT 'open',
                created_at    TEXT DEFAULT (datetime('now')),
                answered_at   TEXT
            )
            """
        )
        # ردِّ آخرین پیامِ همگانی (/broadcast): برای هر کاربر، message_id پیامی که براش
        # فرستاده شده تا /undobroadcast بتونه همون‌ها رو پاک کنه (delete_message تا ۴۸ ساعت).
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS last_broadcast (
                user_id    INTEGER,
                message_id INTEGER
            )
            """
        )
        # کوکی‌های sessionidِ «زنده»: ادمین با /addcookie اضافه‌شون می‌کنه و download() هر بار
        # تازه می‌خونتشون، پس بدونِ خاموش/روشنِ ربات بلافاصله اعمال می‌شن (مکملِ کوکی‌های .env).
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS live_cookies (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                sessionid TEXT UNIQUE NOT NULL,
                added_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # پروکسی‌های رزیدنشالِ «زنده»: یک استخر (pool) که ادمین با /addproxy بهش اضافه می‌کنه؛
        # download() بینشون می‌چرخه تا سهمیه‌ی یک پروکسی زود ته نکشه. اینجا هم بدونِ ری‌استارت.
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS live_proxies (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy    TEXT UNIQUE NOT NULL,
                added_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # پرداخت‌های موفقِ Telegram Stars: charge_id رو نگه می‌داریم تا ادمین بتونه با
        # /refund بازپرداخت کنه (refund_star_payment هم user_id و هم charge_id می‌خواد).
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS star_payments (
                charge_id   TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                amount      INTEGER,
                days        INTEGER,
                created_at  TEXT DEFAULT (datetime('now')),
                refunded_at TEXT
            )
            """
        )
        # مهاجرت‌ها: ستون‌های جدید روی دیتابیس‌های قدیمی با ALTER اضافه می‌شن
        # (CREATE TABLE IF NOT EXISTS ستونِ جدید به جدولِ موجود اضافه نمی‌کنه).
        await _ensure_column(db, "media_cache", "compressed_file_id", "TEXT")
        await _ensure_column(db, "media_cache", "audio_file_id", "TEXT")
        await _ensure_column(db, "media_cache", "author", "TEXT")
        # آیا ویدیو صدا داره؟ ۱=داره، ۰=نداره، NULL=نامعلوم (ردیف‌های قدیمیِ قبل از این قابلیت)
        await _ensure_column(db, "media_cache", "has_audio", "INTEGER")
        # نتیجه‌ی شناساییِ آهنگ: NULL=هنوز امتحان نشده، ""=امتحان شد و چیزی نبود، متن=«عنوان — خواننده»
        await _ensure_column(db, "media_cache", "song_name", "TEXT")
        # آلبوم/کاروسل: لیستِ JSON از [[file_id, is_video(۱/۰)], ...] برای پست‌های چندتایی.
        # NULL یعنی پستِ تک‌فایلیِ معمولی (همون file_id بالا استفاده می‌شه).
        await _ensure_column(db, "media_cache", "media_items", "TEXT")
        await _ensure_column(db, "users", "terms_seen_at", "TEXT")
        # VIP و سهمیه‌ی روزانه
        await _ensure_column(db, "users", "vip_until", "TEXT")        # انقضای VIP (UTC)؛ NULL=عادی
        await _ensure_column(db, "users", "quota_date", "TEXT")       # روزی که شمارنده مالِ اونه
        await _ensure_column(db, "users", "quota_used", "INTEGER DEFAULT 0")
        # سهمیه‌ی جداگانه‌ی گرفتنِ صدا (مستقل از سهمیه‌ی دانلود)
        await _ensure_column(db, "users", "audio_quota_date", "TEXT")
        await _ensure_column(db, "users", "audio_quota_used", "INTEGER DEFAULT 0")
        # سهمیه‌ی جداگانه‌ی ساختنِ «نسخه‌ی کم‌حجم» (مستقل از دانلود و صدا)
        await _ensure_column(db, "users", "compress_quota_date", "TEXT")
        await _ensure_column(db, "users", "compress_quota_used", "INTEGER DEFAULT 0")
        # زبانِ کاربر ("fa"/"en")؛ NULL/خالی یعنی هنوز انتخاب نشده → بارِ اول ازش می‌پرسیم
        await _ensure_column(db, "users", "lang", "TEXT")
        # فعال/غیرفعال: کاربری که ربات رو بلاک یا حساب رو پاک کرده، هنگامِ broadcast غیرفعال
        # علامت می‌خوره تا دفعه‌ی بعد وقتِ ارسال سرش هدر نره. ۱=فعال (پیش‌فرض)، ۰=بلاک‌شده.
        # با هر تعاملِ بعدیِ کاربر دوباره فعال می‌شه (در upsert_user).
        await _ensure_column(db, "users", "active", "INTEGER DEFAULT 1")
        # آخرین باری که یادآوریِ انقضای VIP براش رفت؛ با هر تمدیدِ VIP این NULL می‌شه تا
        # نزدیکِ انقضای جدید دوباره (و فقط یک‌بار) یادآوری بشه.
        await _ensure_column(db, "users", "vip_reminded_at", "TEXT")
        # کانال‌های اجباری: تاریخِ انقضای موندگاری (UTC). NULL = نامحدود (همیشگی).
        # بعد از این تاریخ کانال دیگه برای جوینِ اجباری اعمال نمی‌شه و توسطِ cleanup حذف می‌شه.
        await _ensure_column(db, "required_channels", "expires_at", "TEXT")

        # پاک‌سازیِ کشِ منقضی‌شده تا ربات آرشیوِ دائمیِ محتوای دیگران نشه
        if config.CACHE_TTL_DAYS > 0:
            await db.execute(
                "DELETE FROM media_cache WHERE created_at < datetime('now', ?)",
                (f"-{config.CACHE_TTL_DAYS} days",),
            )
        await db.commit()


async def _ensure_column(db, table: str, column: str, decl: str) -> None:
    """اگه ستون در جدول نبود اضافه‌اش می‌کنه (مهاجرتِ امن و idempotent)."""
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        existing = {row[1] for row in await cur.fetchall()}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


# ---------- کاربران ----------
async def upsert_user(user_id: int, first_name: str | None, username: str | None) -> None:
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, first_name, username) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET first_name=excluded.first_name,
                                               username=excluded.username,
                                               active=1
            """,
            (user_id, first_name, username),
        )
        await db.commit()


async def count_users() -> int:
    async with aiosqlite.connect(_DB) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def should_show_terms(user_id: int) -> bool:
    """فقط بارِ اول True برمی‌گردونه و کاربر رو «دیده» علامت می‌زنه (سلبِ مسئولیتِ یک‌بار)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT terms_seen_at FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row and row[0]:
            return False
        await db.execute(
            "UPDATE users SET terms_seen_at = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return True


# ---------- زبانِ کاربر ----------
async def get_user_lang(user_id: int) -> str | None:
    """زبانِ ذخیره‌شده‌ی کاربر ("fa"/"en")؛ None یعنی هنوز انتخاب نکرده (بارِ اول)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT lang FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row and row[0] else None


async def set_user_lang(user_id: int, lang: str) -> None:
    """زبانِ کاربر رو ذخیره می‌کنه (اگه کاربر نبود، می‌سازتش)."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "INSERT INTO users (user_id, lang) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang",
            (user_id, lang),
        )
        await db.commit()


async def get_all_user_ids() -> list[int]:
    """آیدیِ کاربرهای فعال (برای پیامِ همگانی) — بلاک‌کرده‌ها (active=0) رد می‌شن."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE active IS NOT 0"
        ) as cur:
            rows = await cur.fetchall()
    return [int(r[0]) for r in rows]


async def deactivate_user(user_id: int) -> None:
    """کاربری که ربات رو بلاک کرده (در broadcast خطای Forbidden داد) رو غیرفعال علامت می‌زنه.
    با هر تعاملِ بعدیِ خودش (upsert_user) دوباره فعال می‌شه."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE users SET active = 0 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


# ---------- پیامِ همگانی (/broadcast و /undobroadcast) ----------
async def clear_last_broadcast() -> None:
    """ردِّ پیامِ همگانیِ قبلی رو پاک می‌کنه (قبل از شروعِ یک broadcast جدید یا بعد از undo)."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute("DELETE FROM last_broadcast")
        await db.commit()


async def add_broadcast_record(user_id: int, message_id: int) -> None:
    """message_id پیامی که در broadcast برای یک کاربر فرستاده شد رو ذخیره می‌کنه (برای undo)."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "INSERT INTO last_broadcast (user_id, message_id) VALUES (?, ?)",
            (user_id, message_id),
        )
        await db.commit()


async def get_last_broadcast() -> list[tuple[int, int]]:
    """لیستِ (user_id, message_id) پیام‌های آخرین broadcast — برای حذف در /undobroadcast."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT user_id, message_id FROM last_broadcast"
        ) as cur:
            rows = await cur.fetchall()
    return [(int(r[0]), int(r[1])) for r in rows]


# ---------- VIP و سهمیه‌ی روزانه ----------
@dataclass
class Quota:
    """وضعیتِ VIP و سهمیه‌ی امروزِ یک کاربر."""
    is_vip: bool
    used: int          # تعدادِ دانلودِ مصرف‌شده‌ی امروز
    limit: int         # سقفِ امروز (بسته به VIP/عادی)
    vip_until: str | None  # انقضای VIP اگه VIP باشه، وگرنه None

    @property
    def remaining(self) -> int:
        if self.limit <= 0:
            return 10**9  # ۰ یعنی نامحدود
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.limit > 0 and self.used >= self.limit


async def get_quota(user_id: int, free_limit: int, vip_limit: int) -> Quota:
    """وضعیتِ VIP + مصرفِ امروز رو یک‌جا می‌خونه (اگه روز عوض شده باشه مصرف صفر حساب می‌شه)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT vip_until, "
            "CASE WHEN quota_date = date('now') THEN quota_used ELSE 0 END, "
            "(vip_until IS NOT NULL AND vip_until > datetime('now')) "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return Quota(False, 0, free_limit, None)
    vip = bool(row[2])
    used = int(row[1] or 0)
    limit = vip_limit if vip else free_limit
    return Quota(vip, used, limit, row[0] if vip else None)


async def is_vip(user_id: int) -> bool:
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT 1 FROM users WHERE user_id = ? AND vip_until IS NOT NULL "
            "AND vip_until > datetime('now')",
            (user_id,),
        ) as cur:
            return await cur.fetchone() is not None


async def consume_quota(user_id: int) -> None:
    """یک واحد از سهمیه‌ی امروز مصرف می‌کنه؛ اگه روز عوض شده باشه از ۱ شروع می‌کنه (ریستِ خودکار)."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE users SET "
            "quota_used = CASE WHEN quota_date = date('now') THEN quota_used + 1 ELSE 1 END, "
            "quota_date = date('now') "
            "WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_audio_quota(user_id: int, free_limit: int, vip_limit: int) -> Quota:
    """سهمیه‌ی «گرفتنِ صدا»ی امروز رو می‌خونه (جدا از سهمیه‌ی دانلود).

    اگه روز عوض شده باشه مصرف صفر حساب می‌شه (ریستِ خودکار نصفه‌شبِ UTC).
    """
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT vip_until, "
            "CASE WHEN audio_quota_date = date('now') THEN audio_quota_used ELSE 0 END, "
            "(vip_until IS NOT NULL AND vip_until > datetime('now')) "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return Quota(False, 0, free_limit, None)
    vip = bool(row[2])
    used = int(row[1] or 0)
    limit = vip_limit if vip else free_limit
    return Quota(vip, used, limit, row[0] if vip else None)


async def consume_audio_quota(user_id: int) -> None:
    """یک واحد از سهمیه‌ی صدای امروز مصرف می‌کنه؛ اگه روز عوض شده از ۱ شروع می‌کنه."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE users SET "
            "audio_quota_used = CASE WHEN audio_quota_date = date('now') "
            "THEN audio_quota_used + 1 ELSE 1 END, "
            "audio_quota_date = date('now') "
            "WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_compress_quota(user_id: int, free_limit: int, vip_limit: int) -> Quota:
    """سهمیه‌ی «نسخه‌ی کم‌حجم»ی امروز رو می‌خونه (جدا از دانلود و صدا).

    اگه روز عوض شده باشه مصرف صفر حساب می‌شه (ریستِ خودکار نصفه‌شبِ UTC).
    """
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT vip_until, "
            "CASE WHEN compress_quota_date = date('now') THEN compress_quota_used ELSE 0 END, "
            "(vip_until IS NOT NULL AND vip_until > datetime('now')) "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return Quota(False, 0, free_limit, None)
    vip = bool(row[2])
    used = int(row[1] or 0)
    limit = vip_limit if vip else free_limit
    return Quota(vip, used, limit, row[0] if vip else None)


async def consume_compress_quota(user_id: int) -> None:
    """یک واحد از سهمیه‌ی نسخه‌ی کم‌حجمِ امروز مصرف می‌کنه؛ اگه روز عوض شده از ۱ شروع می‌کنه."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE users SET "
            "compress_quota_used = CASE WHEN compress_quota_date = date('now') "
            "THEN compress_quota_used + 1 ELSE 1 END, "
            "compress_quota_date = date('now') "
            "WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def grant_vip(user_id: int, days: int) -> str:
    """VIP رو به‌اندازه‌ی ``days`` روز تمدید می‌کنه و انقضای جدید رو برمی‌گردونه.

    اگه کاربر هنوز VIP فعال داره، از همون انقضا ادامه می‌ده (تمدید)، وگرنه از همین حالا.
    """
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING",
            (user_id,),
        )
        await db.execute(
            "UPDATE users SET vip_until = datetime("
            "CASE WHEN vip_until IS NOT NULL AND vip_until > datetime('now') "
            "THEN vip_until ELSE datetime('now') END, ?), "
            "vip_reminded_at = NULL "
            "WHERE user_id = ?",
            (f"+{int(days)} days", user_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT vip_until FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row and row[0] else ""


async def revoke_vip(user_id: int) -> bool:
    """VIP رو لغو می‌کنه. True اگه واقعاً VIP فعال داشت، وگرنه False."""
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(
            "UPDATE users SET vip_until = NULL WHERE user_id = ? "
            "AND vip_until IS NOT NULL AND vip_until > datetime('now')",
            (user_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def count_vip() -> int:
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE vip_until IS NOT NULL "
            "AND vip_until > datetime('now')"
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def get_vips_needing_reminder(within_days: int) -> list[tuple[int, str]]:
    """VIPهایی که انقضاشون تا ``within_days`` روزِ آینده‌ست و هنوز یادآوری نگرفتن.

    خروجی: لیستِ (user_id, vip_until). شرطِ ``vip_reminded_at IS NULL`` تضمین می‌کنه
    هر دوره فقط یک‌بار یادآوری بره؛ ``grant_vip`` این فیلد رو بعدِ تمدید NULL می‌کنه.
    """
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT user_id, vip_until FROM users "
            "WHERE vip_until IS NOT NULL "
            "AND vip_until > datetime('now') "
            "AND vip_until <= datetime('now', ?) "
            "AND vip_reminded_at IS NULL",
            (f"+{int(within_days)} days",),
        ) as cur:
            rows = await cur.fetchall()
    return [(int(r[0]), r[1]) for r in rows]


async def mark_vip_reminded(user_id: int) -> None:
    """ثبت می‌کنه که یادآوریِ انقضای VIP برای این کاربر فرستاده شد (تا تکراری نشه)."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE users SET vip_reminded_at = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def find_user_by_username(username: str) -> int | None:
    """آیدیِ عددیِ کاربر رو از روی یوزرنیم (بدونِ @) پیدا می‌کنه؛ اگه نبود None."""
    uname = (username or "").lstrip("@").strip()
    if not uname:
        return None
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE username = ? COLLATE NOCASE", (uname,)
        ) as cur:
            row = await cur.fetchone()
    return int(row[0]) if row else None


@dataclass
class UserRow:
    user_id: int
    first_name: str | None
    username: str | None
    is_vip: bool
    vip_until: str | None


async def list_users(limit: int = 50) -> list[UserRow]:
    """کاربرها رو برمی‌گردونه؛ اول VIPها بعد تازه‌واردترها (برای پنلِ ادمین)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT user_id, first_name, username, vip_until, "
            "(vip_until IS NOT NULL AND vip_until > datetime('now')) AS v "
            "FROM users ORDER BY v DESC, joined_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [UserRow(r[0], r[1], r[2], bool(r[4]), r[3]) for r in rows]


# ---------- تنظیماتِ زمانِ اجرا (settings) ----------
async def get_setting(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(_DB) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


# ---------- منابعِ زنده‌ی دانلود: کوکی‌ها و پروکسی‌ها (بدونِ ری‌استارت) ----------
# این‌ها مکملِ مقادیرِ .env هستن؛ download() هر بار ادغامِ «‏env + دیتابیس» رو می‌خونه،
# پس هر افزودن/حذفی که ادمین انجام بده بلافاصله روی دانلودِ بعدی اثر می‌ذاره.
async def add_cookie(sessionid: str) -> bool:
    """یک کوکی sessionidِ زنده اضافه می‌کنه. False اگه خالی یا تکراری بود."""
    sid = (sessionid or "").strip()
    if not sid:
        return False
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT 1 FROM live_cookies WHERE sessionid = ?", (sid,)
        ) as cur:
            if await cur.fetchone():
                return False
        await db.execute("INSERT INTO live_cookies (sessionid) VALUES (?)", (sid,))
        await db.commit()
        return True


async def remove_cookie(identifier: str | int) -> bool:
    """با id (عددی) یا مقدارِ کاملِ کوکی، یک کوکیِ زنده رو حذف می‌کنه."""
    raw = str(identifier or "").strip()
    if not raw:
        return False
    async with aiosqlite.connect(_DB) as db:
        if raw.isdigit():
            cur = await db.execute("DELETE FROM live_cookies WHERE id = ?", (int(raw),))
        else:
            cur = await db.execute("DELETE FROM live_cookies WHERE sessionid = ?", (raw,))
        await db.commit()
        return cur.rowcount > 0


async def list_cookies() -> list[tuple[int, str]]:
    """لیستِ (id, sessionid) کوکی‌های زنده — برای نمایش/حذف در پنلِ ادمین."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT id, sessionid FROM live_cookies ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
    return [(int(r[0]), r[1]) for r in rows]


async def get_all_cookies() -> list[str]:
    """کوکی‌های .env و زنده رو ادغام‌شده و بدونِ تکرار برمی‌گردونه (منبعِ دانلود)."""
    out: list[str] = []
    seen: set[str] = set()
    db_cookies = [v for _, v in await list_cookies()]
    for sid in list(config.INSTAGRAM_SESSIONIDS) + db_cookies:
        s = (sid or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


async def add_proxy(proxy: str) -> bool:
    """یک پروکسیِ رزیدنشالِ زنده به استخر اضافه می‌کنه. False اگه خالی یا تکراری بود."""
    p = (proxy or "").strip()
    if not p:
        return False
    async with aiosqlite.connect(_DB) as db:
        async with db.execute("SELECT 1 FROM live_proxies WHERE proxy = ?", (p,)) as cur:
            if await cur.fetchone():
                return False
        await db.execute("INSERT INTO live_proxies (proxy) VALUES (?)", (p,))
        await db.commit()
        return True


async def remove_proxy(identifier: str | int) -> bool:
    """با id (عددی) یا مقدارِ کاملِ پروکسی، یک پروکسیِ زنده رو حذف می‌کنه."""
    raw = str(identifier or "").strip()
    if not raw:
        return False
    async with aiosqlite.connect(_DB) as db:
        if raw.isdigit():
            cur = await db.execute("DELETE FROM live_proxies WHERE id = ?", (int(raw),))
        else:
            cur = await db.execute("DELETE FROM live_proxies WHERE proxy = ?", (raw,))
        await db.commit()
        return cur.rowcount > 0


async def list_proxies() -> list[tuple[int, str]]:
    """لیستِ (id, proxy) پروکسی‌های زنده — برای نمایش/حذف در پنلِ ادمین."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute("SELECT id, proxy FROM live_proxies ORDER BY id") as cur:
            rows = await cur.fetchall()
    return [(int(r[0]), r[1]) for r in rows]


async def get_all_proxies() -> list[str]:
    """پروکسیِ .env و پروکسی‌های زنده رو ادغام‌شده و بدونِ تکرار برمی‌گردونه (استخرِ چرخش)."""
    out: list[str] = []
    seen: set[str] = set()
    db_proxies = [v for _, v in await list_proxies()]
    env_proxies = [config.INSTAGRAM_PROXY] if config.INSTAGRAM_PROXY else []
    for p in env_proxies + db_proxies:
        pp = (p or "").strip()
        if pp and pp not in seen:
            seen.add(pp)
            out.append(pp)
    return out


# ---------- گروهِ اطلاع‌رسانی/پشتیبانی (آیدیِ گروه + تاپیک‌ها، زنده در settings) ----------
# ربات این‌ها رو با گرفتنِ «لینکِ تاپیک» از ادمین پر می‌کنه؛ نیازی به دست‌کاریِ .env نیست.
async def get_support_group_id() -> str:
    """آیدیِ گروهِ سوپرگروهِ پشتیبانی/اطلاع‌رسانی (مثلِ -1001234567890)؛ خالی یعنی تنظیم‌نشده."""
    return (await get_setting("support_group_id")) or ""


async def set_support_group_id(value: str) -> None:
    await set_setting("support_group_id", (value or "").strip())


async def _get_thread(key: str) -> int:
    val = (await get_setting(key)) or ""
    return int(val) if val.lstrip("-").isdigit() else 0


async def get_support_thread_tickets() -> int:
    """آیدیِ تاپیکِ «تیکت‌های پشتیبانی»؛ ۰ یعنی تنظیم‌نشده."""
    return await _get_thread("support_thread_tickets")


async def set_support_thread_tickets(thread_id: int) -> None:
    await set_setting("support_thread_tickets", str(int(thread_id)))


async def get_support_thread_alerts() -> int:
    """آیدیِ تاپیکِ «هشدارها/اطلاع‌رسانیِ سیستمی»؛ ۰ یعنی تنظیم‌نشده."""
    return await _get_thread("support_thread_alerts")


async def set_support_thread_alerts(thread_id: int) -> None:
    await set_setting("support_thread_alerts", str(int(thread_id)))


async def clear_support_group() -> None:
    """همه‌ی تنظیماتِ گروهِ پشتیبانی/اطلاع‌رسانی رو پاک می‌کنه."""
    for key in ("support_group_id", "support_thread_tickets", "support_thread_alerts"):
        await set_setting(key, "")


# ---------- تیکت‌های پشتیبانی ----------
@dataclass
class SupportTicket:
    id: int
    user_id: int
    status: str
    message: str


async def count_open_tickets_for_user(user_id: int) -> int:
    """تعدادِ تیکت‌های بازِ (بی‌پاسخِ) یک کاربر — برای جلوگیری از اسپمِ پشتیبانی."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE user_id = ? AND status = 'open'",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    return int(row[0]) if row else 0


async def create_ticket(
    user_id: int, user_name: str | None, username: str | None, message: str
) -> int:
    """یک تیکتِ جدید می‌سازه و آیدیِ عددیش رو برمی‌گردونه."""
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(
            "INSERT INTO support_tickets (user_id, user_name, username, message) "
            "VALUES (?, ?, ?, ?)",
            (user_id, user_name, username, message),
        )
        await db.commit()
        return int(cur.lastrowid)


async def set_ticket_group_msg(ticket_id: int, group_chat_id: int, group_msg_id: int) -> None:
    """message_id کارتِ تیکت توی گروه رو ذخیره می‌کنه تا با ریپلایِ ادمین پیداش کنیم."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE support_tickets SET group_chat_id = ?, group_msg_id = ? WHERE id = ?",
            (group_chat_id, group_msg_id, ticket_id),
        )
        await db.commit()


async def get_ticket_by_group_msg(group_msg_id: int) -> SupportTicket | None:
    """از روی message_id کارتِ تیکت در گروه، صاحبِ تیکت رو پیدا می‌کنه (برای ریلیِ جواب)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT id, user_id, status, message FROM support_tickets "
            "WHERE group_msg_id = ? ORDER BY id DESC LIMIT 1",
            (group_msg_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return SupportTicket(id=int(row[0]), user_id=int(row[1]), status=row[2], message=row[3] or "")


async def mark_ticket_answered(ticket_id: int) -> None:
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE support_tickets SET status = 'answered', "
            "answered_at = datetime('now') WHERE id = ?",
            (ticket_id,),
        )
        await db.commit()


async def get_vip_price() -> int:
    """قیمتِ زنده‌ی VIP (Stars)؛ اگه ادمین تنظیم نکرده باشه دیفالتِ config."""
    val = await get_setting("vip_price_stars")
    try:
        return int(val) if val is not None else config.VIP_PRICE_STARS
    except (TypeError, ValueError):
        return config.VIP_PRICE_STARS


async def set_vip_price(stars: int) -> None:
    await set_setting("vip_price_stars", str(int(stars)))


async def get_vip_duration() -> int:
    """مدتِ زنده‌ی اشتراکِ VIP (روز)؛ اگه تنظیم نشده دیفالتِ config."""
    val = await get_setting("vip_duration_days")
    try:
        return int(val) if val is not None else config.VIP_DURATION_DAYS
    except (TypeError, ValueError):
        return config.VIP_DURATION_DAYS


async def set_vip_duration(days: int) -> None:
    await set_setting("vip_duration_days", str(int(days)))


# ---------- پرداخت‌های Telegram Stars (برای /refund) ----------
@dataclass
class Payment:
    charge_id: str
    user_id: int
    amount: int
    days: int
    created_at: str | None
    refunded_at: str | None


async def record_payment(charge_id: str, user_id: int, amount: int, days: int) -> None:
    """یک پرداختِ موفق رو ثبت می‌کنه تا بعداً قابلِ بازپرداخت باشه (تکراری نادیده گرفته می‌شه)."""
    cid = (charge_id or "").strip()
    if not cid:
        return
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "INSERT INTO star_payments (charge_id, user_id, amount, days) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(charge_id) DO NOTHING",
            (cid, user_id, int(amount or 0), int(days or 0)),
        )
        await db.commit()


def _payment_from_row(row) -> Payment | None:
    if not row:
        return None
    return Payment(
        charge_id=row[0], user_id=int(row[1]), amount=int(row[2] or 0),
        days=int(row[3] or 0), created_at=row[4], refunded_at=row[5],
    )


async def get_payment(charge_id: str) -> Payment | None:
    """یک پرداخت رو با charge_id برمی‌گردونه (یا None)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT charge_id, user_id, amount, days, created_at, refunded_at "
            "FROM star_payments WHERE charge_id = ?",
            ((charge_id or "").strip(),),
        ) as cur:
            row = await cur.fetchone()
    return _payment_from_row(row)


async def get_latest_refundable_payment(user_id: int) -> Payment | None:
    """آخرین پرداختِ بازپرداخت‌نشده‌ی یک کاربر — تا ادمین بدونِ دونستنِ charge_id رفاند کنه."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT charge_id, user_id, amount, days, created_at, refunded_at "
            "FROM star_payments WHERE user_id = ? AND refunded_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    return _payment_from_row(row)


async def mark_payment_refunded(charge_id: str) -> bool:
    """پرداخت رو «بازپرداخت‌شده» علامت می‌زنه. True اگه ردیفِ بازپرداخت‌نشده‌ای بود."""
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(
            "UPDATE star_payments SET refunded_at = datetime('now') "
            "WHERE charge_id = ? AND refunded_at IS NULL",
            ((charge_id or "").strip(),),
        )
        await db.commit()
        return cur.rowcount > 0


# ---------- کانال‌های اجباری ----------
async def add_channel(
    chat_id: int,
    title: str,
    username: str | None,
    invite_link: str | None,
    days: int = 0,
) -> bool:
    """کانالِ اجباری رو اضافه (یا اگه از قبل بود، عنوان/لینک/موندگاریش رو به‌روز) می‌کنه.

    ``days`` مدتِ موندگاریه: ``0`` یعنی نامحدود (expires_at = NULL)، عددِ مثبت یعنی بعد از
    این تعداد روز منقضی می‌شه. خروجی: True اگه کانالِ تازه‌ای اضافه شد، False اگه موردِ
    موجود فقط به‌روز/تمدید شد.
    """
    if days and days > 0:
        expires_sql, extra = "datetime('now', ?)", (f"+{int(days)} days",)
    else:
        expires_sql, extra = "NULL", ()
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT 1 FROM required_channels WHERE chat_id = ?", (chat_id,)
        ) as cur:
            exists = await cur.fetchone() is not None
        if exists:
            await db.execute(
                f"UPDATE required_channels SET title = ?, username = ?, "
                f"invite_link = ?, expires_at = {expires_sql} WHERE chat_id = ?",
                (title, username, invite_link, *extra, chat_id),
            )
        else:
            await db.execute(
                f"INSERT INTO required_channels "
                f"(chat_id, title, username, invite_link, expires_at) "
                f"VALUES (?, ?, ?, ?, {expires_sql})",
                (chat_id, title, username, invite_link, *extra),
            )
        await db.commit()
        return not exists


async def remove_channel(chat_id: int) -> bool:
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(
            "DELETE FROM required_channels WHERE chat_id = ?", (chat_id,)
        )
        await db.commit()
        return cur.rowcount > 0


# فقط کانال‌هایی که هنوز منقضی نشدن (expires_at NULL یا در آینده) برای جوینِ اجباری معتبرن.
_CHANNEL_ACTIVE = "(expires_at IS NULL OR expires_at > datetime('now'))"


async def get_channels() -> list[Channel]:
    """کانال‌های اجباریِ فعال (منقضی‌نشده) رو برمی‌گردونه."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            "SELECT chat_id, title, username, invite_link, expires_at "
            f"FROM required_channels WHERE {_CHANNEL_ACTIVE} ORDER BY added_at"
        ) as cur:
            rows = await cur.fetchall()
    return [Channel(r[0], r[1], r[2], r[3], r[4]) for r in rows]


async def count_channels() -> int:
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(
            f"SELECT COUNT(*) FROM required_channels WHERE {_CHANNEL_ACTIVE}"
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def purge_expired_channels() -> int:
    """کانال‌هایی که موندگاریشون تموم شده رو حذف می‌کنه (توسطِ کارِ دوره‌ای صدا زده می‌شه)."""
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(
            "DELETE FROM required_channels "
            "WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')"
        )
        await db.commit()
        return cur.rowcount


# ---------- کشِ مدیا (file_id تلگرام) ----------
@dataclass
class CachedMedia:
    file_id: str
    media_type: str  # "video" یا "photo"
    caption: str | None
    author: str | None = None              # یوزرنیمِ سازنده‌ی اصلی (اعتباردهی)
    # file_idِ نسخه‌ی فشرده (کم‌حجم) اگه قبلاً ساخته شده باشه؛ وگرنه None
    compressed_file_id: str | None = None
    # file_idِ نسخه‌ی صوتی (MP3) اگه قبلاً ساخته شده باشه؛ وگرنه None
    audio_file_id: str | None = None
    # آیا ویدیو صدا داره؟ ۱=داره، ۰=نداره، None=نامعلوم (ردیف‌های قدیمی)
    has_audio: int | None = None
    # نتیجه‌ی شناساییِ آهنگ: None=امتحان‌نشده، ""=امتحان‌شده/بی‌نتیجه، متن=«عنوان — خواننده»
    song_name: str | None = None
    # آلبوم/کاروسل: لیستِ [(file_id, is_video), ...] برای پست‌های چندتایی؛ None=تک‌فایلی
    media_items: list[tuple[str, bool]] | None = None


async def get_cached_media(shortcode: str) -> CachedMedia | None:
    """نسخه‌ی کش‌شده رو برمی‌گردونه؛ اگه از TTL گذشته باشه انگار وجود نداره (None)."""
    query = (
        "SELECT file_id, media_type, caption, author, compressed_file_id, "
        "audio_file_id, has_audio, song_name, media_items "
        "FROM media_cache WHERE shortcode = ?"
    )
    params: list = [shortcode]
    if config.CACHE_TTL_DAYS > 0:
        query += " AND created_at >= datetime('now', ?)"
        params.append(f"-{config.CACHE_TTL_DAYS} days")
    async with aiosqlite.connect(_DB) as db:
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return CachedMedia(
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7],
        _parse_media_items(row[8]),
    )


def _parse_media_items(raw: str | None) -> list[tuple[str, bool]] | None:
    """رشته‌ی JSONِ آلبوم را به ``[(file_id, is_video), ...]`` تبدیل می‌کند (یا None)."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    items: list[tuple[str, bool]] = []
    for entry in data or []:
        try:
            items.append((str(entry[0]), bool(entry[1])))
        except (IndexError, TypeError):
            continue
    return items or None


async def set_compressed_file_id(shortcode: str, file_id: str) -> None:
    """file_idِ نسخه‌ی فشرده رو روی همون ردیفِ کش ذخیره می‌کنه تا دفعه‌ی بعد آنی فرستاده بشه."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE media_cache SET compressed_file_id = ? WHERE shortcode = ?",
            (file_id, shortcode),
        )
        await db.commit()


async def set_audio_file_id(shortcode: str, file_id: str) -> None:
    """file_idِ نسخه‌ی صوتی (MP3) رو روی همون ردیفِ کش ذخیره می‌کنه تا دفعه‌ی بعد آنی فرستاده بشه."""
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE media_cache SET audio_file_id = ? WHERE shortcode = ?",
            (file_id, shortcode),
        )
        await db.commit()


async def set_has_audio(shortcode: str, has_audio: int) -> None:
    """وضعیتِ «صدا داره/نداره» رو روی ردیفِ کش به‌روز می‌کنه.

    وقتی موقعِ کلیک معلوم شد ریلزِ قدیمی‌ای واقعاً بی‌صداست، با ست کردنِ ۰ باعث می‌شیم
    دفعه‌ی بعد دکمه‌ی صدا اصلاً نشون داده نشه (خودترمیمی برای کش‌های قدیمی).
    """
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE media_cache SET has_audio = ? WHERE shortcode = ?",
            (has_audio, shortcode),
        )
        await db.commit()


async def set_song_name(shortcode: str, song_name: str) -> None:
    """نتیجه‌ی شناساییِ آهنگ رو روی ردیفِ کش ذخیره می‌کنه تا دفعه‌ی بعد آنی جواب بده.

    ``""`` یعنی «امتحان شد ولی آهنگی پیدا نشد» (تا بی‌خود دوباره Shazam نزنیم)،
    و متنِ غیرخالی یعنی نامِ آهنگِ شناخته‌شده.
    """
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            "UPDATE media_cache SET song_name = ? WHERE shortcode = ?",
            (song_name, shortcode),
        )
        await db.commit()


async def cache_media(
    shortcode: str,
    file_id: str,
    media_type: str,
    caption: str | None,
    author: str | None = None,
    has_audio: int | None = None,
    media_items: list[tuple[str, bool]] | None = None,
) -> None:
    """file_id یه مدیا رو با کلیدِ shortcode ذخیره (یا به‌روز) می‌کنه.

    موقعِ به‌روزرسانی، ``created_at`` هم ریست می‌شه تا ساعتِ TTL از نو بشمره.
    ``media_items`` برای پست‌های آلبومی/کاروسلی‌ست؛ به‌صورتِ JSON ذخیره می‌شه.
    """
    items_json = (
        json.dumps([[fid, 1 if isv else 0] for fid, isv in media_items])
        if media_items
        else None
    )
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            """
            INSERT INTO media_cache
                (shortcode, file_id, media_type, caption, author, has_audio, media_items)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shortcode) DO UPDATE SET file_id=excluded.file_id,
                                                 media_type=excluded.media_type,
                                                 caption=excluded.caption,
                                                 author=excluded.author,
                                                 has_audio=excluded.has_audio,
                                                 media_items=excluded.media_items,
                                                 created_at=datetime('now')
            """,
            (shortcode, file_id, media_type, caption, author, has_audio, items_json),
        )
        await db.commit()


# ---------- نگه‌داری/سلامتِ دیتابیس (برای /backup، /health و کارهای دوره‌ای) ----------
async def checkpoint_wal() -> None:
    """فایلِ WAL رو توی فایلِ اصلیِ دیتابیس ادغام و خالی می‌کنه (TRUNCATE).

    قبل از گرفتنِ بکاپ صدا زده می‌شه تا فایلِ bot.db کامل و به‌روز باشه و آخرین
    تغییراتِ توی WAL هم داخلش بیاد.
    """
    async with aiosqlite.connect(_DB) as db:
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await db.commit()


async def count_cache() -> int:
    """تعدادِ ردیف‌های کشِ مدیا (برای نمای /health)."""
    async with aiosqlite.connect(_DB) as db:
        async with db.execute("SELECT COUNT(*) FROM media_cache") as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def purge_expired_cache() -> int:
    """ردیف‌های کشِ منقضی‌شده (قدیمی‌تر از CACHE_TTL_DAYS) رو پاک می‌کنه و تعدادشون رو برمی‌گردونه.

    اگه CACHE_TTL_DAYS صفر باشه (کش بی‌انقضا) هیچ کاری نمی‌کنه و ۰ برمی‌گردونه.
    """
    if config.CACHE_TTL_DAYS <= 0:
        return 0
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(
            "DELETE FROM media_cache WHERE created_at < datetime('now', ?)",
            (f"-{config.CACHE_TTL_DAYS} days",),
        )
        await db.commit()
        return cur.rowcount
