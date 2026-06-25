"""محدودسازی نرخ درخواست‌ها برای محافظت از هاست در برابر فلود/حمله."""
from __future__ import annotations

import time

from InstaDownloadBot import config


class Cooldown:
    """حداقل فاصله‌ی زمانی بین درخواست‌های هر کاربر را نگه می‌دارد (ضدفلود)."""

    def __init__(self, seconds: float) -> None:
        self._seconds = seconds
        self._last: dict[int, float] = {}

    def remaining(self, user_id: int) -> float:
        """ثانیه‌های باقی‌مانده تا درخواست بعدیِ مجاز؛ ۰ یعنی همین حالا مجازه."""
        if self._seconds <= 0:
            return 0.0
        last = self._last.get(user_id)
        if last is None:
            return 0.0
        passed = time.monotonic() - last
        return self._seconds - passed if passed < self._seconds else 0.0

    def mark(self, user_id: int) -> None:
        """زمان آخرین درخواستِ پذیرفته‌شده را ثبت می‌کند."""
        self._last[user_id] = time.monotonic()


class ConcurrencyGate:
    """سقف تعداد دانلودهای هم‌زمان روی کل ربات را نگه می‌دارد.

    لوپ asyncio تک‌نخیه و بین چک و تغییرِ شمارنده await نداریم، پس این
    عملیات اتمیک محسوب می‌شه و به قفل نیازی نیست.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._active = 0

    def try_acquire(self) -> bool:
        """اگر ظرفیت خالی باشه یک اسلات می‌گیره و True برمی‌گردونه."""
        if self._limit <= 0:
            return True
        if self._active >= self._limit:
            return False
        self._active += 1
        return True

    def release(self) -> None:
        if self._active > 0:
            self._active -= 1


cooldown = Cooldown(config.COOLDOWN_SECONDS)
gate = ConcurrencyGate(config.MAX_CONCURRENT_DOWNLOADS)
