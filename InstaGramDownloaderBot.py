"""فایل اصلی اجرای ربات دانلود ریلز اینستاگرام.

اجرا:
    python InstaGramDownloaderBot.py

قبل از اجرا مطمئن شو وابستگی‌ها نصب شدن و فایل InstaDownloadBot/.env پر شده:
    pip install -r InstaDownloadBot/requirements.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

# اطمینان از اینکه ریشه پروژه روی مسیر ایمپورت هست (مستقل از محل اجرا)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from InstaDownloadBot.bot import main

if __name__ == "__main__":
    main()
