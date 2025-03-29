from multiprocessing import cpu_count
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from json import loads as jloads
from re import findall
from os import path as ospath
from time import sleep
from traceback import format_exc
from asyncio import sleep as asleep, create_subprocess_shell
from asyncio.subprocess import PIPE
from base64 import urlsafe_b64encode, urlsafe_b64decode

from aiohttp import ClientSession
from aiofiles import open as aiopen
from aioshutil import rmtree as aiormtree
from html_telegraph_poster import TelegraphPoster
from feedparser import parse as feedparse
from pyrogram.types import InlineKeyboardButton
from pyrogram.errors import MessageNotModified, FloodWait, UserNotParticipant, ReplyMarkupInvalid, MessageIdInvalid

from bot import bot, bot_loop, LOGS, Var
from .reporter import rep

def handle_logs(func):
    """Decorator to handle function exceptions and log errors."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            await rep.report(format_exc(), "error")
    return wrapper

async def sync_to_async(func, *args, wait=True, **kwargs):
    """Runs a blocking function asynchronously."""
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(ThreadPoolExecutor(max_workers=cpu_count() * 10), pfunc)
    return await future if wait else future

def new_task(func):
    """Decorator to create an async task in the event loop."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return bot_loop.create_task(func(*args, **kwargs))
    return wrapper

async def getfeed(link, index=0):
    """Fetches RSS feed entries asynchronously."""
    try:
        feed = await sync_to_async(feedparse, link)
        return feed.entries[index] if index < len(feed.entries) else None
    except Exception:
        LOGS.error(format_exc())
        return None

@handle_logs
async def aio_urldownload(link):
    """Downloads an image asynchronously and saves it."""
    async with ClientSession() as sess:
        async with sess.get(link) as data:
            image = await data.read()
    path = f"thumbs/{link.split('/')[-1]}"
    if not path.endswith((".jpg", ".png")):
        path += ".jpg"
    async with aiopen(path, "wb") as f:
        await f.write(image)
    return path

@handle_logs
async def get_telegraph(out):
    """Uploads text to Telegraph and returns the URL."""
    client = TelegraphPoster(use_api=True)
    client.create_api_token("Mediainfo")
    uname = Var.BRAND_UNAME.lstrip('@')
    page = client.post(
        title="Mediainfo",
        author=uname,
        author_url=f"https://t.me/{uname}",
        text=f"<pre>{out}</pre>",
    )
    return page.get("url")

def retry_on_exception(func):
    """Decorator to retry function on specific exceptions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except FloodWait as f:
            await rep.report(f, "warning")
            await asleep(f.value * 1.2)
            return await wrapper(*args, **kwargs)
        except ReplyMarkupInvalid:
            return await func(*args, buttons=None, **kwargs)
        except Exception:
            await rep.report(format_exc(), "error")
            return None
    return wrapper

@retry_on_exception
async def sendMessage(chat, text, buttons=None, **kwargs):
    """Sends a message with automatic flood wait handling."""
    if isinstance(chat, int):
        return await bot.send_message(chat, text, disable_web_page_preview=True, reply_markup=buttons, **kwargs)
    return await chat.reply(text, quote=True, disable_web_page_preview=True, reply_markup=buttons, **kwargs)

@retry_on_exception
async def editMessage(msg, text, buttons=None, **kwargs):
    """Edits a message with flood wait handling."""
    if msg:
        return await msg.edit_text(text, disable_web_page_preview=True, reply_markup=buttons, **kwargs)

async def encode(string):
    """Encodes a string in URL-safe Base64."""
    return urlsafe_b64encode(string.encode()).decode().strip("=")

async def decode(b64_str):
    """Decodes a URL-safe Base64 string."""
    return urlsafe_b64decode((b64_str + "=" * (-len(b64_str) % 4)).encode()).decode()

async def is_fsubbed(uid):
    """Checks if a user is subscribed to required channels."""
    for chat_id in Var.FSUB_CHATS:
        try:
            await bot.get_chat_member(chat_id, uid)
        except UserNotParticipant:
            return False
        except Exception:
            await rep.report(format_exc(), "warning")
            continue
    return True

async def get_fsubs(uid, txtargs):
    """Generates subscription check message and buttons."""
    txt = "<b><i>Please Join the Following Channels to Use this Bot!</i></b>\n\n"
    btns = []
    for no, chat in enumerate(Var.FSUB_CHATS, start=1):
        try:
            cha = await bot.get_chat(chat)
            await bot.get_chat_member(chat, uid)
            status = "Joined ✅"
        except UserNotParticipant:
            status = "Not Joined ❌"
            invite_link = (await bot.create_chat_invite_link(chat)).invite_link
            btns.append([InlineKeyboardButton(cha.title, url=invite_link)])
        except Exception:
            await rep.report(format_exc(), "warning")
            continue
        txt += f"<b>{no}. {cha.title}</b>\n  <b>Status:</b> <i>{status}</i>\n\n"
    
    if len(txtargs) > 1:
        btns.append([InlineKeyboardButton('🗂 Get Files', url=f'https://t.me/{(await bot.get_me()).username}?start={txtargs[1]}')])
    
    return txt, btns

async def mediainfo(file, get_json=False, get_duration=False):
    """Gets media information using Mediainfo."""
    try:
        format_type = "JSON" if get_json or get_duration else "HTML"
        process = await create_subprocess_shell(f"mediainfo '{file}' --Output={format_type}", stdout=PIPE, stderr=PIPE)
        stdout, _ = await process.communicate()

        if get_duration:
            try:
                return float(jloads(stdout.decode())['media']['track'][0]['Duration'])
            except Exception:
                return 1440  # Default 24 min

        return await get_telegraph(stdout.decode())
    except Exception:
        await rep.report(format_exc(), "error")
        return ""

async def clean_up():
    """Cleans up temporary directories."""
    for dirtree in ("downloads", "thumbs", "encode"):
        try:
            await aiormtree(dirtree)
        except Exception:
            LOGS.error(format_exc())

def convertTime(seconds: int) -> str:
    """Converts seconds to human-readable format."""
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = [(days, "d"), (hours, "h"), (minutes, "m"), (seconds, "s")]
    return ", ".join(f"{value}{unit}" for value, unit in parts if value)

def convertBytes(size) -> str:
    """Converts bytes to human-readable format."""
    if not size:
        return ""
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    index = 0
    while size > 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{round(size, 2)} {units[index]}"