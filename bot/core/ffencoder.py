from re import findall, compile as re_compile
from math import floor
from time import time
from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, rename as aiorename
from shlex import split as ssplit
from asyncio import sleep as asleep, gather, create_subprocess_shell, create_task
from asyncio.subprocess import PIPE

from bot import Var, bot_loop, ffpids_cache, LOGS
from .func_utils import mediainfo, convertBytes, convertTime, sendMessage, editMessage
from .reporter import rep

ffargs = {
    '1080': Var.FFCODE_1080,
    '720': Var.FFCODE_720,
    '480': Var.FFCODE_480,
    'Hdrip': Var.FFCODE_Hdrip,
}

# Precompile regex for efficiency
TIME_REGEX = re_compile(r"out_time_ms=(\d+)")
SIZE_REGEX = re_compile(r"total_size=(\d+)")
PROGRESS_REGEX = re_compile(r"progress=(\w+)")

class FFEncoder:
    def __init__(self, message, path, name, qual):
        self.__proc = None
        self.is_cancelled = False
        self.message = message
        self.__name = name
        self.__qual = qual
        self.dl_path = path
        self.out_path = ospath.join("encode", name)
        self.__prog_file = 'prog.txt'
        self.__start_time = time()
        self.__total_time = None

    async def progress(self):
        self.__total_time = await mediainfo(self.dl_path, get_duration=True) or 1.0
        while not (self.__proc is None or self.is_cancelled):
            async with aiopen(self.__prog_file, 'r') as p:
                text = await p.read()

            if text:
                time_done = floor(int(TIME_REGEX.findall(text)[-1]) / 1_000_000) if TIME_REGEX.findall(text) else 1
                ensize = int(SIZE_REGEX.findall(text)[-1]) if SIZE_REGEX.findall(text) else 0

                diff = time() - self.__start_time
                speed = ensize / max(diff, 1)
                percent = round((time_done / self.__total_time) * 100, 2)
                tsize = ensize / max(percent / 100, 0.01)
                eta = (tsize - ensize) / max(speed, 0.01)

                bar = f"{'█' * floor(percent / 8)}{'▒' * (12 - floor(percent / 8))}"

                progress_str = (
                    f"<blockquote>‣ <b>Anime Name :</b> <b><i>{self.__name}</i></b></blockquote>\n"
                    f"<blockquote>‣ <b>Status :</b> <i>Encoding</i>\n"
                    f"    <code>[{bar}]</code> {percent}%</blockquote>\n"
                    f"<blockquote>   ‣ <b>Size :</b> {convertBytes(ensize)} out of ~ {convertBytes(tsize)}\n"
                    f"    ‣ <b>Speed :</b> {convertBytes(speed)}/s\n"
                    f"    ‣ <b>Time Took :</b> {convertTime(diff)}\n"
                    f"    ‣ <b>Time Left :</b> {convertTime(eta)}</blockquote>\n"
                    f"<blockquote>‣ <b>File(s) Encoded:</b> <code>{Var.QUALS.index(self.__qual)} / {len(Var.QUALS)}</code></blockquote>"
                )

                await editMessage(self.message, progress_str)

                if PROGRESS_REGEX.findall(text) and PROGRESS_REGEX.findall(text)[-1] == 'end':
                    break

            await asleep(8)

    async def start_encode(self):
        if ospath.exists(self.__prog_file):
            await aioremove(self.__prog_file)

        async with aiopen(self.__prog_file, 'w'):
            LOGS.info("Progress Temp Generated!")

        dl_npath, out_npath = ospath.join("encode", "ffanimeadvin.mkv"), ospath.join("encode", "ffanimeadvout.mkv")
        await aiorename(self.dl_path, dl_npath)

        ffcode = ffargs[self.__qual].format(dl_npath, self.__prog_file, out_npath)
        LOGS.info(f'FFCode: {ffcode}')

        self.__proc = await create_subprocess_shell(ffcode, stdout=PIPE, stderr=PIPE)
        ffpids_cache.append(self.__proc.pid)

        _, return_code = await gather(create_task(self.progress()), self.__proc.wait())
        ffpids_cache.remove(self.__proc.pid)

        await aiorename(dl_npath, self.dl_path)

        if not self.is_cancelled and return_code == 0 and ospath.exists(out_npath):
            await aiorename(out_npath, self.out_path)
            return self.out_path

        if return_code != 0:
            stderr_output = (await self.__proc.stderr.read()).decode().strip()
            await rep.report(stderr_output, "error")

    async def cancel_encode(self):
        self.is_cancelled = True
        if self.__proc:
            try:
                self.__proc.kill()
            except ProcessLookupError:
                pass