from os import path as ospath
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from aiofiles.os import remove as aioremove, rename as aiorename
from datetime import datetime

from bot import bot, Var
from .func_utils import sendMessage, encode
from .tordownload import TorDownloader
from .text_utils import TextEditor
from .tguploader import TgUploader
from .ffencoder import FFEncoder
from .reporter import rep

def generate_safe_filename(original_name, qual):
    """
    Generate a safe, standardized filename
    
    Args:
        original_name (str): Original anime name
        qual (str): Quality of the file
    
    Returns:
        str: Formatted filename
    """
    # Remove special characters and replace spaces
    safe_name = ''.join(c if c.isalnum() or c in [' ', '.', '_'] else '' for c in original_name)
    safe_name = safe_name.replace(' ', '_')

    # Add timestamp and quality
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_name}_{qual}_{timestamp}.mkv"

async def handle_download_command(client, message):
    """
    Handle the /download command with advanced renaming
    """
    # Admin check
    if message.from_user.id not in Var.ADMINS:
        await sendMessage(message.chat.id, "❌ You are not authorized to use this command.")
        return

    # Extract torrent link and optional anime name
    try:
        command_parts = message.text.split(maxsplit=2)
        torrent_link = command_parts[1]
        anime_name = command_parts[2] if len(command_parts) > 2 else None
    except IndexError:
        await sendMessage(message.chat.id, "❌ Usage: `/download <torrent_link> [anime_name]`")
        return

    # Send initial status message
    status_msg = await sendMessage(
        message.chat.id, 
        f"🔄 Processing download:\n\n" + 
        f"🔗 Torrent: {torrent_link}\n" + 
        f"📝 Anime Name: {anime_name or 'Auto-detect'}"
    )

    try:
        # Download the torrent
        dl_path = await TorDownloader("./downloads").download(torrent_link, anime_name)

        if not dl_path:
            await status_msg.edit("❌ Download failed. Please check the torrent link.")
            return

        # If anime name not provided, try to extract from filename
        if not anime_name:
            anime_name = ospath.basename(dl_path)

        # Process anime information
        aniInfo = TextEditor(anime_name)
        await aniInfo.load_anilist()

        # Prepare temporary paths
        downloads_dir = ospath.dirname(dl_path)
        temp_input_path = ospath.join(downloads_dir, f"temp_input_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mkv")

        # Rename original download to temp input
        await aiorename(dl_path, temp_input_path)

        # Prepare encoding and upload buttons
        btns = []
        for qual in Var.QUALS:
            # Generate safe filename
            safe_filename = generate_safe_filename(anime_name, qual)
            out_path = ospath.join("encode", safe_filename)

            # Edit status message
            await status_msg.edit(f"🔄 Encoding {qual} version...")

            # Temporary output path
            temp_output_path = ospath.join(downloads_dir, f"temp_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mkv")

            # Create FFEncoder instance with temp paths
            encoder = FFEncoder(
                message=status_msg, 
                path=temp_input_path, 
                name=safe_filename, 
                qual=qual
            )

            # Modify FFEncoder to use temp output path
            encoder.out_path = out_path

            # Encode
            encoded_path = await encoder.start_encode()

            # Upload
            upload_msg = await TgUploader(status_msg).upload(encoded_path, qual)

            # Generate shareable link
            msg_id = upload_msg.id
            link = f"https://telegram.me/{(await bot.get_me()).username}?start={await encode('get-'+str(msg_id * abs(Var.FILE_STORE)))}"

            # Add quality button
            btns.append([InlineKeyboardButton(f"📥 {qual} Version", url=link)])

        # Cleanup temporary input file
        if ospath.exists(temp_input_path):
            await aioremove(temp_input_path)

        # Final status
        await status_msg.edit(
            f"✅ Download and Upload Complete!\n\n" + 
            f"🔗 Anime: {anime_name}",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")
        await rep.report(f"Download Command Error: {str(e)}", "error")
        # Ensure temp files are cleaned up
        if 'temp_input_path' in locals() and ospath.exists(temp_input_path):
            await aioremove(temp_input_path)

# Add this to the bot/modules/download.py
@bot.on_message(filters.command("download") & filters.user(Var.ADMINS))
async def download_command(client, message):
    await handle_download_command(client, message)