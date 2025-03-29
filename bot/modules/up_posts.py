import asyncio
from json import loads as jloads
from os import execl
from sys import executable

from aiohttp import ClientSession
from bot import Var, bot, ffQueue
from bot.core.text_utils import TextEditor
from bot.core.reporter import rep

TD_SCHR = None  # Global variable to store the pinned message

async def upcoming_animes():
    global TD_SCHR

    if Var.SEND_SCHEDULE:
        try:
            async with ClientSession() as session:
                async with session.get("https://subsplease.org/api/?f=schedule&h=true&tz=Asia/Kolkata") as res:
                    if res.status != 200:
                        raise Exception(f"Failed to fetch schedule, HTTP Status: {res.status}")
                    aniContent = await res.json()

            text_lines = ["<b>📆 Today's Anime Releases Schedule [IST]</b>\n"]
            for i in aniContent.get("schedule", []):
                aname = TextEditor(i["title"])
                await aname.load_anilist()
                title = aname.adata.get('title', {}).get('english') or i['title']
                text_lines.append(f''' <a href="https://subsplease.org/shows/{i['page']}">{title}</a>\n    • <b>Time</b> : {i["time"]} hrs\n''')

            TD_SCHR = await bot.send_message(Var.MAIN_CHANNEL, "\n".join(text_lines))
            await (await TD_SCHR.pin()).delete()

        except Exception as err:
            await rep.report(f"Error in upcoming_animes: {err}", "error")

    if not ffQueue.empty():
        await ffQueue.join()

    await rep.report("Auto Restarting..!!", "info")
    execl(executable, executable, "-m", "bot")

async def update_shdr(name, link):
    global TD_SCHR

    if TD_SCHR:
        TD_lines = TD_SCHR.text.split('\n')
        TD_lines = [
            f"    • **Status :** ✅ __Uploaded__\n    • **Link :** {link}" if line.startswith(f"📌 {name}") else line
            for line in TD_lines
        ]
        await TD_SCHR.edit("\n".join(TD_lines))
