import re, time, base64, json, logging, sys, threading, aiohttp
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update, InputFile
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from bs4 import BeautifulSoup
import pytz

# --- الإعدادات ومراقبة السيرفر ---
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAGJXv7U60MDLScX87DF8LsTZx90_Ff3CPo"
CHAT_ID = "8372609971"
STATE_FILE = "nazar_state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

# القواميس الحقيقية المحدثة للعبة RDO
ID_MAP = {
    "der": ("Bluewater Marsh",   "Lemoyne"),
    "grz": ("Grizzlies East",    "Ambarino"),
    "bbr": ("Black Balsam Rise", "Ambarino"),
    "bgv": ("Big Valley",        "West Elizabeth"),
    "blg": ("Scarlett Meadows",  "Lemoyne"),
    "bwm": ("Bluewater Marsh",   "Lemoyne"),
    "bch": ("Beecher's Hope",    "West Elizabeth"),
    "twn": ("Twin Rocks",        "New Austin"),
    "tmw": ("Tumbleweed",        "New Austin"),
    "flt": ("Flatneck Station",  "New Hanover"),
    "lmp": ("The Heartlands",    "New Hanover"),
    "wnr": ("The Heartlands",    "New Hanover"),
    "ann": ("Grizzlies East",    "Ambarino"),
    "grw": ("Grizzlies East",    "Ambarino"),
}

FAST_TRAVEL_MAP = {
    "Grizzlies East":    "Annesburg",
    "Black Balsam Rise": "Annesburg",
    "Big Valley":        "Strawberry",
    "Flatneck Station":  "Flatneck Station",
    "The Heartlands":    "Emerald Ranch",
    "Bluewater Marsh":   "Saint Denis",
    "Great Plains":      "Blackwater",
    "Scarlett Meadows":  "Rhodes",
    "Tumbleweed":        "Tumbleweed",
    "Hennigan's Stead":  "Armadillo",
    "Twin Rocks":        "Armadillo",
    "Beecher's Hope":    "Blackwater",
}

# ── نظام منع التكرار لطلب المستخدم (update_id) ──
_seen_updates = set()
_seen_lock = threading.Lock()

def is_duplicate_update(update_id: int) -> bool:
    with _seen_lock:
        if update_id in _seen_updates:
            return True
        _seen_updates.add(update_id)
        if len(_seen_updates) > 1000:
            _seen_updates.clear()
    return False

# ── نظام منع تكرار الإرسال التلقائي (Anti-Repeat State) ──
def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_date": None}

def save_state(date_str):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_date": date_str}, f)

# ── جلب البيانات والترقية لنظام Async (aiohttp) بدون كاش ──
async def get_nazar():
    location, region = None, None
    timestamp = int(time.time())
    sources = [
        ("api", f"https://api.github.com/repos/jeanropke/RDR2CollectorsMap/contents/data/nazar.json?t={timestamp}"),
        ("pages", f"https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json?t={timestamp}"),
    ]
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for name, url in sources:
            try:
                req_headers = {**HEADERS}
                if name == "api":
                    req_headers["Accept"] = "application/vnd.github.v3+json"
                
                async with session.get(url, headers=req_headers, timeout=15) as resp:
                    if resp.status != 200:
                        continue
                    
                    raw = (base64.b64decode((await resp.json())["content"]).decode() if name == "api" else await resp.text())
                    data = json.loads(raw)
                    first = data[0] if isinstance(data, list) else data
                    loc_id = first.get("id", "").strip().lower()
                    
                    if loc_id in ID_MAP:
                        location, region = ID_MAP[loc_id]
                        break
            except Exception as e:
                logger.error(f"خطأ في جلب جين روبك [{name}]: {e}")

        # جلب صورة اليوم من المصدر الصحيح madamnazar.io
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        img_url = None
        try:
            async with session.get(f"https://madamnazar.io/madam-nazar-location-{today}", timeout=10) as resp:
                if resp.status == 200:
                    soup = BeautifulSoup(await resp.text(), "html.parser")
                    img_tag = soup.find("img")
                    if img_tag and "src" in img_tag.attrs:
                        img_url = img_tag["src"]
        except Exception as e:
            logger.error(f"خطأ في جلب صورة اليوم: {e}")

    return img_url, location, region

def get_countdown():
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= nxt:
        nxt += timedelta(days=1)
    total = int((nxt - now).total_seconds())
    return total // 3600, (total % 3600) // 60

# ── الأوامر والردود التفاعلية ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار المطور\n\n"
        "📍 /nazar أو اكتب نزار — لموقع مدام نزار المحدث فورياً\n"
    )

async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_duplicate_update(update.update_id):
        return

    msg = await update.message.reply_text("🔍 جاري الفحص وجلب الموقع المحدث الحين...")
    img_url, location, region = await get_nazar()

    if not location:
        await msg.edit_text("❌ لم يتم تحديث الموقع من المصدر بعد، جربي مرة أخرى لاحقاً.")
        return

    hours, minutes = get_countdown()
    fast = FAST_TRAVEL_MAP.get(location, "غير معروف")

    caption = (
        f"📍 موقع مدام نزار الحالي:\n"
        f"← *{location}* ({region})\n\n"
        f"🏇 أقرب فاست ترافل: *{fast}*\n"
        f"⏳ تتغير نزار بعد: *{hours} ساعة و{minutes} دقيقة*"
    )

    await msg.delete()

    if img_url:
        try:
            await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
            return
        except Exception:
            pass

    await update.message.reply_text(caption, parse_mode="Markdown")

# ── الإرسال التلقائي اليومي المنظم ──
async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = load_state()
    
    if state.get("last_date") == today_str:
        logger.info("تم الإرسال التلقائي اليوم مسبقاً، تخطي التكرار.")
        return

    img_url, location, region = await get_nazar()
    if not location:
        return

    fast = FAST_TRAVEL_MAP.get(location, "غير معروف")
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
        
        save_state(today_str)
        logger.info(f"✅ تم الإرسال التلقائي اليومي بنجاح لتاريخ {today_str}")
    except Exception as e:
        logger.error(f"فشل الإرسال التلقائي اليومي: {e}")

# ── تشغيل البوت الأساسي المكتمل ──
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), send_nazar))
    
    # جدولة الإرسال اليومي الساعة 6:01 UTC بانتظام وبدون تكرار
    app.job_queue.run_daily(daily_auto_send, time=dtime(6, 1, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot is completely running now...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
