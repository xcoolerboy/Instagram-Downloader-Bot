"""دانلود ریلز/پست اینستاگرام با چند روش مختلف (تا به یک روش وابسته نباشیم).

ترتیب تلاش: ۱) yt-dlp  ۲) instaloader  ۳) صفحه embed
اولین روشی که موفق بشه نتیجه رو برمی‌گردونه.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from InstaDownloadBot import config, database

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_SHORTCODE_RE = re.compile(r"(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")
_URL_RE = re.compile(r"https?://(?:www\.)?instagram\.com/\S+", re.IGNORECASE)
# استوری: instagram.com/stories/<username>/<id>/  و هایلایت: instagram.com/stories/highlights/<id>/
_STORY_RE = re.compile(r"instagram\.com/stories/", re.IGNORECASE)
# استوریِ یک کاربرِ مشخص (نه هایلایت) — برای مسیرِ پشتیبانِ instaloader
_STORY_USER_RE = re.compile(r"instagram\.com/stories/([^/?#]+)/(\d+)", re.IGNORECASE)
# پسوندهای تصویری که موقعِ تشخیصِ عکس‌بودنِ آیتمِ استوری به‌کار می‌رن
_IMAGE_URL_EXTS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}


@dataclass
class MediaItem:
    """یک تک‌فایلِ مدیا (عکس یا ویدیو) — جزءِ یک پست یا یکی از آیتم‌های آلبوم."""
    file_path: Path
    is_video: bool


@dataclass
class MediaResult:
    # لیستِ آیتم‌ها: یک عنصر برای پستِ معمولی، چند عنصر برای آلبوم/کاروسل
    items: list[MediaItem]
    caption: str | None
    # یوزرنیمِ سازنده‌ی اصلیِ پست/ریلز (برای اعتباردهی توی کپشن)؛ اگه پیدا نشد None
    author: str | None = None

    @property
    def file_path(self) -> Path:
        """مسیرِ اولین آیتم — برای سازگاری با مسیرهای تک‌فایلیِ موجود."""
        return self.items[0].file_path

    @property
    def is_album(self) -> bool:
        return len(self.items) > 1


class DownloadError(Exception):
    """هیچ روشی نتونست محتوا رو دانلود کنه."""


class FileTooLargeError(DownloadError):
    """حجم فایل از حد مجاز بیشتره."""


class AuthRequiredError(DownloadError):
    """شکست به‌خاطر نیاز به لاگین/منقضی‌شدن کوکی sessionid یا ریت‌لیمیتِ اینستاگرام."""


def find_instagram_url(text: str) -> str | None:
    m = _URL_RE.search(text or "")
    return m.group(0) if m else None


def extract_shortcode(url: str) -> str | None:
    m = _SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def is_story_url(url: str) -> bool:
    """آیا این لینک استوری یا هایلایت است؟ (همیشه به کوکیِ معتبرِ لاگین نیاز دارد)."""
    return bool(_STORY_RE.search(url or ""))


def _url_ext(url: str) -> str:
    """پسوندِ فایلِ یک URL رو (بدونِ query/fragment) برمی‌گردونه؛ اگه نبود رشته‌ی خالی."""
    clean = (url or "").split("?", 1)[0].split("#", 1)[0]
    tail = clean.rpartition("/")[2]
    return tail.rpartition(".")[2].lower() if "." in tail else ""


def permalink(shortcode: str, media_type: str = "video") -> str:
    """لینکِ دائمیِ اصلِ پست/ریلز رو از روی shortcode می‌سازه (برای اعتباردهی)."""
    kind = "reel" if media_type == "video" else "p"
    return f"https://www.instagram.com/{kind}/{shortcode}/"


def _ytdlp_author(info: dict) -> str | None:
    """یوزرنیمِ سازنده رو از خروجیِ yt-dlp درمیاره (نه آیدیِ عددی)."""
    for key in ("channel", "uploader_id", "uploader"):
        val = (info.get(key) or "").strip().lstrip("@")
        if val and not val.isdigit():
            return val
    m = re.search(r"instagram\.com/([^/?#]+)", info.get("uploader_url") or "")
    return m.group(1) if m else None


# ---------- ابزارهای کمکی ----------
def _json_unescape(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except (json.JSONDecodeError, ValueError):
        return value.replace("\\u0026", "&").replace("\\/", "/")


def _proxies(proxy: str) -> dict[str, str] | None:
    """رشته‌ی پروکسی رو به دیکشنریِ موردنیازِ requests تبدیل می‌کنه (یا None اگه خالی باشه)."""
    return {"http": proxy, "https": proxy} if proxy else None


def _http_download(url: str, target: Path, sessionid: str = "", proxy: str = "") -> None:
    headers = {"User-Agent": _UA, "Referer": "https://www.instagram.com/"}
    if sessionid:
        headers["Cookie"] = f"sessionid={sessionid}"
    with requests.get(
        url, headers=headers, stream=True, timeout=30, proxies=_proxies(proxy)
    ) as resp:
        resp.raise_for_status()

        length = resp.headers.get("Content-Length")
        if length and int(length) > config.MAX_FILE_BYTES:
            raise FileTooLargeError(f"حجم {length} بایت بیشتر از حد مجازه")

        written = 0
        with open(target, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if not chunk:
                    continue
                written += len(chunk)
                if written > config.MAX_FILE_BYTES:
                    raise FileTooLargeError("حجم فایل حین دانلود از حد مجاز گذشت")
                fh.write(chunk)


def _write_netscape_cookies(workdir: Path, sessionid: str) -> Path:
    """کوکی sessionid رو به‌صورت فایل Netscape می‌نویسه.

    yt-dlp پاس‌دادن کوکی به‌صورت هدر رو منسوخ کرده و فایل کوکی رو توصیه می‌کنه؛
    این روش هم احرازِ هویت رو درست‌تر می‌کنه هم اون هشدار deprecation رو می‌بنده.
    """
    path = workdir / "cookies.txt"
    expiry = int(time.time()) + 365 * 24 * 60 * 60
    path.write_text(
        "# Netscape HTTP Cookie File\n"
        f".instagram.com\tTRUE\t/\tTRUE\t{expiry}\tsessionid\t{sessionid}\n",
        encoding="utf-8",
    )
    return path


def _download_media_bytes(url: str, target: Path, sessionid: str, proxy: str) -> None:
    """بایت‌های ویدیو رو اول «مستقیم» (بدون پروکسی) می‌گیره تا سهمیه‌ی پروکسی نسوزه.

    لینک‌های CDN اینستا معمولاً به IP قفل نیستن، پس دانلودِ مستقیم از IP هاست کار می‌کنه.
    فقط اگه استثنائاً مستقیم رد شد (مثلاً CDN به IP حساس بود)، یک‌بار از پروکسی تلاش می‌کنه.
    """
    try:
        _http_download(url, target, sessionid)
        return
    except FileTooLargeError:
        raise
    except Exception as exc:  # noqa: BLE001 - تلاش پشتیبان از مسیر پروکسی
        if not proxy:
            raise
        logger.info("Direct media download failed (%s); retrying via proxy", exc)
        _http_download(url, target, sessionid, proxy=proxy)


def _pick_progressive_url(info: dict) -> str | None:
    """از خروجی yt-dlp یه URL مستقیمِ progressive (صدا+تصویر در یک فایل) بیرون می‌کشه.

    اینطوری خودِ yt-dlp چیزی دانلود نمی‌کنه (و از پروکسی رد نمی‌شه)؛ فقط لینک رو می‌ده
    و ما بایت‌ها رو مستقیم می‌گیریم. استریم‌های جداگانه (DASH/m3u8) رد می‌شن چون
    به مرج نیاز دارن و این روش ساده‌ی تک‌فایل رو می‌خوایم.
    """

    def _is_progressive(protocol: object) -> bool:
        p = str(protocol or "")
        return p.startswith("http") and "m3u8" not in p and "dash" not in p

    direct = info.get("url")
    if direct and direct.startswith("http") and _is_progressive(info.get("protocol", "https")):
        return direct

    best: str | None = None
    best_score = -1.0
    for fmt in info.get("formats") or []:
        furl = fmt.get("url")
        if not furl or not furl.startswith("http") or not _is_progressive(fmt.get("protocol")):
            continue
        if fmt.get("vcodec") in (None, "none") or fmt.get("acodec") in (None, "none"):
            continue  # باید هم صدا داشته باشه هم تصویر
        score = float(fmt.get("height") or 0) * 10000 + float(fmt.get("tbr") or 0)
        if fmt.get("ext") == "mp4":
            score += 1e9  # mp4 ارجح
        if score > best_score:
            best_score, best = score, furl
    return best


# ---------- روش ۱: yt-dlp ----------
def _ytdlp_item(entry: dict, workdir: Path, idx: int, sessionid: str, proxy: str) -> MediaItem:
    """یک آیتمِ آلبوم رو از یک entryِ yt-dlp می‌سازه.

    yt-dlp عمدتاً ویدیو رو خوب درمیاره؛ اگه آیتم تصویر باشه و لینکِ progressive
    نداشته باشه ``DownloadError`` می‌ده تا کلِ آلبوم به instaloader واگذار بشه
    (که عکس‌ها رو تمیز می‌گیره).
    """
    media_url = _pick_progressive_url(entry)
    if not media_url:
        raise DownloadError(f"yt-dlp برای آیتمِ {idx} لینکِ مستقیم پیدا نکرد")
    target = workdir / f"{entry.get('id', 'item')}_{idx}.mp4"
    _download_media_bytes(media_url, target, sessionid, proxy)
    return MediaItem(target, True)


def _via_ytdlp(url: str, workdir: Path, sessionid: str, proxy: str) -> MediaResult:
    import yt_dlp

    # فقط «استخراج» می‌کنیم (download=False)؛ بایت‌ها رو خودمون مستقیم می‌گیریم تا
    # ترافیکِ سنگین از پروکسی نگذره و سهمیه نسوزه. پروکسی فقط روی همین استخراج اعمال می‌شه.
    # noplaylist=False تا پست‌های آلبومی/کاروسلی همه‌ی آیتم‌هاشون رو به‌صورتِ entries بدن.
    opts = {
        "format": "best[acodec!=none][vcodec!=none]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "skip_download": True,
    }
    if proxy:
        opts["proxy"] = proxy
    if sessionid:
        opts["cookiefile"] = str(_write_netscape_cookies(workdir, sessionid))

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = [e for e in (info.get("entries") or []) if e]

    # آلبوم/کاروسل: چند آیتم → همه رو می‌سازیم. کپشن/سازنده از خودِ پست (سطحِ بالا)
    # و در نبودش از اولین آیتم. اگه آیتمی resolve نشد (مثلاً عکس)، _ytdlp_item خطا
    # می‌ده و کلِ روش به instaloader واگذار می‌شه.
    if len(entries) > 1:
        caption = (
            info.get("description") or info.get("title")
            or entries[0].get("description") or entries[0].get("title")
        )
        author = _ytdlp_author(info) or _ytdlp_author(entries[0])
        items = [
            _ytdlp_item(entry, workdir, idx, sessionid, proxy)
            for idx, entry in enumerate(entries)
        ]
        return MediaResult(items, caption, author)

    if entries:
        info = entries[0]
    caption = info.get("description") or info.get("title")
    author = _ytdlp_author(info)

    media_url = _pick_progressive_url(info)
    if not media_url:
        raise DownloadError("yt-dlp لینک مستقیمِ progressive پیدا نکرد")

    target = workdir / f"{info.get('id', 'video')}.mp4"
    _download_media_bytes(media_url, target, sessionid, proxy)
    return MediaResult([MediaItem(target, True)], caption, author)


# ---------- روش ۲: instaloader ----------
def _via_instaloader(url: str, workdir: Path, sessionid: str, proxy: str) -> MediaResult:
    import instaloader

    shortcode = extract_shortcode(url)
    if not shortcode:
        raise DownloadError("شورت‌کد پیدا نشد")

    loader = instaloader.Instaloader(
        quiet=True, download_comments=False, save_metadata=False
    )
    # پروکسی فقط روی استخراجِ متادیتا (Post.from_shortcode) اعمال می‌شه
    if proxy:
        try:
            loader.context._session.proxies.update(_proxies(proxy) or {})
        except Exception:  # noqa: BLE001 - پروکسی اختیاریه
            pass
    if sessionid:
        try:
            loader.context._session.cookies.set(
                "sessionid", sessionid, domain=".instagram.com"
            )
        except Exception:  # noqa: BLE001 - کوکی اختیاریه
            pass

    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    caption = post.caption
    try:
        author = post.owner_username
    except Exception:  # noqa: BLE001 - دریافتِ یوزرنیم اختیاریه
        author = None

    # آلبوم/کاروسل (GraphSidecar): هر گره یک عکس یا ویدیوست — همه رو جدا می‌گیریم.
    if post.typename == "GraphSidecar":
        items: list[MediaItem] = []
        for idx, node in enumerate(post.get_sidecar_nodes()):
            if node.is_video:
                media_url, target = node.video_url, workdir / f"{shortcode}_{idx}.mp4"
            else:
                media_url, target = node.display_url, workdir / f"{shortcode}_{idx}.jpg"
            # بایت‌ها مستقیم (بدون پروکسی) تا سهمیه نسوزه
            _download_media_bytes(media_url, target, sessionid, proxy)
            items.append(MediaItem(target, node.is_video))
        if not items:
            raise DownloadError("instaloader هیچ آیتمی در آلبوم پیدا نکرد")
        return MediaResult(items, caption, author)

    if post.is_video:
        media_url, target, is_vid = post.video_url, workdir / f"{shortcode}.mp4", True
    else:
        media_url, target, is_vid = post.url, workdir / f"{shortcode}.jpg", False

    # بایت‌ها مستقیم (بدون پروکسی) تا سهمیه نسوزه
    _download_media_bytes(media_url, target, sessionid, proxy)
    return MediaResult([MediaItem(target, is_vid)], caption, author)


# ---------- روش ۳: صفحه embed ----------
def _via_embed(url: str, workdir: Path, sessionid: str, proxy: str) -> MediaResult:
    shortcode = extract_shortcode(url)
    if not shortcode:
        raise DownloadError("شورت‌کد پیدا نشد")

    embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
    headers = {"User-Agent": _UA}
    if sessionid:
        headers["Cookie"] = f"sessionid={sessionid}"

    # استخراجِ صفحه‌ی embed از پروکسی می‌ره (درخواست کوچیکه)
    resp = requests.get(embed_url, headers=headers, timeout=25, proxies=_proxies(proxy))
    resp.raise_for_status()
    html = resp.text

    video_url = None
    for pattern in (r'"video_url":"(.*?)"', r'property="og:video" content="(.*?)"'):
        m = re.search(pattern, html)
        if m:
            video_url = _json_unescape(m.group(1))
            break
    if not video_url:
        raise DownloadError("لینک ویدیو در صفحه embed پیدا نشد")

    caption = None
    cap = re.search(r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"(.*?)"\}', html)
    if cap:
        caption = _json_unescape(cap.group(1))

    author = None
    own = re.search(r'"owner":\{[^}]*?"username":"(.*?)"', html) or re.search(
        r'"username":"(.*?)"', html
    )
    if own:
        author = _json_unescape(own.group(1))

    target = workdir / f"{shortcode}.mp4"
    # بایت‌ها مستقیم (بدون پروکسی) تا سهمیه نسوزه
    _download_media_bytes(video_url, target, sessionid, proxy)
    return MediaResult([MediaItem(target, True)], caption, author)


# ---------- استوری / هایلایت ----------
# استوری‌ها shortcode ندارن (پس روش‌های instaloader/embed که به shortcode وابسته‌ان
# اینجا بی‌فایده‌ان)، ولی yt-dlp لینکِ استوری/هایلایت رو مستقیم resolve می‌کنه و فقط
# به کوکیِ معتبر نیاز داره. استوری می‌تونه عکس باشه نه ویدیو، پس اینجا هر دو رو هندل می‌کنیم.
def _pick_image_url(info: dict) -> str | None:
    """بهترین URLِ تصویرِ مستقیم رو از خروجیِ yt-dlp درمیاره (برای استوری/پستِ عکسی)."""
    direct = info.get("url")
    if direct and direct.startswith("http") and _url_ext(direct) in _IMAGE_URL_EXTS:
        return direct
    best: str | None = None
    best_score = -1
    for th in info.get("thumbnails") or []:
        u = th.get("url")
        if not u or not str(u).startswith("http"):
            continue
        score = int(th.get("width") or 0) * int(th.get("height") or 0)
        if not score:
            score = int(th.get("preference") or 0)
        if score > best_score:
            best_score, best = score, u
    if best:
        return best
    # هیچ thumbnail نبود؛ اگه url مستقیم داریم همونو بده (حتی با پسوندِ مبهم)
    return direct if direct and str(direct).startswith("http") else None


def _ytdlp_entry_is_video(entry: dict) -> bool:
    """تشخیصِ ویدیو/عکس‌بودنِ یک آیتمِ استوری از خروجیِ yt-dlp."""
    ext = (entry.get("ext") or "").lower()
    if ext in ("mp4", "mov", "mkv", "webm"):
        return True
    if ext in _IMAGE_URL_EXTS:
        return False
    if (entry.get("vcodec") or "none") != "none":
        return True
    for fmt in entry.get("formats") or []:
        if (fmt.get("vcodec") or "none") != "none":
            return True
    return False


def _ytdlp_any_item(entry: dict, workdir: Path, idx: int, sessionid: str, proxy: str) -> MediaItem | None:
    """یک آیتمِ استوری (عکس یا ویدیو) رو از یک entryِ yt-dlp می‌سازه؛ اگه نشد None."""
    if _ytdlp_entry_is_video(entry):
        media_url = _pick_progressive_url(entry)
        if media_url:
            target = workdir / f"story_{idx}.mp4"
            _download_media_bytes(media_url, target, sessionid, proxy)
            return MediaItem(target, True)
    img_url = _pick_image_url(entry)
    if img_url:
        ext = _url_ext(img_url)
        if ext not in _IMAGE_URL_EXTS:
            ext = "jpg"
        target = workdir / f"story_{idx}.{ext}"
        _download_media_bytes(img_url, target, sessionid, proxy)
        return MediaItem(target, False)
    # تلاشِ آخر: شاید ویدیو بود ولی ext/کدک مبهم بود
    media_url = _pick_progressive_url(entry)
    if media_url:
        target = workdir / f"story_{idx}.mp4"
        _download_media_bytes(media_url, target, sessionid, proxy)
        return MediaItem(target, True)
    return None


def _via_ytdlp_story(url: str, workdir: Path, sessionid: str, proxy: str) -> MediaResult:
    """استوری/هایلایت رو با yt-dlp می‌گیره (به کوکیِ معتبر نیاز دارد).

    یک لینکِ استوری معمولاً یک آیتمه؛ لینکِ هایلایت می‌تونه چند آیتم باشه که به‌صورتِ
    entries میان. سقفِ ۱۰ تا می‌ذاریم (محدودیتِ media_group تلگرام) تا الکی همه‌ی آیتم‌های
    یه هایلایتِ بزرگ دانلود نشن. هم عکس و هم ویدیو پشتیبانی می‌شه.
    """
    import yt_dlp

    # format رو تعیین نمی‌کنیم تا استوریِ عکسی با خطای «format not available» رد نشه؛
    # skip_download=True چون بایت‌ها رو خودمون مستقیم می‌گیریم (پروکسی فقط روی استخراج).
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "skip_download": True,
    }
    if proxy:
        opts["proxy"] = proxy
    if sessionid:
        opts["cookiefile"] = str(_write_netscape_cookies(workdir, sessionid))

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = [e for e in (info.get("entries") or []) if e] or [info]
    entries = entries[:10]
    caption = info.get("description") or info.get("title")
    author = _ytdlp_author(info) or _ytdlp_author(entries[0])

    items: list[MediaItem] = []
    for idx, entry in enumerate(entries):
        try:
            item = _ytdlp_any_item(entry, workdir, idx, sessionid, proxy)
        except FileTooLargeError:
            raise
        except Exception as exc:  # noqa: BLE001 - یه آیتمِ خراب نباید کلِ استوری رو بسوزونه
            logger.info("Story item %d failed: %s", idx, exc)
            continue
        if item is not None:
            items.append(item)

    if not items:
        raise DownloadError("yt-dlp هیچ آیتمی از استوری استخراج نکرد")
    return MediaResult(items, caption, author)


def _via_instaloader_story(url: str, workdir: Path, sessionid: str, proxy: str) -> MediaResult:
    """پشتیبانِ استوریِ یک کاربرِ مشخص با instaloader (هایلایت پشتیبانی نمی‌شه).

    به کوکیِ sessionidِ معتبر نیاز داره؛ بدونِ اون مستقیم AuthRequiredError می‌ده تا
    لایه‌ی بالاتر کوکیِ بعدی رو امتحان کنه یا به کاربر هشدارِ لاگین بده.
    """
    import instaloader

    m = _STORY_USER_RE.search(url or "")
    if not m:
        raise DownloadError("فرمتِ این استوری برای instaloader پشتیبانی نمی‌شود")
    username, media_id = m.group(1), m.group(2)
    if username.lower() == "highlights":
        raise DownloadError("هایلایت با instaloader پشتیبانی نمی‌شود")
    if not sessionid:
        raise AuthRequiredError("استوری به کوکیِ لاگین نیاز دارد")

    loader = instaloader.Instaloader(
        quiet=True, download_comments=False, save_metadata=False
    )
    if proxy:
        try:
            loader.context._session.proxies.update(_proxies(proxy) or {})
        except Exception:  # noqa: BLE001 - پروکسی اختیاریه
            pass
    try:
        loader.context._session.cookies.set(
            "sessionid", sessionid, domain=".instagram.com"
        )
    except Exception:  # noqa: BLE001 - کوکی اختیاریه
        pass

    profile = instaloader.Profile.from_username(loader.context, username)
    target_pk = int(media_id)
    for story in loader.get_stories([profile.userid]):
        for item in story.get_items():
            if item.mediaid != target_pk:
                continue
            if item.is_video:
                media_url, target, is_vid = item.video_url, workdir / f"{media_id}.mp4", True
            else:
                media_url, target, is_vid = item.url, workdir / f"{media_id}.jpg", False
            _download_media_bytes(media_url, target, sessionid, proxy)
            return MediaResult([MediaItem(target, is_vid)], None, username)
    raise DownloadError("آیتمِ استوری پیدا نشد (شاید منقضی شده)")


# نشانه‌هایی که می‌گن شکست از نوع لاگین/کوکی/ریت‌لیمیت بوده (نه پست خصوصی/حذف‌شده)
_AUTH_MARKERS = (
    "login required",
    "login_required",
    "rate-limit",
    "rate limit",
    "please wait a few minutes",
    "401",
    "403",
    "unauthorized",
    "forbidden",
    "checkpoint",
    "challenge",
)


def _looks_like_auth_failure(text: str) -> bool:
    """آیا متنِ خطاها به مشکل لاگین/کوکی/ریت‌لیمیت اشاره داره؟"""
    low = (text or "").lower()
    return any(marker in low for marker in _AUTH_MARKERS)


_METHODS = (_via_ytdlp, _via_instaloader, _via_embed)
# استوری/هایلایت shortcode ندارن؛ فقط روش‌هایی که لینک رو مستقیم resolve می‌کنن به‌کار میان.
_STORY_METHODS = (_via_ytdlp_story, _via_instaloader_story)


def _download_once(url: str, workdir: Path, sessionid: str, proxy: str) -> MediaResult:
    """با یک کوکیِ مشخص همه‌ی روش‌ها رو پشت‌سرهم امتحان می‌کنه (همگام/sync).

    هر روش توی زیرپوشه‌ی جدا کار می‌کنه تا فایل‌های ناقصِ روشِ شکست‌خورده با
    روش بعدی قاطی نشن. اگه همه‌ی روش‌ها با نشانه‌ی لاگین/ریت‌لیمیت شکست بخورن
    ``AuthRequiredError`` می‌ده تا لایه‌ی بالاتر کوکیِ بعدی رو امتحان کنه.
    ``proxy`` فقط روی مرحله‌ی استخراجِ هر روش اعمال می‌شه؛ بایت‌ها مستقیم میان.

    برای لینکِ استوری/هایلایت مجموعه‌روش‌های مخصوصِ استوری به‌کار می‌ره (چون اون‌ها
    shortcode ندارن و باید مستقیم resolve بشن).
    """
    errors: list[str] = []
    methods = _STORY_METHODS if is_story_url(url) else _METHODS

    for method in methods:
        sub = workdir / method.__name__.lstrip("_")
        sub.mkdir(parents=True, exist_ok=True)
        try:
            result = method(url, sub, sessionid, proxy)
        except FileTooLargeError:
            raise
        except Exception as exc:  # noqa: BLE001 - می‌ریم سراغ روش بعدی
            logger.info("Method %s failed: %s", method.__name__, exc)
            errors.append(f"{method.__name__}: {exc}")
            continue

        if result.file_path.exists() and result.file_path.stat().st_size > 0:
            logger.info("Downloaded successfully via %s", method.__name__)
            return result
        errors.append(f"{method.__name__}: فایل خالی")

    combined = " | ".join(errors)
    if _looks_like_auth_failure(combined):
        raise AuthRequiredError(combined)
    raise DownloadError(combined)


async def download(url: str, workdir: Path) -> MediaResult:
    """با چند کوکی و چند روش تلاش می‌کنه؛ اولین موفقیت برگردونده می‌شه.

    اگه یه کوکی ریت‌لیمیت/منقضی باشه خودکار سراغ کوکیِ بعدی می‌ره تا ربات با
    سوختن یک کوکی از کار نیفته. ترتیب کوکی‌ها هر بار درهم می‌شه تا بارِ درخواست‌ها
    بین‌شون پخش بشه و یکی‌شون زود ریت‌لیمیت نشه. ``workdir`` باید از
    ``temp_workdir`` بیاد تا در پایان کل خروجی از هاست پاک بشه.

    کوکی‌ها و پروکسی‌ها هر بار به‌صورتِ «زنده» از دیتابیس (+ .env) خونده می‌شن، پس
    افزودن/حذفشون با دستورهای ادمین بلافاصله و بدونِ ری‌استارت اثر می‌ذاره. پروکسی‌ها
    یک استخرن و به‌صورتِ چرخشی بینِ تلاش‌ها پخش می‌شن تا سهمیه‌ی یک پروکسی زود ته نکشه.
    """
    candidates = await database.get_all_cookies() or [""]
    random.shuffle(candidates)
    proxies = await database.get_all_proxies()
    random.shuffle(proxies)

    errors: list[str] = []
    auth_problem = False

    for idx, sessionid in enumerate(candidates):
        # پروکسیِ این تلاش از استخر به‌صورتِ چرخشی انتخاب می‌شه (خالی = بدونِ پروکسی)
        proxy = proxies[idx % len(proxies)] if proxies else ""
        cookie_dir = workdir / f"cookie{idx}"
        cookie_dir.mkdir(parents=True, exist_ok=True)
        try:
            return await asyncio.to_thread(
                _download_once, url, cookie_dir, sessionid, proxy
            )
        except FileTooLargeError:
            raise  # حجم به کوکی ربطی نداره؛ تلاش بیشتر بی‌فایده‌ست
        except AuthRequiredError as exc:
            auth_problem = True
            logger.info("Cookie #%d hit auth/rate-limit, trying next", idx)
            errors.append(f"cookie#{idx}: {exc}")
        except DownloadError as exc:
            logger.info("Cookie #%d failed, trying next", idx)
            errors.append(f"cookie#{idx}: {exc}")

    combined = " || ".join(errors)
    if auth_problem or _looks_like_auth_failure(combined):
        raise AuthRequiredError("لاگین/کوکی لازمه ← " + combined)
    raise DownloadError("همه روش‌ها و کوکی‌ها ناموفق بودند ← " + combined)
