"""شناساییِ نامِ آهنگِ ریلز از روی خودِ صدا (مثلِ Shazam) با کتابخانه‌ی ``ShazamAPI``.

این ماژول یه تکه‌ی کوتاهِ صوتیِ ریلز رو fingerprint می‌کنه و به سرورِ شناساییِ Shazam
می‌فرسته و نامِ آهنگ + خواننده رو برمی‌گردونه. حتی وقتی ریلز «Original audio» باشه ولی
پشتش آهنگِ معروفی پخش شه، باز هم تشخیص داده می‌شه.

چرا ``ShazamAPI`` و نه ``shazamio``؟
-----------------------------------
هر دو همون سرورِ مجانیِ Shazam رو صدا می‌زنن، ولی ``shazamio`` به ``pydantic`` نسخه‌ی ۱
نیاز داره؛ روی این سرور که چند رباتِ دیگه (aiogram، نیازمندِ pydantic v2) محیطِ پایتونِ
مشترک دارن، نصبِ shazamio اون‌ها رو می‌شکنه. اما ``ShazamAPI`` فقط به ``numpy`` و
``requests`` (و ``pydub`` که فقط برای importش لازمه، نه استفاده) وابسته‌ست و **هیچ
ربطی به pydantic نداره** — پس بی‌خطر کنارِ بقیه نصب می‌شه.

نکته‌ی مهم: عمداً از کلاسِ ``ShazamAPI.Shazam`` استفاده **نمی‌کنیم**، چون اون داخلش با
``pydub.AudioSegment.from_file`` فرمتِ صدا رو با **ffprobe** تشخیص می‌ده و ffprobe روی
این سرور (که فقط ffmpegِ imageio داره) نصب نیست. به‌جاش، خودمون WAVِ مونو/۱۶kHz رو که
``video.extract_audio_snippet`` ساخته با ماژولِ استانداردِ ``wave`` می‌خونیم و مستقیم
به الگوریتمِ fingerprint می‌دیم — پس به ffprobe نیازی نیست.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
import wave
from array import array
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# حداکثر تعدادِ قطعه‌ی fingerprint که از یه snippet به سرور می‌فرستیم. هر قطعه ~۸ ثانیه
# رو پوشش می‌ده؛ این سقف جلوی طولانی‌شدنِ بی‌مورد رو وقتی آهنگی مَچ نمی‌شه می‌گیره.
_MAX_SIGNATURES = 6
# مهلتِ هر درخواستِ شبکه‌ای به سرورِ Shazam (ثانیه).
_HTTP_TIMEOUT = 30


@lru_cache(maxsize=1)
def recognition_available() -> bool:
    """آیا کتابخانه‌ی ShazamAPI روی این سرور نصب و **واقعاً قابلِ استفاده** هست؟

    عمداً خودِ ماژولِ الگوریتم رو import می‌کنیم (نه فقط ``find_spec``) چون importِ
    ``ShazamAPI`` به‌صورتِ زنجیره‌ای ``pydub`` رو هم import می‌کنه و ``pydub`` روی
    پایتونِ ۳.۱۳+ (که ماژولِ ``audioop`` رو حذف کرده) شکست می‌خوره. با importِ واقعی
    مطمئن می‌شیم روی این مفسر «قابلِ استفاده» هست؛ وگرنه دکمه‌ی آهنگ اصلاً نمایش داده
    نمی‌شه (نه دکمه‌ی بی‌خاصیت، نه خطا). نتیجه با ``lru_cache`` فقط یک‌بار اجرا می‌شه.
    """
    try:
        from ShazamAPI.algorithm import SignatureGenerator  # noqa: F401

        return True
    except Exception:  # noqa: BLE001 - نبودِ پکیج یا حذفِ audioop = «در دسترس نیست»
        return False


def _format_track(result: dict | None) -> str:
    """از پاسخِ Shazam نامِ «عنوان — خواننده» رو می‌سازه.

    خروجی:
      * رشته‌ی غیرخالی → آهنگ شناخته شد.
      * رشته‌ی خالی ("") → پاسخ اومد ولی هیچ آهنگی مَچ نشد.
    """
    track = (result or {}).get("track") or {}
    title = (track.get("title") or "").strip()
    artist = (track.get("subtitle") or "").strip()  # در پاسخِ Shazam، خواننده در subtitle است
    if not title:
        return ""
    return f"{title} — {artist}" if artist else title


def _read_mono16_samples(path: Path) -> array:
    """نمونه‌های صوتیِ یک WAVِ مونو/۱۶بیتی رو با ماژولِ استانداردِ ``wave`` می‌خونه.

    ``video.extract_audio_snippet`` خروجی رو دقیقاً مونو/۱۶kHz/۱۶بیتی (pcm_s16le)
    می‌سازه، پس اینجا فقط بایت‌ها رو به آرایه‌ی ``int16`` تبدیل می‌کنیم — بدونِ نیاز به
    pydub یا ffprobe.
    """
    with wave.open(str(path), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    samples = array("h")  # signed 16-bit
    samples.frombytes(frames)
    return samples


def _recognize_sync(path: Path) -> str:
    """نسخه‌ی همگام (blocking) شناسایی — باید داخلِ ``asyncio.to_thread`` صدا زده شه.

    خروجی: نامِ آهنگ، یا "" وقتی پاسخ اومد ولی چیزی مَچ نشد. خطاهای شبکه‌ای raise
    می‌شن تا لایه‌ی بالاتر اون‌ها رو «شکستِ موقت» (نه «آهنگی نیست») حساب کنه.
    """
    import requests
    from ShazamAPI.algorithm import SignatureGenerator
    from ShazamAPI.api import API_URL, HEADERS, TIME_ZONE

    samples = _read_mono16_samples(path)

    generator = SignatureGenerator()
    generator.feed_input(samples)
    generator.MAX_TIME_SECONDS = 8

    for _ in range(_MAX_SIGNATURES):
        signature = generator.get_next_signature()
        if not signature:
            break
        payload = {
            "timezone": TIME_ZONE,
            "signature": {
                "uri": signature.encode_to_uri(),
                "samplems": int(
                    signature.number_samples / signature.sample_rate_hz * 1000
                ),
            },
            "timestamp": int(time.time() * 1000),
            "context": {},
            "geolocation": {},
        }
        response = requests.post(
            API_URL % (str(uuid.uuid4()).upper(), str(uuid.uuid4()).upper()),
            headers=HEADERS,
            json=payload,
            timeout=_HTTP_TIMEOUT,
        )
        response.raise_for_status()  # خطای HTTP = شکستِ موقت (raise می‌شه)
        name = _format_track(response.json())
        if name:
            return name

    return ""


async def identify_song(path: Path) -> str | None:
    """نامِ آهنگ ("عنوان — خواننده") رو از روی فایلِ صوتیِ ``path`` برمی‌گردونه.

    خروجی:
      * رشته‌ی غیرخالی → آهنگ شناخته شد.
      * "" → شناسایی اجرا شد ولی آهنگی پیدا نشد (قطعی؛ قابلِ کش‌کردن).
      * ``None`` → کتابخانه در دسترس نیست (نباید رخ بده اگه ``recognition_available``
        قبلش چک شده باشه).

    کارِ سنگین (fingerprint + شبکه) داخلِ یک thread اجرا می‌شه تا لوپِ asyncio بلاک
    نشه. خطاهای شبکه‌ای/موقت raise می‌شن تا لایه‌ی بالاتر «تلاشِ دوباره» رو ممکن نگه داره.
    """
    if not recognition_available():
        return None
    return await asyncio.to_thread(_recognize_sync, path)
