from motor.motor_asyncio import AsyncIOMotorClient
from bot import Var

class MongoDB:
    def __init__(self, uri, database_name):
        self.__client = AsyncIOMotorClient(uri)
        self.__db = self.__client[database_name]
        self.__animes = self.__db.animes[Var.BOT_TOKEN.split(':')[0]]
        self.__channels = self.__db.channels  # New collection for anime-channel mappings

    async def getAnime(self, ani_id):
        botset = await self.__animes.find_one({'_id': ani_id})
        return botset or {}

    async def saveAnime(self, ani_id, ep, qual, post_id=None):
        quals = (await self.getAnime(ani_id)).get(ep, {qual: False for qual in Var.QUALS})
        quals[qual] = True
        await self.__animes.update_one({'_id': ani_id}, {'$set': {ep: quals}}, upsert=True)
        if post_id:
            await self.__animes.update_one({'_id': ani_id}, {'$set': {"msg_id": post_id}}, upsert=True)

    async def reboot(self):
        await self.__animes.drop()

    # New Functions for Separate Channel Mapping
    async def set_separate_channel(self, anime_name, channel_id):
        """Set a separate upload channel for a specific anime."""
        await self.__channels.update_one(
            {'anime_name': anime_name.lower()},
            {'$set': {'channel_id': channel_id}},
            upsert=True
        )

    async def get_separate_channel(self, anime_name):
        """Retrieve the upload channel for a specific anime."""
        data = await self.__channels.find_one({'anime_name': anime_name.lower()})
        return data['channel_id'] if data else None

    async def remove_separate_channel(self, anime_name):
        """Remove a channel mapping for an anime."""
        await self.__channels.delete_one({'anime_name': anime_name.lower()})

    async def get_all_separate_channels(self):
        """Return all anime-to-channel mappings."""
        mappings = await self.__channels.find().to_list(length=None)
        return {item['anime_name']: item['channel_id'] for item in mappings}

db = MongoDB(Var.MONGO_URI, "FZAutoAnimes")