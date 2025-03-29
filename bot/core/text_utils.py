from calendar import month_name
from datetime import datetime
from random import choice
from asyncio import sleep
from aiohttp import ClientSession
from anitopy import parse

from bot import Var, bot
from .ffencoder import ffargs
from .func_utils import handle_logs
from .reporter import rep

CAPTION_FORMAT = """
<b>㊂ <i>{title}</i></b>
<b>╭┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</b>
<b>⊙</b> <i>Genres:</i> <i>{genres}</i>
<b>⊙</b> <i>Status:</i> <i>RELEASING</i> 
<b>⊙</b> <i>Episodes:</i> <i>{total_eps}</i>
<b>⊙</b> <i>Current Episode:</i> <i>{ep_no}</i>
<b>⊙</b> <i>Audio: Japanese</i>
<b>⊙</b> <i>Subtitle: English</i>
<b>╰┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</b>
<b>⌬ <i>Powered By</i> ~ {cred}</b>
"""

GENRES_EMOJI = {
    "Action": "👊", "Adventure": "🧗", "Comedy": "🤣", "Drama": "🎭", "Ecchi": "💋",
    "Fantasy": "🧞", "Hentai": "🔞", "Horror": "☠", "Mahou Shoujo": "☯", "Mecha": "🤖",
    "Music": "🎸", "Mystery": "🔮", "Psychological": "♟", "Romance": "💞", "Sci-Fi": "🛸",
    "Slice of Life": "☘", "Sports": "⚽", "Supernatural": "🫧", "Thriller": "🥶"
}

ANIME_GRAPHQL_QUERY = """
query ($id: Int, $search: String, $seasonYear: Int) {
  Media(id: $id, type: ANIME, search: $search, seasonYear: $seasonYear) {
    id title { romaji english native } genres siteUrl startDate { year month day } episodes
  }
}
"""

class AniLister:
    def __init__(self, anime_name: str, year: int):
        self.__api = "https://graphql.anilist.co"
        self.__vars = {'search': anime_name, 'seasonYear': year}

    async def post_data(self):
        async with ClientSession() as session:
            async with session.post(self.__api, json={'query': ANIME_GRAPHQL_QUERY, 'variables': self.__vars}) as resp:
                return resp.status, await resp.json(), resp.headers

    async def get_anidata(self):
        for _ in range(3):  # Retry logic
            status, data, headers = await self.post_data()
            if status == 200:
                return data.get('data', {}).get('Media', {}) or {}
            elif status == 429:
                await sleep(int(headers.get('Retry-After', 5)))
            elif status >= 500:
                await sleep(5)
        return {}

class TextEditor:
    def __init__(self, name):
        self.__name = name
        self.pdata = parse(name)
        self.adata = {}

    async def load_anilist(self):
        attempts = [await self.parse_name(no_s, no_y) for no_s, no_y in [(False, False), (False, True), (True, False), (True, True)]]
        for ani_name in set(attempts):
            self.adata = await AniLister(ani_name, datetime.now().year).get_anidata()
            if self.adata:
                break

    @handle_logs
    async def parse_name(self, no_s=False, no_y=False):
        pname = self.pdata.get("anime_title", "")
        if not no_s and self.pdata.get("anime_season"):
            pname += f" {self.pdata['anime_season']}"
        if not no_y and self.pdata.get("anime_year"):
            pname += f" {self.pdata['anime_year']}"
        return pname

    @handle_logs
    async def get_poster(self):
        return f"https://img.anili.st/media/{self.adata.get('id', '')}" or "https://telegra.ph/file/112ec08e59e73b6189a20.jpg"

    @handle_logs
    async def get_caption(self):
        titles = self.adata.get("title", {})
        genres = ", ".join(f"{GENRES_EMOJI.get(x, '')} #{x.replace(' ', '_')}" for x in self.adata.get('genres', []))
        return CAPTION_FORMAT.format(
            title=titles.get('english') or titles.get('romaji') or titles.get('native', 'Unknown'),
            genres=genres,
            ep_no=self.pdata.get("episode_number", "N/A"),
            total_eps=self.adata.get("episodes", "N/A"),
            cred=Var.BRAND_UNAME
        )
