"""دریافت لینک، دانلود با چند روش، ارسال ویدیو+کپشن و پاکسازی فایل موقت."""
from __future__ import annotations

import asyncio
import html
import logging
import time

from telegram import InputMediaPhoto, InputMediaVideo, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from InstaDownloadBot import database
from InstaDownloadBot import localization as t
from InstaDownloadBot.handlers.start import gate_passed, _user_lang
from InstaDownloadBot.keyboards import (
    alert_admin_keyboard,
    auth_fail_keyboard,
    buy_vip_keyboard,
    reel_keyboard,
)
from InstaDownloadBot.services import instagram
from InstaDownloadBot.services.instagram import (
    AuthRequiredError,
    DownloadError,
    FileTooLargeError,
)
from InstaDownloadBot.utils.files import is_video, temp_workdir
from InstaDownloadBot.utils import ratelimit, song, video
from InstaDownloadBot import config

logger = logging.getLogger(__name__)

_CAPTION_LIMIT = 1024
_MESSAGE_LIMIT = 4096

# حداکثر هر ۳۰ دقیقه یک‌بار به ادمین درباره‌ی مشکل کوکی هشدار بده تا اسپم نشه
_COOKIE_ALERT_COOLDOWN = 30 * 60
_last_cookie_alert_at = 0.0


async def _alert_admins_cookie(context, url: str | None = None) -> None:
    """هشدارِ سوختنِ کوکی رو به تاپیکِ «هشدارها»ی گروه می‌فرسته (با محدودیت زمانی).

    اگه گروه/تاپیک تنظیم نشده باشه، مثلِ قبل دایرکت به همه‌ی ادمین‌ها می‌ره. لینکِ ناموفق
    (در صورتِ وجود) داخلِ <code> و همراهِ دکمه‌ی «باز کردنِ لینک» برای بررسی ضمیمه می‌شه.
    """
    global _last_cookie_alert_at
    now = time.monotonic()
    if _last_cookie_alert_at and now - _last_cookie_alert_at < _COOKIE_ALERT_COOLDOWN:
        return
    _last_cookie_alert_at = now

    text = t.COOKIE_EXPIRED_ADMIN
    markup = None
    if url:
        text += t.ALERT_FAILING_LINK.format(url=html.escape(url))
        markup = alert_admin_keyboard(url)

    group_id = await database.get_support_group_id()
    thread = await database.get_support_thread_alerts()
    if group_id and thread:
        try:
            await context.bot.send_message(
                int(group_id),
                text,
                message_thread_id=thread,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            return
        except Exception:  # noqa: BLE001 - اگه ارسال به گروه نشد، می‌افتیم رو دایرکتِ ادمین
            logger.exception("Could not send cookie alert to alerts topic; falling back to DMs")

    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
        except Exception:  # noqa: BLE001 - اگه ادمین ربات رو start نکرده باشه مهم نیست
            logger.warning("Could not alert admin %s about cookie issue", admin_id)


def _chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


async def _notify_remaining(message, user_id: int, lang: str) -> None:
    """بعد از مصرفِ سهمیه، تعدادِ دانلودِ باقی‌مانده‌ی امروز رو یادآوری می‌کنه.

    فقط وقتی سقف محدوده (limit>0) نشون داده می‌شه؛ کاربرِ نامحدود (سقفِ ۰) چیزی نمی‌گیره.
    خطاهاش بی‌صدا نادیده گرفته می‌شن تا یادآوری هیچ‌وقت جریانِ اصلیِ دانلود رو خراب نکنه.
    """
    try:
        quota = await database.get_quota(
            user_id, config.FREE_DAILY_LIMIT, config.VIP_DAILY_LIMIT
        )
        if quota.limit > 0:
            tr = t.L(lang)
            await message.reply_text(tr.REMAINING_TODAY.format(remaining=quota.remaining))
    except Exception:  # noqa: BLE001 - یادآوریِ سهمیه نباید چیزی رو بشکنه
        pass


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    await database.upsert_user(user.id, user.first_name, user.username)
    lang = await _user_lang(user.id)
    tr = t.L(lang)

    url = instagram.find_instagram_url(message.text)
    if not url:
        await message.reply_text(tr.INVALID_LINK)
        return

    is_admin_user = config.is_admin(user.id)

    # ضدفلود: فاصله‌ی حداقلی بین درخواست‌های هر کاربر (ادمین‌ها معاف‌اند)
    if not is_admin_user:
        wait = ratelimit.cooldown.remaining(user.id)
        if wait > 0:
            await message.reply_text(tr.COOLDOWN_WAIT.format(seconds=int(wait) + 1))
            return

    # سهمیه‌ی روزانه (ادمین‌ها نامحدودن). اگه سهمیه پر شده همین‌جا متوقف می‌شیم؛
    # برای کاربرِ عادی دکمه‌ی خریدِ VIP هم نشون داده می‌شه.
    if not is_admin_user:
        quota = await database.get_quota(
            user.id, config.FREE_DAILY_LIMIT, config.VIP_DAILY_LIMIT
        )
        if quota.exhausted:
            if quota.is_vip:
                await message.reply_text(tr.QUOTA_REACHED_VIP.format(limit=quota.limit))
            else:
                price = await database.get_vip_price()
                await message.reply_text(
                    tr.QUOTA_REACHED_FREE.format(
                        limit=quota.limit, vip_limit=config.VIP_DAILY_LIMIT
                    ),
                    reply_markup=buy_vip_keyboard(price, lang),
                )
            return

    if not await gate_passed(update, context, lang):
        return

    # کش: اگه این ریلز قبلاً گرفته شده، مستقیم از تلگرام دوباره بفرست
    # (نه اینستا، نه پروکسی، نه دانلود) — صفر بایت مصرف و آنی
    shortcode = instagram.extract_shortcode(url)
    if shortcode:
        cached = await database.get_cached_media(shortcode)
        if cached:
            ratelimit.cooldown.mark(user.id)
            try:
                await _send_cached(context, message.chat_id, cached, shortcode, lang)
                if not is_admin_user:
                    await database.consume_quota(user.id)
                    await _notify_remaining(message, user.id, lang)
                logger.info("Served %s from file_id cache", shortcode)
                return
            except Exception:  # noqa: BLE001 - file_id باطل شده؛ می‌ریم دانلود مجدد
                logger.info("Cached send failed for %s; re-downloading", shortcode)

    # سقف دانلودهای هم‌زمان تا منابع هاست زیر فشار نره
    if not ratelimit.gate.try_acquire():
        await message.reply_text(tr.TOO_BUSY)
        return

    # درخواست پذیرفته شد؛ از همین لحظه کول‌داونِ کاربر شروع می‌شه
    ratelimit.cooldown.mark(user.id)

    status = await message.reply_text(tr.PROCESSING)
    try:
        with temp_workdir() as workdir:
            await context.bot.send_chat_action(message.chat_id, ChatAction.UPLOAD_VIDEO)
            result = await instagram.download(url, workdir)

            # هر آیتمِ آلبوم هم باید زیرِ سقفِ حجم باشه (پستِ تک‌فایلی فقط یک آیتم داره)
            if any(
                item.file_path.stat().st_size > config.MAX_FILE_BYTES
                for item in result.items
            ):
                await status.edit_text(tr.FILE_TOO_LARGE)
                return

            file_id, media_type, has_audio, media_items = await _send_media(
                context, message.chat_id, result, shortcode, lang
            )
            if not is_admin_user:
                await database.consume_quota(user.id)
                await _notify_remaining(message, user.id, lang)
            # file_id رو کش کن تا دفعه‌ی بعد همین ریلز بدون لمسِ اینستا فرستاده شه
            if shortcode and file_id:
                caption = (result.caption or "").strip() or None
                await database.cache_media(
                    shortcode, file_id, media_type, caption, result.author,
                    has_audio=int(has_audio), media_items=media_items,
                )
        await status.delete()
    except FileTooLargeError:
        await status.edit_text(tr.FILE_TOO_LARGE)
    except AuthRequiredError as exc:
        logger.warning("Auth/cookie failure for %s: %s", url, exc)
        await status.edit_text(
            tr.DOWNLOAD_FAILED_AUTH, reply_markup=auth_fail_keyboard(url, lang)
        )
        await _alert_admins_cookie(context, url)
    except DownloadError as exc:
        logger.info("Download failed for %s: %s", url, exc)
        await status.edit_text(tr.DOWNLOAD_FAILED)
    except Exception:  # noqa: BLE001 - هر خطای پیش‌بینی‌نشده نباید ربات رو بخوابونه
        logger.exception("Unexpected error while processing %s", url)
        await status.edit_text(tr.DOWNLOAD_FAILED)
    finally:
        ratelimit.gate.release()


def _build_caption(caption: str | None, footer: str) -> tuple[str, str | None]:
    """کپشن نهاییِ روی فایل + سرریز رو می‌سازه (خروجی HTML، parse_mode=HTML لازمه).

    تبلیغ ربات (footer) همیشه باید روی خود فایل باشه تا موقع فوروارد همراهش بمونه.
    اگه کپشن+footer از حد تلگرام بیشتر شد، فقط footer روی فایل می‌مونه و کپشن جدا می‌ره.

    کپشنِ کاربر html-escape می‌شه (مثلاً «<3» پارس رو خراب نکنه)، ولی footer که خودش
    تگِ <a> داره خام می‌مونه. سرریز به‌صورتِ متنِ خام (بدون escape) جدا می‌ره چون با
    parse_mode فرستاده نمی‌شه.
    """
    raw = (caption or "").strip()
    safe = html.escape(raw)
    combined = f"{safe}\n\n{footer}" if safe else footer
    if len(combined) <= _CAPTION_LIMIT:
        return combined, None
    return footer, raw


async def _send_overflow(context, chat_id: int, overflow: str | None) -> None:
    if overflow:
        for chunk in _chunks(overflow, _MESSAGE_LIMIT):
            await context.bot.send_message(chat_id, chunk)


def _build_footer(
    context, shortcode: str | None, author: str | None, media_type: str,
    lang: str = "fa",
) -> str:
    """فوترِ پای فایل: اعتبار به سازنده‌ی اصلی + لینکِ منبع + برندینگِ ربات."""
    tr = t.L(lang)
    lines: list[str] = []
    if shortcode:
        url = instagram.permalink(shortcode, media_type)
        if author:
            # یوزرنیم خودش لینکِ ریلز می‌شه؛ html.escape چون داخلِ تگِ <a> می‌شینه
            lines.append(tr.SOURCE_AUTHOR.format(url=url, author=html.escape(author)))
        else:
            lines.append(tr.SOURCE_LINK.format(url=url))
    lines.append(tr.CAPTION_FOOTER.format(username=context.bot.username))
    return "\n".join(lines)


async def _send_album(
    context, chat_id: int, result: instagram.MediaResult, shortcode: str | None,
    lang: str = "fa",
) -> list[tuple[str, bool]]:
    """آیتم‌های آلبوم/کاروسل رو در یک media_group می‌فرسته و [(file_id, is_video), ...] می‌ده.

    تلگرام برای media_group حداکثر ۱۰ آیتم و «بدونِ دکمه» قبول می‌کنه؛ کپشن (footer)
    فقط روی اولین آیتم می‌شینه. permalink با نوعِ «photo» ساخته می‌شه تا به /p/ بره.
    """
    footer = _build_footer(context, shortcode, result.author, "photo", lang)
    media_caption, overflow = _build_caption(result.caption, footer)

    items = result.items[:10]
    handles = []
    try:
        media_group = []
        for i, item in enumerate(items):
            fh = open(item.file_path, "rb")
            handles.append(fh)
            cap = media_caption if i == 0 else None
            pm = ParseMode.HTML if i == 0 else None
            if item.is_video:
                media_group.append(
                    InputMediaVideo(media=fh, caption=cap, parse_mode=pm, supports_streaming=True)
                )
            else:
                media_group.append(InputMediaPhoto(media=fh, caption=cap, parse_mode=pm))
        msgs = await context.bot.send_media_group(
            chat_id, media=media_group, read_timeout=120, write_timeout=120
        )
    finally:
        for fh in handles:
            fh.close()

    media_items: list[tuple[str, bool]] = []
    for msg in msgs:
        if msg.video:
            media_items.append((msg.video.file_id, True))
        elif msg.photo:
            media_items.append((msg.photo[-1].file_id, False))

    await _send_overflow(context, chat_id, overflow)
    return media_items


async def _send_media(
    context, chat_id: int, result: instagram.MediaResult, shortcode: str | None,
    lang: str = "fa",
) -> tuple[str, str, bool, list[tuple[str, bool]] | None]:
    """مدیا رو از فایل می‌فرسته و (file_id, media_type, has_audio, media_items) برمی‌گردونه.

    برای پستِ آلبومی/کاروسلی همه‌ی آیتم‌ها در یک media_group می‌رن و media_items پر
    برمی‌گرده (تا کش بشه)؛ آلبوم‌ها دکمه و پروبِ صدا ندارن. برای پستِ تک‌فایلی،
    media_items برابرِ None و رفتار مثلِ قبله.
    """
    if result.is_album:
        media_items = await _send_album(context, chat_id, result, shortcode, lang)
        first_id = media_items[0][0] if media_items else ""
        return first_id, "photo", False, media_items

    media_type = "video" if is_video(result.file_path) else "photo"

    # آیا این ویدیو اصلاً صدا داره؟ (دکمه‌ی صدا فقط برای ویدیوهای صدادار میاد — نسخه‌ی تمیز).
    # پروبِ ffmpeg همگام/CPU-bound است؛ توی thread جدا می‌زنیمش که لوپ بلاک نشه. اگه ffmpeg
    # نباشه has_audio_stream خودش False می‌ده و دکمه‌ی صدا (که بی‌فایده‌ست) هم نمیاد.
    has_audio = False
    if media_type == "video":
        has_audio = await asyncio.to_thread(video.has_audio_stream, result.file_path)

    footer = _build_footer(context, shortcode, result.author, media_type, lang)
    media_caption, overflow = _build_caption(result.caption, footer)

    with open(result.file_path, "rb") as fh:
        if media_type == "video":
            # دکمه‌های زیرِ ویدیو (نسخه‌ی کم‌حجم + دریافتِ موزیک/صدا) فقط وقتی shortcode
            # داریم (برای پیدا کردنِ file_id از کش هنگام پردازش). دکمه‌ی موزیک خودش نامِ
            # آهنگ رو هم شناسایی می‌کنه، پس دکمه‌ی جداگانه‌ی آهنگ لازم نیست.
            markup = reel_keyboard(shortcode, has_audio, lang) if shortcode else None
            msg = await context.bot.send_video(
                chat_id,
                video=fh,
                caption=media_caption,
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
                filename=result.file_path.name,
                reply_markup=markup,
                read_timeout=120,
                write_timeout=120,
            )
            file_id = msg.video.file_id
        else:
            msg = await context.bot.send_photo(
                chat_id,
                photo=fh,
                caption=media_caption,
                parse_mode=ParseMode.HTML,
                write_timeout=120,
            )
            file_id = msg.photo[-1].file_id

    # کپشن بلندتر از حد مجاز رو جداگانه و تکه‌تکه می‌فرستیم
    await _send_overflow(context, chat_id, overflow)
    return file_id, media_type, has_audio, None


async def _send_cached(
    context, chat_id: int, cached: "database.CachedMedia", shortcode: str | None,
    lang: str = "fa",
) -> None:
    """نسخه‌ی کش‌شده رو فقط با file_id دوباره می‌فرسته (بدون آپلودِ دوباره)."""
    # آلبوم/کاروسل: از روی media_itemsِ کش‌شده دوباره media_group می‌سازیم (بدونِ دکمه).
    if cached.media_items:
        footer = _build_footer(context, shortcode, cached.author, "photo", lang)
        media_caption, overflow = _build_caption(cached.caption, footer)
        media_group = []
        for i, (fid, is_vid) in enumerate(cached.media_items[:10]):
            cap = media_caption if i == 0 else None
            pm = ParseMode.HTML if i == 0 else None
            if is_vid:
                media_group.append(
                    InputMediaVideo(media=fid, caption=cap, parse_mode=pm, supports_streaming=True)
                )
            else:
                media_group.append(InputMediaPhoto(media=fid, caption=cap, parse_mode=pm))
        await context.bot.send_media_group(chat_id, media=media_group)
        await _send_overflow(context, chat_id, overflow)
        return

    footer = _build_footer(context, shortcode, cached.author, cached.media_type, lang)
    media_caption, overflow = _build_caption(cached.caption, footer)

    if cached.media_type == "video":
        # has_audio: ۱=صدادار→دکمه بیاد، ۰=بی‌صدا→دکمه نیاد، None=قدیمی/نامعلوم→دکمه بیاد
        # (محتاطانه؛ اگه واقعاً بی‌صدا بود، موقعِ کلیک خودش has_audio رو ۰ می‌کنه و بعداً حذف می‌شه)
        show_audio = cached.has_audio != 0
        markup = reel_keyboard(shortcode, show_audio, lang) if shortcode else None
        await context.bot.send_video(
            chat_id,
            video=cached.file_id,
            caption=media_caption,
            parse_mode=ParseMode.HTML,
            supports_streaming=True,
            reply_markup=markup,
        )
    else:
        await context.bot.send_photo(
            chat_id,
            photo=cached.file_id,
            caption=media_caption,
            parse_mode=ParseMode.HTML,
        )

    await _send_overflow(context, chat_id, overflow)


async def handle_compress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی «نسخه‌ی کم‌حجم»: همون ویدیو رو از تلگرام برمی‌داره، با ffmpeg کوچیک
    می‌کنه و دوباره می‌فرسته — بدونِ لمسِ دوباره‌ی اینستاگرام.
    """
    query = update.callback_query
    lang = await _user_lang(query.from_user.id)
    tr = t.L(lang)
    data = query.data or ""
    shortcode = data.split(":", 1)[1] if ":" in data else ""

    cached = await database.get_cached_media(shortcode) if shortcode else None
    if not cached or cached.media_type != "video":
        await query.answer(tr.COMPRESS_NOT_FOUND, show_alert=True)
        return

    user_id = query.from_user.id
    is_admin_user = config.is_admin(user_id)

    # سهمیه‌ی روزانه‌ی نسخه‌ی کم‌حجم (ادمین‌ها نامحدودن). همین اول چک می‌شه تا بیخود
    # اسلاتِ پردازش گرفته نشه. فقط روی تحویلِ موفق مصرف می‌شه.
    if not is_admin_user:
        cquota = await database.get_compress_quota(
            user_id, config.FREE_COMPRESS_DAILY_LIMIT, config.VIP_COMPRESS_DAILY_LIMIT
        )
        if cquota.exhausted:
            if cquota.is_vip:
                await query.answer(
                    tr.COMPRESS_QUOTA_VIP.format(limit=cquota.limit), show_alert=True
                )
            else:
                await query.answer()
                price = await database.get_vip_price()
                await context.bot.send_message(
                    query.message.chat_id,
                    tr.COMPRESS_QUOTA_FREE.format(
                        limit=cquota.limit, vip_limit=config.VIP_COMPRESS_DAILY_LIMIT
                    ),
                    reply_markup=buy_vip_keyboard(price, lang),
                )
            return

    footer = _build_footer(context, shortcode, cached.author, "video", lang)

    # اگه نسخه‌ی فشرده قبلاً ساخته شده، آنی و بدونِ پردازشِ دوباره بفرست
    if cached.compressed_file_id:
        await query.answer()
        try:
            await context.bot.send_video(
                query.message.chat_id,
                video=cached.compressed_file_id,
                caption=footer,
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
            )
        except Exception:  # noqa: BLE001 - file_id باطل شده؛ از نو می‌سازیم
            logger.info("Cached compressed send failed for %s; rebuilding", shortcode)
        else:
            if not is_admin_user:
                await database.consume_compress_quota(user_id)
            return

    if not video.ffmpeg_available():
        await query.answer(tr.COMPRESS_UNAVAILABLE, show_alert=True)
        return

    # از همون سقفِ دانلودهای هم‌زمان استفاده می‌کنیم تا CPUِ هاست زیرِ فشار نره
    if not ratelimit.gate.try_acquire():
        await query.answer(tr.COMPRESS_BUSY, show_alert=True)
        return

    await query.answer(tr.COMPRESS_WORKING)
    chat_id = query.message.chat_id
    try:
        with temp_workdir() as workdir:
            # تلگرام برای ربات‌ها فقط دانلودِ فایلِ تا ۲۰ مگ رو اجازه می‌ده
            try:
                tg_file = await context.bot.get_file(cached.file_id)
            except BadRequest as exc:
                if "too big" in str(exc).lower():
                    await context.bot.send_message(chat_id, tr.COMPRESS_TOO_LARGE)
                    return
                raise

            src = workdir / "src.mp4"
            await tg_file.download_to_drive(custom_path=str(src))

            dst = workdir / "small.mp4"
            await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)
            await asyncio.to_thread(video.compress_video, src, dst)

            with open(dst, "rb") as fh:
                msg = await context.bot.send_video(
                    chat_id,
                    video=fh,
                    caption=footer,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                    filename="compressed.mp4",
                    read_timeout=120,
                    write_timeout=120,
                )
            # نسخه‌ی فشرده رو کش کن تا دفعه‌ی بعد بدونِ پردازش فرستاده بشه
            if msg.video and shortcode:
                await database.set_compressed_file_id(shortcode, msg.video.file_id)
            # تحویل موفق بود؛ یک واحد از سهمیه‌ی نسخه‌ی کم‌حجم مصرف می‌شه (ادمین معاف)
            if not is_admin_user:
                await database.consume_compress_quota(user_id)
    except Exception:  # noqa: BLE001 - هیچ خطایی نباید ربات رو بخوابونه
        logger.exception("Compression failed for %s", shortcode)
        await context.bot.send_message(chat_id, tr.COMPRESS_FAILED)
    finally:
        ratelimit.gate.release()


def _audio_send_meta(
    song_name: str | None, footer: str, lang: str = "fa"
) -> tuple[str, str]:
    """عنوانِ متادیتا + کپشنِ نهاییِ فایلِ صوتی رو می‌سازه.

    ``song_name``: ``None``=هنوز شناسایی نشده، ``""``=امتحان شد ولی آهنگی نبود،
    متنِ غیرخالی=نامِ آهنگ («عنوان — خواننده»).

    اگه آهنگ شناخته شده باشه، عنوانِ فایل (که توی پلیرِ تلگرام دیده می‌شه) خودِ نامِ
    آهنگ می‌شه و یه خط هم بالای کپشن اضافه می‌شه؛ وگرنه عنوانِ پیش‌فرض و فقط footer.
    کپشن با ``parse_mode=HTML`` می‌ره، پس نامِ آهنگ html-escape می‌شه ولی footer (که
    خودش تگِ <a> داره) خام می‌مونه.
    """
    tr = t.L(lang)
    if song_name:
        caption = f"{tr.AUDIO_SONG_LINE.format(name=html.escape(song_name))}\n\n{footer}"
        return song_name, caption
    return tr.AUDIO_TITLE, footer


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی «دریافت موزیک / صدا»: صدای همون ویدیو رو با ffmpeg جدا و به‌صورتِ MP3
    می‌فرسته و — اگه روی سرور ممکن باشه — نامِ آهنگ رو هم (مثلِ Shazam) شناسایی و توی
    عنوان/کپشنِ همون فایل می‌نویسه. همه‌چی با همین یه دکمه و یه سهمیه (سهمیه‌ی صدا)
    انجام می‌شه؛ بدونِ لمسِ دوباره‌ی اینستاگرام.
    """
    query = update.callback_query
    lang = await _user_lang(query.from_user.id)
    tr = t.L(lang)
    data = query.data or ""
    shortcode = data.split(":", 1)[1] if ":" in data else ""

    cached = await database.get_cached_media(shortcode) if shortcode else None
    if not cached or cached.media_type != "video":
        await query.answer(tr.AUDIO_NOT_FOUND, show_alert=True)
        return

    user_id = query.from_user.id
    is_admin_user = config.is_admin(user_id)

    # سهمیه‌ی روزانه‌ی گرفتنِ صدا (ادمین‌ها نامحدودن). همین اول چک می‌شه تا بیخود اسلاتِ
    # پردازش گرفته نشه. فقط روی تحویلِ موفق مصرف می‌شه (نه روی ریلزِ بی‌صدا).
    if not is_admin_user:
        aquota = await database.get_audio_quota(
            user_id, config.FREE_AUDIO_DAILY_LIMIT, config.VIP_AUDIO_DAILY_LIMIT
        )
        if aquota.exhausted:
            if aquota.is_vip:
                await query.answer(
                    tr.AUDIO_QUOTA_VIP.format(limit=aquota.limit), show_alert=True
                )
            else:
                await query.answer()
                price = await database.get_vip_price()
                await context.bot.send_message(
                    query.message.chat_id,
                    tr.AUDIO_QUOTA_FREE.format(
                        limit=aquota.limit, vip_limit=config.VIP_AUDIO_DAILY_LIMIT
                    ),
                    reply_markup=buy_vip_keyboard(price, lang),
                )
            return

    footer = _build_footer(context, shortcode, cached.author, "video", lang)
    performer = (cached.author or "").lstrip("@").strip() or None
    chat_id = query.message.chat_id

    # نامِ آهنگی که از قبل کش شده: None=هنوز امتحان نشده، ""=امتحان شد/نبود، متن=هست.
    song_name = cached.song_name
    # فقط وقتی هنوز امتحان نشده و قابلیتِ شناسایی روی سرور فعاله سراغِ شناسایی می‌ریم.
    want_song = (
        song_name is None
        and song.recognition_available()
        and video.ffmpeg_available()
    )

    # مسیرِ سریع: صدا از قبل کش شده و چیزِ تازه‌ای برای شناسایی نمونده → آنی بفرست.
    if cached.audio_file_id and not want_song:
        await query.answer()
        title, caption = _audio_send_meta(song_name, footer, lang)
        try:
            await context.bot.send_audio(
                chat_id,
                audio=cached.audio_file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                title=title,
                performer=performer,
            )
        except Exception:  # noqa: BLE001 - file_id باطل شده؛ از نو می‌سازیم (می‌افتیم پایین)
            logger.info("Cached audio send failed for %s; rebuilding", shortcode)
        else:
            if not is_admin_user:
                await database.consume_audio_quota(user_id)
            return

    if not video.ffmpeg_available():
        await query.answer(tr.AUDIO_UNAVAILABLE, show_alert=True)
        return

    # از همون سقفِ دانلودهای هم‌زمان استفاده می‌کنیم تا CPUِ هاست زیرِ فشار نره
    if not ratelimit.gate.try_acquire():
        await query.answer(tr.AUDIO_BUSY, show_alert=True)
        return

    await query.answer(tr.AUDIO_WORKING)
    try:
        with temp_workdir() as workdir:
            # تلگرام برای ربات‌ها فقط دانلودِ فایلِ تا ۲۰ مگ رو اجازه می‌ده
            try:
                tg_file = await context.bot.get_file(cached.file_id)
            except BadRequest as exc:
                if "too big" in str(exc).lower():
                    await context.bot.send_message(chat_id, tr.AUDIO_TOO_LARGE)
                    return
                raise

            src = workdir / "src.mp4"
            await tg_file.download_to_drive(custom_path=str(src))

            # ۱) شناساییِ آهنگ (اگه لازم بود) — بهترین‌تلاش: شکستش فقط یعنی نامِ آهنگ
            #    نمیاد، ولی فرستادنِ خودِ فایلِ صوتی ادامه پیدا می‌کنه. ریلزِ بی‌صدا
            #    NoAudioError می‌ده که بیرون هندل می‌شه (هم برای آهنگ هم برای خودِ صدا).
            if want_song:
                try:
                    snippet = workdir / "snippet.wav"
                    await asyncio.to_thread(
                        video.extract_audio_snippet, src, snippet, 20
                    )
                    found = await song.identify_song(snippet)
                except video.NoAudioError:
                    raise  # ریلزِ بی‌صدا → پایین هندل می‌شه
                except Exception:  # noqa: BLE001 - خطای شبکه/موقت؛ بعداً دوباره امتحان می‌شه
                    logger.info(
                        "Song recognition failed for %s; sending audio without name",
                        shortcode,
                    )
                else:
                    if found is not None:
                        song_name = found
                        if shortcode:
                            await database.set_song_name(shortcode, found)

            title, caption = _audio_send_meta(song_name, footer, lang)

            # ۲) خودِ فایلِ صوتی: اگه قبلاً کش شده با همون file_id بفرست (بدونِ استخراجِ
            #    دوباره)؛ اگه نبود یا file_id باطل بود، استخراج و آپلود کن. عنوان/کپشن در
            #    هر دو حالت نامِ آهنگ رو نشون می‌ده.
            sent = False
            if cached.audio_file_id:
                try:
                    await context.bot.send_audio(
                        chat_id,
                        audio=cached.audio_file_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        title=title,
                        performer=performer,
                    )
                    sent = True
                except Exception:  # noqa: BLE001 - file_id باطل شده؛ از نو می‌سازیم
                    logger.info("Cached audio send failed for %s; rebuilding", shortcode)

            if not sent:
                dst = workdir / "audio.mp3"
                await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VOICE)
                await asyncio.to_thread(video.extract_audio, src, dst)
                with open(dst, "rb") as fh:
                    msg = await context.bot.send_audio(
                        chat_id,
                        audio=fh,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        title=title,
                        performer=performer,
                        filename=f"{shortcode}.mp3",
                        read_timeout=120,
                        write_timeout=120,
                    )
                # نسخه‌ی صوتی رو کش کن تا دفعه‌ی بعد بدونِ پردازش فرستاده بشه
                if msg.audio and shortcode:
                    await database.set_audio_file_id(shortcode, msg.audio.file_id)

            # تحویل موفق بود؛ یک واحد از سهمیه‌ی صدا مصرف می‌شه (ادمین معاف)
            if not is_admin_user:
                await database.consume_audio_quota(user_id)
    except video.NoAudioError:
        # ریلزِ بی‌صدا — این یه خطا نیست، فقط به کاربر خبر می‌دیم (سهمیه مصرف نمی‌شه).
        await context.bot.send_message(chat_id, tr.AUDIO_NO_TRACK)
        # حالا که مطمئن شدیم بی‌صداست، علامتش می‌زنیم تا دفعه‌ی بعد نه دکمه‌ی صدا بیاد و
        # نه سراغِ شناساییِ آهنگ بره.
        if shortcode:
            await database.set_has_audio(shortcode, 0)
            await database.set_song_name(shortcode, "")
    except Exception:  # noqa: BLE001 - هیچ خطایی نباید ربات رو بخوابونه
        logger.exception("Audio extraction failed for %s", shortcode)
        await context.bot.send_message(chat_id, tr.AUDIO_FAILED)
    finally:
        ratelimit.gate.release()
