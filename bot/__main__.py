import asyncio
from asyncio import create_subprocess_exec, sleep as asleep, gather, all_tasks
from aiofiles import open as aiopen
from os import path as ospath, execl, kill
from sys import executable
from signal import SIGKILL
from pyrogram import idle
from pyrogram.filters import command, user

from bot import bot, Var, bot_loop, sch, LOGS, ffQueue, ffLock, ffpids_cache, ff_queued
from bot.core.auto_animes import fetch_animes
from bot.core.func_utils import clean_up, new_task
from bot.modules.up_posts import upcoming_animes

@bot.on_message(command('restart') & user(Var.ADMINS))
@new_task
async def restart(client, message):
    rmessage = await message.reply('<i>Restarting...</i>')

    if sch.running:
        await asyncio.to_thread(sch.shutdown, wait=False)
    
    await clean_up()
    
    for pid in ffpids_cache:
        try:
            LOGS.info(f"Killing Process ID: {pid}")
            kill(pid, SIGKILL)
        except (OSError, ProcessLookupError):
            LOGS.error(f"Failed to kill Process ID: {pid}")

    await (await create_subprocess_exec('python3', 'update.py')).wait()

    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{rmessage.chat.id}\n{rmessage.id}\n")

    execl(executable, executable, "-m", "bot")

async def queue_loop():
    LOGS.info("Queue Loop Started !!")
    while True:
        if not ffQueue.empty():
            post_id = await ffQueue.get()
            ff_queued[post_id].set()
            async with ffLock:
                ffQueue.task_done()
        await asleep(5)  # Reduced delay for better efficiency

async def main():
    sch.add_job(upcoming_animes, "cron", hour=0, minute=30)
    
    await bot.start()

    if ospath.isfile(".restartmsg"):
        async with aiopen(".restartmsg") as f:
            data = await f.readlines()
            if len(data) >= 2:
                chat_id, msg_id = map(int, data[:2])
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="<i>Restarted !</i>")
                except Exception as e:
                    LOGS.error(e)

    LOGS.info("Auto Anime Bot Started!")
    sch.start()
    bot_loop.create_task(queue_loop())
    await fetch_animes()
    await idle()
    
    LOGS.info("Auto Anime Bot Stopped!")
    await bot.stop()

    await gather(*[task.cancel() for task in all_tasks()])
    await clean_up()
    LOGS.info("Finished AutoCleanUp !!")

if __name__ == '__main__':
    bot_loop.run_until_complete(main())
