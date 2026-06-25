<div align="center">

# 📥 InstaDownloadBot

**A fast, multilingual Telegram bot for saving Instagram Reels, posts & stories — with VIP subscriptions, forced‑join channels, song recognition, and a full admin toolkit.**

🌐 **[English](#-english)** · **[فارسی](#-فارسی)**

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.6-26A5E4?logo=telegram&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white)
![Async](https://img.shields.io/badge/async-aiosqlite-4B8BBE)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)
![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-D97757?logo=anthropic&logoColor=white)

</div>

---

## 🇬🇧 English

### ✨ Overview

**InstaDownloadBot** is a production‑grade Telegram bot that lets users grab media from Instagram by simply sending a link. It ships with a complete monetization & growth layer (VIP subscriptions paid in Telegram Stars, forced‑join channels with expiry), smart anti‑abuse limits, and a rich admin panel — all running comfortably on cheap, **console‑less** hosts thanks to a single auto‑installing `requirements.txt`.

The UI is fully bilingual (**Persian 🇮🇷 / English 🇬🇧**), chosen per user on first start; all console logs stay in English for easy server debugging.

### 🚀 Features

#### For users
- 🎬 **One‑link media saving** — send a Reel/post/story link, get the file back automatically.
- 🎵 **"What's this song?"** — recognizes the track in a Reel via Shazam (no paid API).
- 🪶 **Low‑size version** — re‑encodes heavy videos with a bundled `ffmpeg` so they fit Telegram's limit.
- 🌐 **Per‑user language** — pick Persian or English on first `/start`, switchable anytime.
- ⭐ **VIP membership** — higher daily quotas, paid natively with **Telegram Stars**.

#### Growth & monetization
- 🔒 **Forced‑join gate** — require users to join one or more channels before using the bot.
- ⏳ **Per‑channel expiry (موندگاری)** — set how many days a required channel stays active (`0` = unlimited); expired channels auto‑drop.
- 📣 **Broadcast** — message every user, with automatic deactivation of blocked users.
- 💎 **Runtime‑configurable VIP** — change price & duration live with admin commands; expiry reminders sent automatically.

#### Reliability & anti‑abuse
- 🛡️ **Anti‑flood** — per‑user cooldown + a global cap on concurrent downloads to protect host resources.
- 📊 **Daily quotas** — separate free/VIP limits for downloads, audio extraction, and compression (reset at UTC midnight).
- 🗃️ **Smart cache with TTL** — avoids re‑downloading the same media; cache expires so the bot never becomes a permanent archive of others' content.
- 🔁 **Source rotation** — multiple Instagram `sessionid` cookies rotate automatically when one is rate‑limited.
- 🌍 **Residential‑proxy aware** — the proxy is used **only** for the small link‑extraction request, while heavy video bytes stream straight from Instagram's CDN — so a limited proxy quota lasts up to ~50× longer.

#### Admin toolkit
- 🔑 `/addcookie` · `/addproxy` · `/sources` — manage `sessionid` cookies & proxies **live**, without restarting.
- 💾 `/backup` — download a copy of the SQLite database.
- 🩺 `/health` — quick status snapshot.
- 💸 `/refund` — refund a Telegram Stars payment.
- 💲 `/setprice` · `/setduration` — tune VIP pricing on the fly.
- ➕ Channel management for the forced‑join gate (title → channel → duration flow).

#### Operations
- ⏰ **Background jobs (JobQueue)** — periodic cache purge, orphaned temp‑dir sweep, expired‑channel cleanup, and VIP‑expiry reminders. Degrades gracefully if the `[job-queue]` extra isn't installed.
- 🪶 **Console‑less hosting friendly** — designed for hosts like PebbleHost: upload the folder, dependencies auto‑install from `requirements.txt`, no shell required.

### 🧰 Tech stack

| Layer | Choice |
|------|--------|
| Language | Python 3.9+ |
| Bot framework | [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) `21.6` (with `[job-queue]`) |
| Database | SQLite (WAL mode) via `aiosqlite` |
| Downloading | `yt-dlp` + `instaloader` |
| Media processing | `imageio-ffmpeg` (bundled ffmpeg binary — **no system install needed**) |
| Song ID | `ShazamAPI` |
| Config | `python-dotenv` |

### 📂 Project structure

```
InstaGramDownload/
├─ InstaGramDownloaderBot.py      # entry-point launcher
├─ README.md
├─ .gitignore
└─ InstaDownloadBot/              # main package
   ├─ bot.py                      # app setup, handler registration, job scheduling
   ├─ config.py                   # .env loader & settings
   ├─ database.py                 # aiosqlite (WAL) data layer
   ├─ jobs.py                     # periodic jobs (cleanup, VIP reminders)
   ├─ keyboards.py                # inline / reply keyboards
   ├─ localization.py             # fa / en UI strings
   ├─ requirements.txt
   ├─ .env.example                # config template — copy to .env
   ├─ handlers/
   │  ├─ start.py                 # /start, language pick, forced-join gate
   │  ├─ download.py              # core: link → media
   │  ├─ vip.py                   # VIP purchase (Telegram Stars)
   │  ├─ admin.py                 # admin commands & channel management
   │  ├─ sources.py               # live cookie / proxy management
   │  ├─ broadcast.py             # broadcast to all users
   │  └─ support.py               # help / support
   ├─ services/
   │  ├─ instagram.py             # download engine (yt-dlp / instaloader)
   │  └─ membership.py            # channel membership checks
   └─ utils/
      ├─ files.py                 # filesystem helpers
      ├─ ratelimit.py             # cooldown & daily quotas
      ├─ song.py                  # Shazam song recognition
      └─ video.py                 # ffmpeg compression
```

### ⚙️ Setup

```bash
# 1) Clone
git clone https://github.com/xcoolerboy/Instagram-Downloader-Bot.git
cd Instagram-Downloader-Bot

# 2) (optional) virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 3) Install dependencies
pip install -r InstaDownloadBot/requirements.txt

# 4) Configure
cp InstaDownloadBot/.env.example InstaDownloadBot/.env
#   then edit InstaDownloadBot/.env and set at least:
#     BOT_TOKEN  (from @BotFather)
#     ADMIN_IDS  (your numeric Telegram ID, from @userinfobot)

# 5) Run
python InstaGramDownloaderBot.py
#   or:  python -m InstaDownloadBot.bot
```

### 🔧 Configuration

All settings live in `InstaDownloadBot/.env` (see `.env.example` for the fully‑commented template).

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | **Required.** Token from [@BotFather](https://t.me/BotFather). |
| `ADMIN_IDS` | — | **Required.** Comma‑separated numeric admin IDs. |
| `DB_PATH` | `bot.db` | SQLite database path. |
| `DOWNLOAD_DIR` | `downloads` | Temp folder for media (cleared after sending). |
| `MAX_FILE_MB` | `50` | Max upload size to Telegram. |
| `COOLDOWN_SECONDS` | `60` | Min seconds between a user's downloads (`0` = off). |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Global cap on simultaneous downloads (`0` = unlimited). |
| `CACHE_TTL_DAYS` | `30` | Media cache lifetime (`0` = never expire). |
| `FREE_DAILY_LIMIT` / `VIP_DAILY_LIMIT` | `10` / `50` | Daily download quotas. |
| `FREE_AUDIO_DAILY_LIMIT` / `VIP_AUDIO_DAILY_LIMIT` | `2` / `50` | Daily audio‑extraction quotas. |
| `FREE_COMPRESS_DAILY_LIMIT` / `VIP_COMPRESS_DAILY_LIMIT` | `2` / `10` | Daily compression quotas. |
| `VIP_PRICE_STARS` | `50` | Initial VIP price in Telegram Stars (editable at runtime). |
| `VIP_DURATION_DAYS` | `30` | Initial VIP duration (editable at runtime). |
| `INSTAGRAM_SESSIONID` | — | Optional. One or more `sessionid` cookies (comma‑separated) to boost success rate. |
| `INSTAGRAM_PROXY` | — | Optional residential proxy for link extraction. `http(s)://user:pass@host:port` or `socks5://...` |

### ☁️ Deployment (console‑less hosts, e.g. PebbleHost)

1. Upload the whole `InstaDownloadBot/` folder (plus the launcher) to the host.
2. Point the host's Python startup file at `InstaGramDownloaderBot.py` (or run `python -m InstaDownloadBot.bot`).
3. Make sure `requirements.txt` is picked up so dependencies auto‑install.
4. Create `InstaDownloadBot/.env` on the server with your real values.
5. Add the bot as **admin** in any channel you use for the forced‑join gate (so it can verify membership).

### ⚠️ Disclaimer

This project is provided for **educational and personal use**. You are responsible for complying with Instagram's Terms of Service and applicable copyright law in your jurisdiction. The cache is intentionally short‑lived (`CACHE_TTL_DAYS`) so the bot does not act as a permanent archive of third‑party content. This project is **not affiliated with, endorsed by, or sponsored by** Instagram or Meta.

### 📝 License

Released under the **MIT License** — see [`LICENSE`](LICENSE). You're free to use, modify, and distribute this project (including commercially) with attribution.

---

## 🇮🇷 فارسی

### ✨ معرفی

**InstaDownloadBot** یک ربات تلگرامِ کامل و آماده‌ی بهره‌برداریه که با فرستادنِ یه لینک، مدیا رو از اینستاگرام برای کاربر می‌گیره. یه لایه‌ی کاملِ درآمدزایی و رشد هم داره (اشتراکِ VIP با اِستارزِ تلگرام، جوینِ اجباری با موندگاری)، محدودیت‌های هوشمندِ ضدِسوءاستفاده، و یه پنلِ مدیریتیِ پر و پیمون — همه‌ش روی هاست‌های ارزون و **بدونِ کنسول** هم راحت بالا میاد، چون فقط یه `requirements.txt` داره که خودکار نصب می‌شه.

رابطِ کاربری کاملاً دوزبانه‌ست (**فارسی 🇮🇷 / انگلیسی 🇬🇧**) و بارِ اول توسطِ کاربر انتخاب می‌شه؛ لاگ‌های کنسول برای دیباگِ راحتِ سرور، انگلیسی می‌مونن.

### 🚀 امکانات

#### برای کاربر
- 🎬 **ذخیره با یه لینک** — لینکِ ریلز/پست/استوری رو بفرست، فایل خودکار برمی‌گرده.
- 🎵 **«این آهنگ چیه؟»** — آهنگِ داخلِ ریلز رو با Shazam تشخیص می‌ده (بدونِ APIِ پولی).
- 🪶 **نسخه‌ی کم‌حجم** — ویدیوهای سنگین رو با `ffmpeg`ِ همراه فشرده می‌کنه تا توی سقفِ تلگرام جا شن.
- 🌐 **زبانِ اختصاصیِ هر کاربر** — بارِ اولِ `/start` فارسی یا انگلیسی رو انتخاب کن، هر وقت هم خواستی عوضش کن.
- ⭐ **اشتراکِ VIP** — سهمیه‌ی روزانه‌ی بیشتر، با پرداختِ مستقیمِ **اِستارزِ تلگرام**.

#### رشد و درآمدزایی
- 🔒 **دروازه‌ی جوینِ اجباری** — قبلِ استفاده، کاربر باید عضوِ یک یا چند کانال بشه.
- ⏳ **موندگاریِ هر کانال** — تعیین کن یه کانالِ اجباری چند روز فعال بمونه (`۰` = نامحدود)؛ کانالِ منقضی‌شده خودکار حذف می‌شه.
- 📣 **پیامِ همگانی (Broadcast)** — به همه‌ی کاربرها پیام بده؛ کاربرهایی که ربات رو بلاک کردن خودکار غیرفعال می‌شن.
- 💎 **VIPِ قابلِ‌تنظیم در لحظه** — قیمت و مدت رو زنده با دستورهای ادمین عوض کن؛ یادآوریِ انقضا خودکار فرستاده می‌شه.

#### پایداری و ضدِسوءاستفاده
- 🛡️ **ضدِفلود** — فاصله‌ی زمانیِ هر کاربر + سقفِ کلیِ دانلودِ هم‌زمان برای محافظت از منابعِ هاست.
- 📊 **سهمیه‌ی روزانه** — حدِ جداگانه‌ی رایگان/VIP برای دانلود، گرفتنِ صدا و فشرده‌سازی (نصفه‌شبِ UTC ریست می‌شه).
- 🗃️ **کشِ هوشمند با انقضا** — از دانلودِ دوباره‌ی یه مدیا جلوگیری می‌کنه؛ کش منقضی می‌شه تا ربات هیچ‌وقت آرشیوِ دائمیِ محتوای دیگران نشه.
- 🔁 **چرخشِ منابع** — چند کوکیِ `sessionid` وقتی یکی ریت‌لیمیت بشه، خودکار جابه‌جا می‌شن.
- 🌍 **سازگار با پروکسیِ residential** — پروکسی **فقط** برای درخواستِ کوچیکِ استخراجِ لینک استفاده می‌شه و بایت‌های سنگینِ ویدیو مستقیم از CDNِ اینستا میان — برای همین سهمیه‌ی محدودِ پروکسی تا حدودِ ۵۰ برابر بیشتر دووم میاره.

#### جعبه‌ابزارِ ادمین
- 🔑 `/addcookie` · `/addproxy` · `/sources` — مدیریتِ **زنده‌ی** کوکی و پروکسی، بدونِ ری‌استارت.
- 💾 `/backup` — گرفتنِ کپی از دیتابیسِ SQLite.
- 🩺 `/health` — وضعیتِ سریعِ ربات.
- 💸 `/refund` — برگشتِ پرداختِ اِستارز.
- 💲 `/setprice` · `/setduration` — تنظیمِ لحظه‌ایِ قیمت/مدتِ VIP.
- ➕ مدیریتِ کانال‌های جوینِ اجباری (روندِ عنوان ← کانال ← مدت).

#### عملیات
- ⏰ **کارهای پس‌زمینه (JobQueue)** — پاک‌سازیِ دوره‌ایِ کش، حذفِ پوشه‌های موقتِ یتیم، پاک‌کردنِ کانالِ منقضی و یادآوریِ انقضای VIP. اگه اکسترای `[job-queue]` نصب نباشه، ربات بدونِ این کارها هم سالم کار می‌کنه.
- 🪶 **مناسبِ هاستِ بدونِ کنسول** — برای هاست‌هایی مثلِ PebbleHost ساخته شده: پوشه رو آپلود کن، وابستگی‌ها خودکار از `requirements.txt` نصب می‌شن، نیازی به شل نیست.

### ⚙️ راه‌اندازی

```bash
# ۱) کلون
git clone https://github.com/xcoolerboy/Instagram-Downloader-Bot.git
cd Instagram-Downloader-Bot

# ۲) (اختیاری) محیطِ مجازی
python -m venv .venv

# ۳) نصبِ وابستگی‌ها
pip install -r InstaDownloadBot/requirements.txt

# ۴) تنظیمات
cp InstaDownloadBot/.env.example InstaDownloadBot/.env
#   بعد InstaDownloadBot/.env رو باز کن و حداقل این‌ها رو پر کن:
#     BOT_TOKEN  (از @BotFather)
#     ADMIN_IDS  (آیدیِ عددیت، از @userinfobot)

# ۵) اجرا
python InstaGramDownloaderBot.py
```

> 📌 یادت باشه: برای دروازه‌ی جوینِ اجباری، ربات رو در هر کانالی که استفاده می‌کنی **ادمین** کن تا بتونه عضویت رو بررسی کنه.

### ⚠️ سلبِ مسئولیت

این پروژه فقط برای **استفاده‌ی آموزشی و شخصی** ارائه شده. مسئولیتِ رعایتِ قوانینِ اینستاگرام و قانونِ کپی‌رایتِ کشورت با خودته. کش عمداً کوتاه‌مدته (`CACHE_TTL_DAYS`) تا ربات آرشیوِ دائمیِ محتوای دیگران نشه. این پروژه **هیچ وابستگی‌ای** به اینستاگرام یا متا نداره.

<div align="center">

---

Made with ❤️ for the Persian Telegram community

🤖 Architected & documented with **[Claude Code](https://claude.com/claude-code)**

</div>
