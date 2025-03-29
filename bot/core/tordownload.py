import asyncio
from os import path as ospath, makedirs
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove
from aiohttp import ClientSession
from torrentp import TorrentDownloader
from bot.core.func_utils import handle_logs

class TorDownloader:
    def __init__(self, path="."):
        self.__downdir = path
        self.__torpath = "torrents/"
        if not ospath.exists(self.__torpath):
            makedirs(self.__torpath)

    @handle_logs
    async def download(self, torrent, name=None):
        if torrent.startswith("magnet:"):
            torp = TorrentDownloader(torrent, self.__downdir)
            await torp.start_download()
            return ospath.join(self.__downdir, name or torp._torrent_info._info.name())

        torfile = await self.get_torfile(torrent)
        if not torfile:
            return None

        torp = TorrentDownloader(torfile, self.__downdir)
        await torp.start_download()
        await aioremove(torfile)
        return ospath.join(self.__downdir, torp._torrent_info._info.name())

    @handle_logs
    async def get_torfile(self, url):
        tor_name = ospath.basename(url)
        des_dir = ospath.join(self.__torpath, tor_name)

        async with ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                async with aiopen(des_dir, "wb") as file:
                    await file.write(await response.read())
        return des_dir
