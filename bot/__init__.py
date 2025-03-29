import os
import logging
from asyncio import Queue, Lock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv
from uvloop import install

# Install UVLoop for better async performance
install()

# Logging Configuration
logging.basicConfig(
    format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%m/%d/%Y, %H:%M:%S %p",
    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
    level=logging.INFO
)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
LOGS = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv('config.env')

# Global Caches & Locks
ani_cache = {'fetch_animes': True, 'ongoing': set(), 'completed': set()}
ffpids_cache = []
ffLock = Lock()
ffQueue = Queue()
ff_queued = {}

class Var:
    """ Holds configuration variables loaded from environment. """
    
    API_ID, API_HASH, BOT_TOKEN = os.getenv("API_ID"), os.getenv("API_HASH"), os.getenv("BOT_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI")

    if not all([BOT_TOKEN, API_HASH, API_ID, MONGO_URI]):
        LOGS.critical("Important Variables Missing. Fill Up and Retry..!! Exiting Now...")
        exit(1)

    RSS_ITEMS = os.getenv("RSS_ITEMS", "https://subsplease.org/rss/?r=1080").split()
    FSUB_CHATS = list(map(int, os.getenv("FSUB_CHATS", "").split() or []))
    BACKUP_CHANNEL = os.getenv("BACKUP_CHANNEL", "")
    MAIN_CHANNEL = int(os.getenv("MAIN_CHANNEL", "0"))
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "0"))
    FILE_STORE = int(os.getenv("FILE_STORE", "0"))
    ADMINS = list(map(int, os.getenv("ADMINS", "1242011540").split()))

    SEND_SCHEDULE = os.getenv("SEND_SCHEDULE", "False").lower() == "true"
    BRAND_UNAME = os.getenv("BRAND_UNAME", "@username")
    QUALS = os.getenv("QUALS", "Hdrip 480 720 1080").split()

    AS_DOC = os.getenv("AS_DOC", "True").lower() == "true"
    AUTO_DEL = os.getenv("AUTO_DEL", "True").lower() == "true"
    DEL_TIMER = int(os.getenv("DEL_TIMER", "600"))
    THUMB = os.getenv("THUMB", "https://te.legra.ph/file/621c8d40f9788a1db7753.jpg")
    START_PHOTO = os.getenv("START_PHOTO", "https://te.legra.ph/file/120de4dbad87fb20ab862.jpg")
    START_MSG = os.getenv("START_MSG", "<b>Hey {first_name}</b>,\n\n    <i>I am Auto Animes Store & Automater Encoder Build with ❤️ !!</i>")
    START_BUTTONS = os.getenv("START_BUTTONS", "UPDATES|https://telegram.me/Matiz_Tech SUPPORT|https://t.me/+p78fp4UzfNwzYzQ5")

    # FFmpeg Encoding Commands
    FFCODE_1080 = os.getenv("FFCODE_1080", "ffmpeg -i '{}' -progress '{}' -preset veryfast -c:v libx264 -s 1920x1080 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y")
    FFCODE_720 = os.getenv("FFCODE_720", "ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 1280x720 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y")
    FFCODE_480 = os.getenv("FFCODE_480", "ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 854x480 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y")
    FFCODE_Hdrip = os.getenv("FFCODE_Hdrip", "ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 640x360 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y")

# Ensure Required Directories Exist
for folder in ["encode", "thumbs", "downloads"]:
    os.makedirs(folder, exist_ok=True)

# Download Default Thumbnail if Not Exists
if Var.THUMB and not os.path.exists("thumb.jpg"):
    os.system(f"wget -q {Var.THUMB} -O thumb.jpg")
    LOGS.info("Thumbnail has been saved!")

# Initialize Bot & Scheduler
try:
    bot = Client(
        name="AutoAniAdvance",
        api_id=Var.API_ID,
        api_hash=Var.API_HASH,
        bot_token=Var.BOT_TOKEN,
        plugins=dict(root="bot/modules"),
        parse_mode=ParseMode.HTML
    )
    bot_loop = bot.loop
    sch = AsyncIOScheduler(timezone="Asia/Kolkata", event_loop=bot_loop)
except Exception as e:
    LOGS.error(f"Bot initialization failed: {e}")
    exit(1)
