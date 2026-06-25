"""فشرده‌سازی ویدیو با ffmpeg — برای ساختِ نسخه‌ی کم‌حجم‌ترِ همون ویدیو.

این ماژول ویدیویی که قبلاً روی تلگرام آپلود شده رو (بدون لمسِ دوباره‌ی اینستاگرام)
با رزولوشن/کیفیتِ پایین‌تر دوباره انکد می‌کنه تا حجمش کم بشه.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class NoAudioError(RuntimeError):
    """وقتی فایلِ ورودی اصلاً ترکِ صوتی نداره (مثلاً ریلزِ بی‌صدا)."""


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    """مسیرِ اجراییِ ffmpeg رو پیدا می‌کنه (یک‌بار پیدا و کش می‌شه).

    اولویت:
      ۱) متغیر محیطی ``IMAGEIO_FFMPEG_EXE`` (اگه کاربر دستی مسیر داده)
      ۲) ffmpeg نصب‌شده‌ی سیستمی (روی PATH)
      ۳) باینریِ همراهِ بسته‌ی ``imageio-ffmpeg`` — که بدون نیاز به نصبِ سیستمی،
         یک ffmpeg آماده فراهم می‌کنه.
    اگه هیچ‌کدوم نبود ``None`` برمی‌گردونه.
    """
    env = (os.getenv("IMAGEIO_FFMPEG_EXE") or "").strip()
    if env and Path(env).exists():
        return env

    system = shutil.which("ffmpeg")
    if system:
        return system

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - بسته نصب نیست یا باینری در دسترس نیست
        return None


def ffmpeg_available() -> bool:
    """آیا اصلاً امکانِ فشرده‌سازی روی این سرور هست؟"""
    return ffmpeg_path() is not None


# حداکثر اندازه‌ی کادر خروجی: ویدیو داخلِ ۷۲۰×۱۲۸۰ جا می‌شه و فقط کوچک می‌شه
# (هیچ‌وقت بزرگ‌نمایی نمی‌کنه چون خودِ کادر با min به اندازه‌ی منبع محدود شده).
_SCALE_FILTER = (
    "scale=min(720\\,iw):min(1280\\,ih):force_original_aspect_ratio=decrease,"
    "scale=trunc(iw/2)*2:trunc(ih/2)*2"
)


def compress_video(src: Path, dst: Path) -> None:
    """``src`` رو با رزولوشن/کیفیتِ کمتر در ``dst`` دوباره انکد می‌کنه.

    این تابع همگام (blocking) و CPU-bound است؛ از داخلِ asyncio حتماً با
    ``asyncio.to_thread`` صداش بزن تا لوپ بلاک نشه. اگه ffmpeg نباشه یا انکد
    شکست بخوره ``RuntimeError`` پرتاب می‌کنه.
    """
    exe = ffmpeg_path()
    if not exe:
        raise RuntimeError("ffmpeg not available")

    cmd = [
        exe,
        "-y",
        "-i", str(src),
        "-vf", _SCALE_FILTER,
        "-c:v", "libx264",
        "-crf", "30",            # کیفیت پایین‌تر = حجم کمتر (۲۸–۳۲ منطقیه)
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",  # برای پخشِ استریمیِ روان روی تلگرام
        str(dst),
    ]
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        tail = proc.stderr.decode("utf-8", "replace")[-500:]
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode}): {tail}")


def has_audio_stream(src: Path) -> bool:
    """آیا فایل اصلاً ترکِ صوتی داره؟

    چون ``ffprobe`` همیشه کنارِ ffmpeg نصب نیست (مثلاً باینریِ imageio-ffmpeg فقط
    خودِ ffmpeg رو داره)، با همون ffmpeg پروب می‌کنیم: ``ffmpeg -i file`` بدونِ
    خروجی، مشخصاتِ استریم‌ها رو در stderr چاپ می‌کنه و ما دنبالِ خطِ «Audio:» می‌گردیم.
    """
    exe = ffmpeg_path()
    if not exe:
        return False
    proc = subprocess.run(
        [exe, "-hide_banner", "-i", str(src)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    return "Audio:" in proc.stderr.decode("utf-8", "replace")


def extract_audio(src: Path, dst: Path) -> None:
    """صدای ``src`` رو جدا و به‌صورتِ MP3 در ``dst`` ذخیره می‌کنه.

    این تابع همگام (blocking) و CPU-bound است؛ از داخلِ asyncio حتماً با
    ``asyncio.to_thread`` صداش بزن تا لوپ بلاک نشه. اگه فایل اصلاً صدا نداشته باشه
    ``NoAudioError`` و اگه ffmpeg نبود یا استخراج شکست بخوره ``RuntimeError`` می‌ده.
    """
    exe = ffmpeg_path()
    if not exe:
        raise RuntimeError("ffmpeg not available")
    if not has_audio_stream(src):
        # ریلزِ بی‌صدا — اصلاً سراغِ انکد نمی‌ریم
        raise NoAudioError("source has no audio stream")

    cmd = [
        exe,
        "-y",
        "-i", str(src),
        "-vn",                   # ویدیو رو دور بریز، فقط صدا
        "-c:a", "libmp3lame",
        "-q:a", "2",             # کیفیتِ VBR خوب (~۱۹۰kbps)
        str(dst),
    ]
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        err = proc.stderr.decode("utf-8", "replace")
        # اگه با وجودِ پروب بازم استریمی نبود، همون «بی‌صدا» حساب می‌شه
        if "does not contain any stream" in err:
            raise NoAudioError("source has no audio stream")
        raise RuntimeError(
            f"ffmpeg audio extract failed (code {proc.returncode}): {err[-500:]}"
        )


def extract_audio_snippet(
    src: Path, dst: Path, seconds: int = 20, sample_rate: int = 16000
) -> None:
    """یه تکه‌ی کوتاهِ صوتی از ابتدای ``src`` رو به‌صورتِ WAV در ``dst`` درمیاره.

    این برای «شناساییِ آهنگ» (fingerprinting) استفاده می‌شه؛ به فایلِ کامل یا کیفیتِ
    بالا نیازی نیست، پس کوتاه و سبک می‌گیریم تا سریع باشه. خروجی **مونو / ۱۶kHz /
    ۱۶بیتی** است چون دقیقاً همون فرمتیه که الگوریتمِ fingerprintِ Shazam انتظار داره
    (نرخِ نمونه‌برداریِ ثابتِ ۱۶۰۰۰). به‌علاوه WAVِ خام رو لایه‌ی بالاتر با ماژولِ
    استانداردِ ``wave`` می‌خونه، پس به ffprobe/ffmpegِ روی PATH **نیازی نیست**.

    همگام/blocking است؛ از asyncio حتماً با ``asyncio.to_thread`` صداش بزن.
    ``NoAudioError`` برای ویدیوی بی‌صدا و ``RuntimeError`` برای نبودِ ffmpeg/شکست.
    """
    exe = ffmpeg_path()
    if not exe:
        raise RuntimeError("ffmpeg not available")
    if not has_audio_stream(src):
        raise NoAudioError("source has no audio stream")

    cmd = [
        exe,
        "-y",
        "-i", str(src),
        "-vn",                   # ویدیو رو دور بریز، فقط صدا
        "-t", str(int(seconds)),  # فقط چند ثانیه‌ی اول
        "-ac", "1",              # مونو (برای fingerprinting کافیه و لازمه)
        "-ar", str(int(sample_rate)),  # ۱۶kHz: همون نرخی که Shazam می‌خواد
        "-c:a", "pcm_s16le",     # WAV خام؛ با ماژولِ wave مستقیم خونده می‌شه
        str(dst),
    ]
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        err = proc.stderr.decode("utf-8", "replace")
        if "does not contain any stream" in err:
            raise NoAudioError("source has no audio stream")
        raise RuntimeError(
            f"ffmpeg snippet extract failed (code {proc.returncode}): {err[-500:]}"
        )
