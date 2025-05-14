from pyrogram import Client, filters
from bot.core.database import db
from bot import Var

@Client.on_message(filters.command("setchannel") & filters.user(Var.OWNER_ID))
async def set_channel(client, message):
    """Command: /setchannel <anime_name> <channel_id>"""
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply("Usage: `/setchannel <anime_name> <channel_id>`")
    
    anime_name, channel_id = args[1].lower(), args[2]
    
    if not channel_id.startswith("-100"):
        return await message.reply("Invalid Channel ID! Use a private/public channel's numeric ID (starting with `-100`).")
    
    await db.set_separate_channel(anime_name, channel_id)
    await message.reply(f"✅ Separate channel set for **{anime_name}** → `{channel_id}`")

@Client.on_message(filters.command("listchannels") & filters.user(Var.OWNER_ID))
async def list_channels(client, message):
    """Command: /listchannels"""
    channels = await db.get_all_separate_channels()
    
    if not channels:
        return await message.reply("No separate channels set.")
    
    msg = "**📜 Separate Anime-Channel Mappings:**\n\n"
    for anime, channel in channels.items():
        msg += f"**{anime}** → `{channel}`\n"
    
    await message.reply(msg)

@Client.on_message(filters.command("removechannel") & filters.user(Var.OWNER_ID))
async def remove_channel(client, message):
    """Command: /removechannel <anime_name>"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("Usage: `/removechannel <anime_name>`")
    
    anime_name = args[1].lower()
    await db.remove_separate_channel(anime_name)
    await message.reply(f"❌ Removed separate channel for **{anime_name}**")
