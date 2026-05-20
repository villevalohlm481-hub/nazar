import re, time, base64, json, logging, requests, sys, threading
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from bs4 import BeautifulSoup
import pytz

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "8202101663"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache",
}

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

# ── منع التكرار ───────────────────────────────────────────
_seen_updates: set = set()
_seen_lock = threading.Lock()

def is_duplicate(update_id: int) -> bool:
    with _seen_lock:
        if update_id in _seen_updates:
            return True
        _seen_updates.add(update_id)
        if len(_seen_updates) > 1000:
            _seen_updates.clear()
    return False

# ── Fetch ─────────────────────────────────────────────────
def get_nazar():
    # الموقع من jeanropke
    location, region = None, None
    sources = [
        ("api",   "https://api.github.com/repos/jeanropke/RDR2CollectorsMap/contents/data/nazar.json"),
        ("pages", "https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json"),
    ]
    for name, url in sources:
        try:
            headers = {**HEADERS}
            if name == "api":
                headers["Accept"] = "application/vnd.github.v3+json"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
            raw = (base64.b64decode(resp.json()["content"]).decode()
                   if name == "api" else resp.text)
            data = json.loads(raw)
            first = data[0] if isinstance(data, list) else data
            loc_id = first.get("id", "").strip().lower()
            logger.info(f"jeanropke loc_id: '{loc_id}'")
            if loc_id in ID_MAP:
                location, region = ID_MAP[loc_id]
                logger.info(f"✅ {loc_id} → {location}")
                break
            else:
                logger.warning(f"⛔ id '{loc_id}' مو في ID_MAP")
        except Exception as e:
            logger.error(f"jeanropke [{name}] error: {e}")

    if not location:
        return None, None, None

    # الصورة من madamnazar.io اليوم
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    img_url = None
    try:
        resp = requests.get(
            f"https://madamnazar.io/madam-nazar-location-{today}",
            headers=HEADERS, timeout=15
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            img_tag = soup.find("img")
            img_url = img_tag["src"] if img_tag else None
            logger.info(f"✅ صورة: {img_url}")
    except Exception as e:
        logger.error(f"madamnazar.io error: {e}")

    return img_url, location, region

# ── Countdown ─────────────────────────────────────────────
def get_countdown():
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= nxt:
        nxt += timedelta(days=1)
    total = int((nxt - now).total_seconds())
    return total // 3600, (total % 3600) // 60

# ── Watchdog ──────────────────────────────────────────────
def watchdog():
    while True:
        time.sleep(300)
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe",
                timeout=10
            )
            if r.status_code == 200:
                logger.info("💚 Watchdog OK")
            else:
                raise Exception(f"status {r.status_code}")
        except Exception as e:
            logger.error(f"🔴 Watchdog فشل: {e}")
            sys.exit(1)

# ── Handlers ──────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.warning("⚠️ Conflict")
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Network: {context.error}")
    else:
        logger.error(f"Error: {context.error}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍 /nazar أو اكتب نزار — لموقع مدام نزار\n\n"
        "🌸 /map — لخريطة الكولكتر التفاعلية\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_duplicate(update.update_id):
        return

    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, location, region = get_nazar()

    if not location:
        await msg.edit_text("❌ ما قدرت أجيب الموقع، حاول مرة ثانية.")
        return

    hours, minutes = get_countdown()
    fast = FAST_TRAVEL_MAP.get(location, "غير معروف")

    caption = (
        f"📍 *{location}*\n\n"
        f"أقرب فاست ترافل: *{fast}*\n"
        f"⏳ يتغير بعد *{hours} ساعة و{minutes} دقيقة*"
    )

    await msg.delete()

    if img_url:
        try:
            await update.message.reply_photo(
                photo=img_url, caption=caption, parse_mode="Markdown"
            )
            return
        except Exception as e:
            logger.error(f"صورة فشلت: {e}")

    await update.message.reply_text(caption, parse_mode="Markdown")


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}"
    )


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    img_url, location, region = get_nazar()

    if not location:
        return

    fast = FAST_TRAVEL_MAP.get(location, "غير معروف")

    caption = (
        f"📍 *{location}*\n\n"
        f"أقرب فاست ترافل: *{fast}*"
    )

    if img_url:
        try:
            await context.bot.send_photo(
                chat_id=CHAT_ID, photo=img_url,
                caption=caption, parse_mode="Markdown"
            )
            return
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=CHAT_ID, text=caption, parse_mode="Markdown"
    )

# ── Main ──────────────────────────────────────────────────
def main():
    threading.Thread(target=watchdog, daemon=True).start()
    logger.info("👁️ Watchdog شغال")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"نزار"), send_nazar
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"كول[ي]?كتر"), map_command
    ))
    app.add_error_handler(error_handler)
    app.job_queue.run_daily(
        daily_auto_send, time=dtime(6, 1, 0, tzinfo=pytz.UTC)
    )

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
