import asyncio
import subprocess
from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove as aioremove, mkdir
from aiohttp import ClientSession
from bot import LOGS
from bot.core.func_utils import handle_logs

class TorDownloader:
    def __init__(self, path="downloads"):
        self.__downdir = path
        self.__torpath = "torrents/"

    @handle_logs
    async def download(self, torrent: str, name: str = None) -> str:
        """
        Downloads a torrent or magnet link using aria2c.
        :param torrent: Magnet link or URL to a .torrent file
        :param name: Optional filename override
        :return: Path to the downloaded file or None if failed
        """
        if torrent.startswith("magnet:"):
            return await self._download_with_aria2(torrent, name)
        
        elif torfile := await self.get_torfile(torrent):
            return await self._download_with_aria2(torfile, name)
        
        else:
            LOGS.error("Failed to retrieve torrent metadata. Possible invalid magnet link.")
            return None

    @handle_logs
    async def _download_with_aria2(self, source: str, name: str = None) -> str:
        """
        Uses aria2c to download the torrent.
        :param source: Magnet link or torrent file path
        :param name: Optional filename override
        :return: Path to the downloaded file
        """
        LOGS.info(f"Starting download using aria2: {source}")
        command = [
            "aria2c",
            "--dir=" + self.__downdir,
            "--seed-time=0",
            "--max-connection-per-server=16",
            "--split=16",
            "--bt-max-peers=500",
            "--bt-tracker-connect-timeout=5",
            "--bt-tracker-timeout=5",
            "--bt-tracker=udp://tracker.openbittorrent.com:80/announce",
            "--summary-interval=5",
            "--continue=true",
            source,
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            LOGS.info(f"Download completed: {name if name else source}")
            return self.__downdir
        else:
            LOGS.error(f"aria2c failed: {stderr.decode().strip()}")
            return None

    @handle_logs
    async def get_torfile(self, url: str) -> str:
        """
        Downloads a .torrent file and saves it locally.
        :param url: URL of the .torrent file
        :return: Path to the saved torrent file
        """
        if not await aiopath.isdir(self.__torpath):
            await mkdir(self.__torpath)
        
        tor_name = url.split('/')[-1]
        des_dir = ospath.join(self.__torpath, tor_name)
        
        async with ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiopen(des_dir, 'wb') as file:
                        async for chunk in response.content.iter_any():
                            await file.write(chunk)
                    return des_dir
        return None