from motor.motor_asyncio import AsyncIOMotorClient
from bot import Var

class MongoDB:
    def __init__(self, uri, database_name):
        self.__client = AsyncIOMotorClient(uri)
        self.__db = self.__client[database_name]
        self.__animes = self.__db.animes[Var.BOT_TOKEN.split(':')[0]]

    async def get_anime(self, ani_id):
        return await self.__animes.find_one({'_id': ani_id}) or {}

    async def save_anime(self, ani_id, ep, qual, post_id=None):
        update_data = {f"{ep}.{qual}": True}
        if post_id:
            update_data["msg_id"] = post_id
        await self.__animes.update_one({'_id': ani_id}, {'$set': update_data}, upsert=True)

    async def reboot(self):
        await self.__animes.drop()

db = MongoDB(Var.MONGO_URI, "FZAutoAnimes")