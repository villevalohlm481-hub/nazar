"""
Madam Nazar RDO Telegram Bot
- موقع نزار من jeanropke مباشرة
- صورة الخريطة من madamnazar.io
- إرسال يومي تلقائي 6:01 UTC
- منع التكرار + watchdog داخلي
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# ──────────────────────────────────────────────────────────
# إعداد اللوج
# ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("NazarBot")

# ──────────────────────────────────────────────────────────
# متغيرات البيئة
# ──────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ["8372609971:AAGJXv7U60MDLScX87DF8LsTZx90_Ff3CPo"]          # توكن البوت
CHANNEL_ID  = os.environ["-1003763689916"]         # مثال: -1001234567890 أو @channel
# اختياري: قائمة chat_id مفصولة بفاصلة
EXTRA_CHATS = [
    c.strip()
    for c in os.environ.get("EXTRA_CHATS", "").split(",")
    if c.strip()
]

ALL_TARGETS = [CHANNEL_ID] + EXTRA_CHATS

# ──────────────────────────────────────────────────────────
# خريطة المواقع العربية + أقرب فاست ترافل
# (ID_MAP: id من jeanropke → اسم عربي، اسم إنجليزي، فاست ترافل)
# ──────────────────────────────────────────────────────────
LOCATION_MAP: dict[str, dict] = {
    "rio_del_lobo_rock": {
        "ar": "صخرة ريو ديل لوبو",
        "en": "Rio Del Lobo Rock",
        "region": "New Hanover",
        "fast_travel": "Emerald Ranch",
    },
    "emerald_ranch": {
        "ar": "إيمرالد رانش",
        "en": "Emerald Ranch",
        "region": "New Hanover",
        "fast_travel": "Emerald Ranch",
    },
    "heartlands_oil_fields": {
        "ar": "حقول نفط هارتلاندز",
        "en": "Heartlands Oil Fields",
        "region": "New Hanover",
        "fast_travel": "Emerald Ranch",
    },
    "cumberland_forest": {
        "ar": "غابة كمبرلاند",
        "en": "Cumberland Forest",
        "region": "New Hanover",
        "fast_travel": "Emerald Ranch",
    },
    "flat_iron_lake": {
        "ar": "بحيرة فلات آيرون",
        "en": "Flat Iron Lake",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "tall_trees": {
        "ar": "الأشجار الطويلة",
        "en": "Tall Trees",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "great_plains": {
        "ar": "السهول الكبرى",
        "en": "Great Plains",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "blackwater": {
        "ar": "بلاكووتر",
        "en": "Blackwater",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "thieves_landing": {
        "ar": "ثيفز لاندينج",
        "en": "Thieves Landing",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "scarlett_meadows": {
        "ar": "سكارليت ميدوز",
        "en": "Scarlett Meadows",
        "region": "Lemoyne",
        "fast_travel": "Rhodes",
    },
    "rhodes": {
        "ar": "رودز",
        "en": "Rhodes",
        "region": "Lemoyne",
        "fast_travel": "Rhodes",
    },
    "bluewater_marsh": {
        "ar": "مستنقع بلووتر",
        "en": "Bluewater Marsh",
        "region": "Lemoyne",
        "fast_travel": "Saint Denis",
    },
    "saint_denis": {
        "ar": "سانت دينيس",
        "en": "Saint Denis",
        "region": "Lemoyne",
        "fast_travel": "Saint Denis",
    },
    "lagras": {
        "ar": "لاغراس",
        "en": "Lagras",
        "region": "Lemoyne",
        "fast_travel": "Saint Denis",
    },
    "bayou_nwa": {
        "ar": "بايو نوا",
        "en": "Bayou NWA",
        "region": "Lemoyne",
        "fast_travel": "Saint Denis",
    },
    "bolger_glade": {
        "ar": "بولجر غلايد",
        "en": "Bolger Glade",
        "region": "Lemoyne",
        "fast_travel": "Rhodes",
    },
    "ringneck_creek": {
        "ar": "رينجنيك كريك",
        "en": "Ringneck Creek",
        "region": "New Hanover",
        "fast_travel": "Emerald Ranch",
    },
    "elysian_pool": {
        "ar": "بركة إليزيان",
        "en": "Elysian Pool",
        "region": "New Hanover",
        "fast_travel": "Emerald Ranch",
    },
    "roanoke_ridge": {
        "ar": "روانوك ريدج",
        "en": "Roanoke Ridge",
        "region": "New Hanover",
        "fast_travel": "Van Horn",
    },
    "annesburg": {
        "ar": "أنسبرج",
        "en": "Annesburg",
        "region": "New Hanover",
        "fast_travel": "Van Horn",
    },
    "van_horn": {
        "ar": "فان هورن",
        "en": "Van Horn",
        "region": "New Hanover",
        "fast_travel": "Van Horn",
    },
    "beaver_hollow": {
        "ar": "بيفر هولو",
        "en": "Beaver Hollow",
        "region": "New Hanover",
        "fast_travel": "Van Horn",
    },
    "lemoyne_raiders_hideout": {
        "ar": "مخبأ مهاجمي ليموين",
        "en": "Lemoyne Raiders Hideout",
        "region": "Lemoyne",
        "fast_travel": "Rhodes",
    },
    "tumbleweed": {
        "ar": "تمبلويد",
        "en": "Tumbleweed",
        "region": "New Austin",
        "fast_travel": "Tumbleweed",
    },
    "armadillo": {
        "ar": "أرماديلو",
        "en": "Armadillo",
        "region": "New Austin",
        "fast_travel": "Armadillo",
    },
    "rio_bravo": {
        "ar": "ريو برافو",
        "en": "Rio Bravo",
        "region": "New Austin",
        "fast_travel": "Armadillo",
    },
    "cholla_springs": {
        "ar": "تشولا سبرينجز",
        "en": "Cholla Springs",
        "region": "New Austin",
        "fast_travel": "Armadillo",
    },
    "rathskeller_fork": {
        "ar": "راتسكيلر فورك",
        "en": "Rathskeller Fork",
        "region": "New Austin",
        "fast_travel": "Tumbleweed",
    },
    "nekoti_rock": {
        "ar": "نيكوتي روك",
        "en": "Nekoti Rock",
        "region": "Ambarino",
        "fast_travel": "Annesburg",
    },
    "wapiti_indian_reservation": {
        "ar": "محمية واپيتي",
        "en": "Wapiti Indian Reservation",
        "region": "Ambarino",
        "fast_travel": "Annesburg",
    },
    "bacchus_station": {
        "ar": "محطة باكوس",
        "en": "Bacchus Station",
        "region": "Ambarino",
        "fast_travel": "Emerald Ranch",
    },
    "moonstone_pond": {
        "ar": "بركة مونستون",
        "en": "Moonstone Pond",
        "region": "Ambarino",
        "fast_travel": "Emerald Ranch",
    },
    "fort_wallace": {
        "ar": "قلعة والاس",
        "en": "Fort Wallace",
        "region": "Ambarino",
        "fast_travel": "Emerald Ranch",
    },
    "window_rock": {
        "ar": "ويندو روك",
        "en": "Window Rock",
        "region": "Ambarino",
        "fast_travel": "Annesburg",
    },
    "hanging_dog_ranch": {
        "ar": "مزرعة هانجينج دوج",
        "en": "Hanging Dog Ranch",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "owanjila": {
        "ar": "أوانجيلا",
        "en": "Owanjila",
        "region": "West Elizabeth",
        "fast_travel": "Blackwater",
    },
    "stillwater_creek": {
        "ar": "ستيلووتر كريك",
        "en": "Stillwater Creek",
        "region": "New Austin",
        "fast_travel": "Armadillo",
    },
    "benedict_point": {
        "ar": "بينيديكت بوينت",
        "en": "Benedict Point",
        "region": "New Austin",
        "fast_travel": "Tumbleweed",
    },
}

# ──────────────────────────────────────────────────────────
# حالة البوت (بدون قاعدة بيانات — في الذاكرة)
# ──────────────────────────────────────────────────────────
seen_update_ids: set[int] = set()   # منع تكرار الأوامر
last_daily_date: str | None = None  # منع تكرار الإرسال اليومي


# ──────────────────────────────────────────────────────────
# جلب بيانات نزار من jeanropke
# ──────────────────────────────────────────────────────────
async def fetch_nazar_data() -> dict | None:
    """
    يجيب بيانات مدام نزار من jeanropke.github.io
    يرجع dict فيه: location_id, location_ar, location_en, region, fast_travel
    """
    url = "https://jeanropke.github.io/RDOMap/data/nazar.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (RDO-NazarBot/2.0)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            raw = resp.json()

        # الـ JSON من jeanropke: {"nazar": {"location": "scarlett_meadows", ...}}
        # أو {"location": "scarlett_meadows"} — نتعامل مع الحالتين
        if isinstance(raw, dict):
            loc_id = (
                raw.get("nazar", {}).get("location")
                or raw.get("location")
                or ""
            ).lower().strip()
        else:
            logger.error("nazar.json format unexpected: %s", raw)
            return None

        if not loc_id:
            logger.error("location_id فارغ في nazar.json")
            return None

        # ننظّف الـ id (نزيل المنطقة الفرعية — نأخذ الاسم الأساسي فقط)
        # مثال: "bolger_glade_in_southern_scarlett_meadows" → "bolger_glade"
        clean_id = _clean_location_id(loc_id)
        info = LOCATION_MAP.get(clean_id)

        if info:
            return {
                "location_id": clean_id,
                "location_ar": info["ar"],
                "location_en": info["en"],
                "region": info["region"],
                "fast_travel": info["fast_travel"],
            }
        else:
            # موقع جديد غير موجود في الخريطة — نستخدم الـ id كاسم
            logger.warning("location_id غير موجود في LOCATION_MAP: %s", loc_id)
            pretty = loc_id.replace("_", " ").title()
            return {
                "location_id": loc_id,
                "location_ar": pretty,
                "location_en": pretty,
                "region": "غير معروف",
                "fast_travel": "غير محدد",
            }

    except Exception as e:
        logger.exception("خطأ في جلب nazar.json: %s", e)
        return None


def _clean_location_id(raw_id: str) -> str:
    """
    يحوّل مثل:
      bolger_glade_in_southern_scarlett_meadows → bolger_glade
      rio_del_lobo_rock_in_new_hanover → rio_del_lobo_rock
    يبحث عن أطول مفتاح موجود في LOCATION_MAP يكون prefix للـ raw_id.
    """
    for key in sorted(LOCATION_MAP.keys(), key=len, reverse=True):
        if raw_id == key or raw_id.startswith(key + "_"):
            return key
    return raw_id


# ──────────────────────────────────────────────────────────
# جلب صورة الخريطة من madamnazar.io
# ──────────────────────────name──────────────────────────────
async def fetch_nazar_image() -> bytes | None:
    """
    يجيب صورة الخريطة من madamnazar.io/map
    بدون fallback لأمس — لو فشل يرجع None
    """
    # madamnazar.io تحدّث صورتها يومياً في نفس الـ URL
    image_url = "https://madamnazar.io/map"
    headers = {
        "User-Agent": "Mozilla/5.0 (RDO-NazarBot/2.0)",
        "Referer": "https://madamnazar.io/",
        "Cache-Control": "no-cache",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(image_url, headers=headers)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            # لو الرد HTML (يعني صفحة) نستخرج رابط الصورة منها
            if "html" in ct:
                img_bytes = await _extract_map_image_from_html(resp.text, client)
                return img_bytes
            elif "image" in ct:
                return resp.content
            else:
                logger.warning("محتوى غير متوقع من madamnazar.io: %s", ct)
                return None
    except Exception as e:
        logger.exception("خطأ في جلب صورة madamnazar.io: %s", e)
        return None


async def _extract_map_image_from_html(html: str, client: httpx.AsyncClient) -> bytes | None:
    """يستخرج رابط الصورة من HTML ويحمّلها"""
    # نبحث عن <img ... src="...map..." ...>
    patterns = [
        r'<img[^>]+src=["\']([^"\']*map[^"\']*)["\']',
        r'<img[^>]+src=["\']([^"\']*nazar[^"\']*\.(png|jpg|webp))["\']',
        r'"image":\s*"([^"]+)"',
        r"'image':\s*'([^']+)'",
    ]
    base = "https://madamnazar.io"
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            src = m.group(1)
            if not src.startswith("http"):
                src = base + ("" if src.startswith("/") else "/") + src
            try:
                r = await client.get(src, timeout=15)
                r.raise_for_status()
                if "image" in r.headers.get("content-type", ""):
                    return r.content
            except Exception as e:
                logger.warning("فشل تحميل الصورة %s: %s", src, e)
    logger.warning("لم يُعثر على صورة في HTML madamnazar.io")
    return None


# ──────────────────────────────────────────────────────────
# بناء الرسالة
# ──────────────────────────────────────────────────────────
def build_message(data: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"🔮 *مدام نزار اليوم* — {today}\n\n"
        f"📍 *الموقع:* {data['location_ar']}\n"
        f"🗺 *المنطقة:* {data['region']}\n"
        f"⚡ *أقرب فاست ترافل:* {data['fast_travel']}\n\n"
        f"_📌 {data['location_en']}_"
    )


# ──────────────────────────────────────────────────────────
# إرسال الرسالة (نص + صورة)
# ──────────────────────────────────────────────────────────
async def send_nazar_update(bot: Bot, chat_ids: list[str]) -> bool:
    data = await fetch_nazar_data()
    if not data:
        logger.error("فشل جلب بيانات نزار — لا يوجد إرسال")
        return False

    text = build_message(data)
    image = await fetch_nazar_image()

    success = False
    for chat_id in chat_ids:
        try:
            if image:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image,
                    caption=text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                # لو الصورة فشلت نرسل نص فقط
                await bot.send_message(
                    chat_id=chat_id,
                    text=text + "\n\n_(الخريطة غير متاحة حالياً)_",
                    parse_mode=ParseMode.MARKDOWN,
                )
            logger.info("✅ أُرسلت رسالة نزار إلى %s", chat_id)
            success = True
        except TelegramError as e:
            logger.error("❌ فشل الإرسال إلى %s: %s", chat_id, e)

    return success


# ──────────────────────────────────────────────────────────
# الإرسال اليومي التلقائي (Scheduler)
# ──────────────────────────────────────────────────────────
async def daily_job(bot: Bot) -> None:
    global last_daily_date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if last_daily_date == today:
        logger.info("الإرسال اليومي أُنجز بالفعل اليوم %s — تخطّي", today)
        return

    logger.info("🕕 الإرسال اليومي لـ %s", today)
    ok = await send_nazar_update(bot, ALL_TARGETS)
    if ok:
        last_daily_date = today


# ──────────────────────────────────────────────────────────
# أوامر البوت
# ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_duplicate(update):
        return
    await update.message.reply_text(
        "👋 أهلاً! أنا بوت مدام نزار 🔮\n"
        "استخدم /nazar لمعرفة موقعها اليوم.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_duplicate(update):
        return

    msg = await update.message.reply_text("⏳ جارٍ التحقق من موقع مدام نزار...")

    data = await fetch_nazar_data()
    if not data:
        await msg.edit_text("❌ تعذّر جلب موقع مدام نزار، حاول بعد قليل.")
        return

    text = build_message(data)
    image = await fetch_nazar_image()

    try:
        if image:
            await update.message.reply_photo(
                photo=image,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            await msg.delete()
        else:
            await msg.edit_text(
                text + "\n\n_(الخريطة غير متاحة حالياً)_",
                parse_mode=ParseMode.MARKDOWN,
            )
    except TelegramError as e:
        logger.error("خطأ في إرسال رد /nazar: %s", e)


async def cmd_force(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر مخفي لإعادة الإرسال اليدوي (للمشرف)"""
    if _is_duplicate(update):
        return
    await send_nazar_update(context.bot, ALL_TARGETS)
    await update.message.reply_text("✅ تم الإرسال يدوياً.")


# ──────────────────────────────────────────────────────────
# مساعد: منع تكرار الطلبات
# ──────────────────────────────────────────────────────────
def _is_duplicate(update: Update) -> bool:
    uid = update.update_id
    if uid in seen_update_ids:
        logger.warning("طلب مكرر update_id=%s — تجاهل", uid)
        return True
    seen_update_ids.add(uid)
    # نحتفظ بآخر 1000 فقط لتفادي تضخّم الذاكرة
    if len(seen_update_ids) > 1000:
        oldest = sorted(seen_update_ids)[:200]
        for i in oldest:
            seen_update_ids.discard(i)
    return False


# ──────────────────────────────────────────────────────────
# Watchdog داخلي
# ──────────────────────────────────────────────────────────
_last_heartbeat: float = time.time()


async def heartbeat_task() -> None:
    """يُحدّث نبض القلب كل دقيقة"""
    global _last_heartbeat
    while True:
        _last_heartbeat = time.time()
        await asyncio.sleep(60)


async def watchdog_task(app: Application) -> None:
    """يراقب البوت — لو توقف النبض 10 دقائق يُعيد الاتصال"""
    while True:
        await asyncio.sleep(300)  # كل 5 دقائق
        elapsed = time.time() - _last_heartbeat
        if elapsed > 600:
            logger.warning("⚠️ Watchdog: البوت متوقف منذ %.0f ثانية — إعادة تشغيل البولينج", elapsed)
            try:
                await app.updater.stop()
                await asyncio.sleep(3)
                await app.updater.start_polling(drop_pending_updates=True)
                logger.info("✅ Watchdog: أُعيد تشغيل البولينج")
            except Exception as e:
                logger.error("Watchdog error: %s", e)


# ──────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────
async def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("nazar", cmd_nazar))
    app.add_handler(CommandHandler("force", cmd_force))

    # Scheduler — إرسال يومي 6:01 UTC
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        daily_job,
        trigger="cron",
        hour=6,
        minute=1,
        args=[app.bot],
        id="daily_nazar",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info("✅ Scheduler مُفعَّل — إرسال يومي 06:01 UTC")

    async with app:
        await app.start()
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message"],
        )
        logger.info("🤖 البوت يعمل...")

        # تشغيل المهام الخلفية
        asyncio.create_task(heartbeat_task())
        asyncio.create_task(watchdog_task(app))

        # ابقاء البوت شغّالاً
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
