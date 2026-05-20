import os, time, base64, json, logging, threading, aiohttp
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pytz

# --- الإعدادات ومراقبة السيرفر ---
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("8372609971:AAGJXv7U60MDLScX87DF8LsTZx90_Ff3CPo")
CHAT_ID = "8202101663"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache"
}

# القاموس الحقيقي المعتمد لمعرفات خريطة اللعبة الحالية
ID_MAP = {
    "ann": {"loc": "Annesburg", "reg": "New Hanover", "fast": "Annesburg", "img": "ann"},
    "bch": {"loc": "Beecher's Hope", "reg": "West Elizabeth", "fast": "Blackwater", "img": "bch"},
    "bgv": {"loc": "Big Valley", "reg": "West Elizabeth", "fast": "Strawberry", "img": "bgv"},
    "blg": {"loc": "Scarlett Meadows", "reg": "Lemoyne", "fast": "Rhodes", "img": "blg"},
    "bwm": {"loc": "Bluewater Marsh", "reg": "Lemoyne", "fast": "Saint Denis", "img": "bwm"},
    "bbr": {"loc": "Black Balsam Rise", "reg": "Ambarino", "fast": "Annesburg", "img": "bbr"},
    "coo": {"loc": "Cholla Springs", "reg": "New Austin", "fast": "Armadillo", "img": "coo"},
    "crl": {"loc": "Cotorra Springs", "reg": "Ambarino", "fast": "Bacchus Station", "img": "crl"},
    "der": {"loc": "Cumberland Forest", "reg": "New Hanover", "fast": "Valentine", "img": "der"},
    "flt": {"loc": "Flatneck Station", "reg": "New Hanover", "fast": "Flatneck Station", "img": "flt"},
    "grz": {"loc": "Grizzlies East", "reg": "Ambarino", "fast": "Annesburg", "img": "grz"},
    "hen": {"loc": "Hennigan's Stead", "reg": "New Austin", "fast": "Armadillo", "img": "hen"},
    "lmp": {"loc": "The Heartlands", "reg": "New Hanover", "fast": "Emerald Ranch", "img": "lmp"},
    "riw": {"loc": "Ridgewood Farm", "reg": "New Austin", "fast": "Tumbleweed", "img": "riw"},
    "scr": {"loc": "Scarlett Meadows", "reg": "Lemoyne", "fast": "Rhodes", "img": "blg"},
    "tal": {"loc": "Tall Trees", "reg": "West Elizabeth", "fast": "Manzanita Post", "img": "tal"},
    "tmw": {"loc": "Tumbleweed", "reg": "New Austin", "fast": "Tumbleweed", "img": "tmw"},
    "twn": {"loc": "Twin Rocks", "reg": "New Austin", "fast": "Armadillo", "img": "twn"},
    "wnr": {"loc": "Window Rock", "reg": "Ambarino", "fast": "Valentine", "img": "wnr"}
}

# نظام محكم لمنع تكرار الرسائل المزعج
_seen_updates = set()
_seen_lock = threading.Lock()

def is_duplicate_update(update_id: int) -> bool:
    with _seen_lock:
        if update_id in _seen_updates:
            return True
        _seen_updates.add(update_id)
        if len(_seen_updates) > 500:
            _seen_updates.clear()
    return False

# جلب البيانات الحقيقية اللحظية بدون كاش من المصدر الأساسي
async def get_nazar():
    timestamp = int(time.time())
    # استخدام الرابط المباشر لملف بيانات الخريطة الأساسي لمنع الكاش القديم
    url = f"https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json?t={timestamp}"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        try:
            async with session.get(url, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    first = data[0] if isinstance(data, list) else data
                    loc_id = first.get("id", "").strip().lower()
                    logger.info(f"📍 المعرف المستخرج من اللعبة الحين: {loc_id}")
                    
                    if loc_id in ID_MAP:
                        info = ID_MAP[loc_id]
                        img_url = f"https://jeanropke.github.io/RDR2CollectorsMap/assets/images/nazar/{info['img']}.png"
                        return img_url, info["loc"], info["reg"], info["fast"]
        except Exception as e:
            logger.error(f"خطأ في جلب البيانات الأصلية: {e}")
            
    return None, None, None, None

def get_countdown():
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= nxt:
        nxt += timedelta(days=1)
    total = int((nxt - now).total_seconds())
    return total // 3600, (total % 3600) // 60

# الأوامر والردود
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار المطور الحقيقي\n\n"
        "📍 /nazar أو اكتب نزار — لموقع مدام نزار المحدث فورياً بالصور\n"
    )

async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_duplicate_update(update.update_id):
        return

    msg = await update.message.reply_text("🔍 جاري فحص خوادم اللعبة وسحب الموقع الفعلي الحين...")
    img_url, location, region, fast = await get_nazar()

    if not location:
        await msg.edit_text("❌ عذرًا، فشل سحب البيانات المباشرة حاليًا، جربي مرة ثانية.")
        return

    hours, minutes = get_countdown()

    caption = (
        f"📍 موقع مدام نزار الحالي والـمُحدث الحين:\n"
        f"← *{location}* ({region})\n\n"
        f"🏇 أقرب فاست ترافل: *{fast}*\n"
        f"⏳ تتغير نزار بعد: *{hours} ساعة و{minutes} دقيقة*"
    )

    await msg.delete()

    if img_url:
        try:
            await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
            return
        except Exception as e:
            logger.error(f"فشل إرسال الصورة: {e}")

    await update.message.reply_text(caption, parse_mode="Markdown")

async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    img_url, location, region, fast = await get_nazar()
    if not location:
        return

    caption = (
        f"🔔 *تحديث يومي تلقائي لموقع مدام نزار*\n\n"
        f"📍 الموقع: *{location}* ({region})\n"
        f"🏇 أقرب فاست ترافل: *{fast}*"
    )

    try:
        if img_url:
            await context.bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"فشل الإرسال التلقائي اليومي: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), send_nazar))
    
    app.job_queue.run_daily(daily_auto_send, time=dtime(6, 1, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot is successfully running with Fixed Core Code...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
