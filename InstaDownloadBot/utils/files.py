"""مدیریت فایل‌های موقت — هر دانلود توی پوشه یکتا می‌ره و بعد از کار پاک می‌شه."""
from __future__ import annotations

import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from InstaDownloadBot import config

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@contextmanager
def temp_workdir() -> Iterator[Path]:
    """یک پوشه موقت یکتا می‌سازه و در پایان (حتی با خطا) کاملاً پاکش می‌کنه.

    این تضمین می‌کنه هیچ نمونه‌ای از ویدیو روی هاست باقی نمونه.
    """
    config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    workdir = config.DOWNLOAD_DIR / uuid.uuid4().hex
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def find_media(workdir: Path) -> Path | None:
    """اولین فایل ویدیویی (یا در نبودش تصویری) رو داخل پوشه پیدا می‌کنه."""
    files = [p for p in workdir.rglob("*") if p.is_file()]
    videos = [p for p in files if p.suffix.lower() in VIDEO_EXTS]
    if videos:
        return max(videos, key=lambda p: p.stat().st_size)
    images = [p for p in files if p.suffix.lower() in IMAGE_EXTS]
    if images:
        return max(images, key=lambda p: p.stat().st_size)
    return None


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS
