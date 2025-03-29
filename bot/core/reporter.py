import asyncio
from pyrogram.errors import FloodWait
from bot import Var, LOGS, bot

class Reporter:
    def __init__(self, client, chat_id, logger):
        self.__client = client
        self.__cid = chat_id
        self.__logger = logger
        self.__log_levels = {
            "error": self.__logger.error,
            "warning": self.__logger.warning,
            "critical": self.__logger.critical,
            "info": self.__logger.info,
        }

    async def report(self, msg, log_type, log=True):
        log_type = log_type.lower()
        log_msg = f"[{log_type.upper()}] {msg}"

        self.__log_levels.get(log_type, self.__logger.info)(log_msg)

        if log and self.__cid:
            try:
                await self.__client.send_message(self.__cid, log_msg[:4096])
            except FloodWait as e:
                self.__logger.warning(f"FloodWait: {e}")
                await asyncio.sleep(e.value * 1.5)
            except Exception as err:
                self.__logger.error(f"Report Error: {err}")

rep = Reporter(bot, Var.LOG_CHANNEL, LOGS)