from asyncio import gather, create_task, sleep as asleep, Event
from os import path as ospath
from aiofiles.os import remove as aioremove
from traceback import format_exc
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import bot, bot_loop, Var, ani_cache, ffQueue, ffLock, ff_queued
from .tordownload import TorDownloader
from .database import db
from .func_utils import getfeed, encode, editMessage, sendMessage
from .text_utils import TextEditor
from .ffencoder import FFEncoder
from .tguploader import TgUploader
from .reporter import rep

btn_formatter = {
    '1080': 'ⓉⓌ•1080p', 
    '720': 'ⓉⓌ•720p',
    '480': 'ⓉⓌ•480p',
    'Hdrip': 'ⓉⓌ•HDRip'
}

async def fetch_animes():
    await rep.report("Fetch Animes Started!", "info")
    while True:
        await asleep(60)
        if ani_cache['fetch_animes']:
            tasks = [create_task(get_animes(info.title, info.link))
                     for link in Var.RSS_ITEMS if (info := await getfeed(link, 0))]
            await gather(*tasks)

async def get_animes(name, torrent, force=False):
    try:
        aniInfo = TextEditor(name)
        await aniInfo.load_anilist()
        ani_id, ep_no = aniInfo.adata.get('id'), aniInfo.pdata.get("episode_number")
        if ani_id in ani_cache['completed'] and not force:
            return
        ani_cache['ongoing'].add(ani_id)
        
        if "[Batch]" in name:
            await rep.report(f"Torrent Skipped!\n\n{name}", "warning")
            return
        
        if not force and (ani_data := await db.getAnime(ani_id)) and ani_data.get(ep_no) and all(qual for qual in ani_data[ep_no].values()):
            return
        
        await rep.report(f"New Anime Torrent Found!\n\n{name}", "info")
        post_msg = await bot.send_photo(
            Var.MAIN_CHANNEL, photo=await aniInfo.get_poster(), caption=await aniInfo.get_caption()
        )
        
        stat_msg = await sendMessage(Var.MAIN_CHANNEL, f"‣ <b>Anime Name :</b> <b><i>{name}</i></b>\n\n<i>Downloading...</i>")
        dl = await TorDownloader("./downloads").download(torrent, name)
        if not dl or not ospath.exists(dl):
            await rep.report("File Download Incomplete, Try Again", "error")
            await stat_msg.delete()
            return
        
        post_id = post_msg.id
        ffEvent = Event()
        ff_queued[post_id] = ffEvent
        if ffLock.locked():
            await editMessage(stat_msg, f"‣ <b>Anime Name :</b> <b><i>{name}</i></b>\n\n<i>Queued to Encode...</i>")
            await rep.report("Added Task to Queue...", "info")
        
        await ffQueue.put(post_id)
        await ffEvent.wait()
        await ffLock.acquire()
        
        btns = []
        for qual in Var.QUALS:
            filename = await aniInfo.get_upname(qual)
            await editMessage(stat_msg, f"‣ <b>Anime Name :</b> <b><i>{name}</i></b>\n\n<i>Ready to Encode...</i>")
            
            try:
                out_path = await FFEncoder(stat_msg, dl, filename, qual).start_encode()
            except Exception as e:
                await rep.report(f"Error: {e}, Cancelled, Retry Again!", "error")
                await stat_msg.delete()
                ffLock.release()
                return
            
            await editMessage(stat_msg, f"‣ <b>Anime Name :</b> <b><i>{filename}</i></b>\n\n<i>Ready to Upload...</i>")
            
            try:
                msg = await TgUploader(stat_msg).upload(out_path, qual)
            except Exception as e:
                await rep.report(f"Error: {e}, Cancelled, Retry Again!", "error")
                await stat_msg.delete()
                ffLock.release()
                return
            
            msg_id = msg.id
            link = f"https://telegram.me/{(await bot.get_me()).username}?start={await encode('get-'+str(msg_id * abs(Var.FILE_STORE)))}"
            if post_msg:
                if btns and len(btns[-1]) == 1:
                    btns[-1].append(InlineKeyboardButton(f"{btn_formatter[qual]}", url=link))
                else:
                    btns.append([InlineKeyboardButton(f"{btn_formatter[qual]}", url=link)])
                await editMessage(post_msg, post_msg.caption.html if post_msg.caption else "", InlineKeyboardMarkup(btns))
            
            await db.saveAnime(ani_id, ep_no, qual, post_id)
            bot_loop.create_task(extra_utils(msg_id, out_path))
        
        ffLock.release()
        await stat_msg.delete()
        await aioremove(dl)
        ani_cache['completed'].add(ani_id)
    except Exception:
        await rep.report(format_exc(), "error")

async def extra_utils(msg_id, out_path):
    msg = await bot.get_messages(Var.FILE_STORE, message_ids=msg_id)
    if Var.BACKUP_CHANNEL:
        await gather(*(msg.copy(int(chat_id)) for chat_id in Var.BACKUP_CHANNEL.split()))
