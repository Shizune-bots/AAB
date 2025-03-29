from asyncio import create_task, sleep
import logging
import os
from pyrogram import filters
from pyrogram.types import Message
import time
import threading

from bot import bot, Var, bot_loop
from .func_utils import sendMessage, editMessage
from .tordownload import TorDownloader
from .reporter import rep
from .text_utils import TextEditor
from .database import db

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Download command handler
@bot.on_message(filters.command("download") & filters.private)
async def handle_download_command(client, message: Message):
    """Handle the /download command to download torrents or magnet links"""
    try:
        # Extract the link from the message
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            await message.reply_text("Please provide a magnet or torrent link after the /download command.")
            return
        
        link = command_parts[1].strip()
        
        # Validate the link
        if not (link.startswith("magnet:?") or (link.startswith("http") and 
                                              (link.endswith(".torrent") or "torrent" in link))):
            await message.reply_text("❌ Invalid link. Please provide a valid magnet link or torrent URL.")
            return
        
        # Generate a unique download ID
        download_id = f"dl_{int(time.time())}"
        
        # Send initial status message
        status_message = await message.reply_text("✅ Download started! Initializing...")
        
        # Start download process in a separate task
        create_task(process_download(link, message.chat.id, status_message.id, download_id, message.from_user.id))
        
    except Exception as e:
        logger.error(f"Error in handle_download_command: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def process_download(link, chat_id, message_id, download_id, user_id):
    """Process the download and trigger the anime processing pipeline"""
    try:
        # Send initial status update
        await editMessage(message_id, f"📥 Download started for:\n`{link}`\n\nInitializing download...", chat_id)
        
        # Create the downloader instance (using your existing TorDownloader)
        downloader = TorDownloader("./downloads")
        
        # Track progress in a separate task
        progress_task = create_task(track_download_progress(chat_id, message_id, download_id, link))
        
        # Start the download (using your existing download method)
        file_path = await downloader.download(link, f"Manual_{download_id}")
        
        # Cancel the progress tracking
        progress_task.cancel()
        
        if not file_path or not os.path.exists(file_path):
            await editMessage(message_id, "❌ Download failed. The file could not be downloaded.", chat_id)
            return
        
        # Update status message
        await editMessage(message_id, f"✅ Download complete!\nPath: `{file_path}`\n\nPreparing to process...", chat_id)
        
        # Detect if this is an anime torrent
        filename = os.path.basename(file_path)
        is_anime = any(keyword in filename.lower() for keyword in ["anime", "episode", "ep", "seasons", "horriblesubs", "nyaa", "subsplease"])
        
        if is_anime:
            # Process as anime using your existing system
            await process_as_anime(file_path, filename, chat_id, message_id, user_id)
        else:
            # Send the file directly
            await send_file_to_user(file_path, chat_id, message_id)
        
    except Exception as e:
        logger.error(f"Error in process_download: {e}")
        await editMessage(message_id, f"❌ Error during download: {str(e)}", chat_id)

async def track_download_progress(chat_id, message_id, download_id, link):
    """Track and update the download progress periodically"""
    try:
        last_update_time = 0
        update_interval = 5  # Update progress every 5 seconds
        download_start_time = time.time()
        
        while True:
            await sleep(1)
            
            current_time = time.time()
            elapsed_time = current_time - download_start_time
            
            # Only update message in intervals to avoid API flooding
            if current_time - last_update_time >= update_interval:
                # Get progress from your TorDownloader class
                # Note: You'll need to modify TorDownloader to expose progress info
                progress = await get_download_progress(download_id)
                
                if not progress:
                    # If progress info is not available, provide a simpler message
                    progress_message = (
                        f"📥 Downloading...\n"
                        f"Link: `{link}`\n"
                        f"Time elapsed: {format_time(elapsed_time)}\n\n"
                        f"Download in progress, please wait..."
                    )
                else:
                    # Format progress message with available information
                    progress_percentage = progress.get('progress', 0)
                    download_speed = progress.get('speed', 0)
                    eta = progress.get('eta', 'Unknown')
                    
                    progress_message = (
                        f"📥 Downloading...\n"
                        f"Progress: {progress_percentage:.1f}%\n"
                        f"Speed: {download_speed:.1f} KB/s\n"
                        f"ETA: {eta}\n"
                        f"Time elapsed: {format_time(elapsed_time)}\n"
                        f"ID: `{download_id}`"
                    )
                
                # Update status message
                await editMessage(message_id, progress_message, chat_id)
                last_update_time = current_time
                
    except Exception as e:
        logger.error(f"Error in track_download_progress: {e}")

async def get_download_progress(download_id):
    """Get download progress from TorDownloader
    Note: This is a placeholder. You'll need to implement this in your TorDownloader class
    """
    # This should be implemented in your TorDownloader class
    # For now, return a dummy progress
    return None

async def process_as_anime(file_path, filename, chat_id, message_id, user_id):
    """Process the file as an anime using the existing get_animes function"""
    try:
        await editMessage(message_id, f"🎬 Detected anime content.\nProcessing: `{filename}`\n\nThis may take some time...", chat_id)
        
        # Create a TextEditor instance to parse the anime details
        text_editor = TextEditor(filename)
        
        # Run the existing anime processing function
        from bot_modules import get_animes
        await get_animes(filename, file_path, force=True)
        
        # Notify user that processing is complete
        await editMessage(message_id, f"✅ Anime processing complete for: `{filename}`\n\nCheck the main channel for the posted content.", chat_id)
        
    except Exception as e:
        logger.error(f"Error in process_as_anime: {e}")
        await editMessage(message_id, f"❌ Error during anime processing: {str(e)}", chat_id)

async def send_file_to_user(file_path, chat_id, message_id):
    """Send the downloaded file directly to the user if it's not an anime"""
    try:
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # Update status message
        await editMessage(message_id, f"📤 Preparing to upload: `{file_name}`\nSize: {format_size(file_size)}", chat_id)
        
        # Handle large files (Telegram limit is usually 2GB for bots)
        if file_size > (2 * 1024 * 1024 * 1024):  # 2GB
            await editMessage(message_id, f"❌ File too large to send directly: `{file_name}`\nSize: {format_size(file_size)}\n\nThe file is available on the server at: `{file_path}`", chat_id)
            return
            
        # For smaller files, send them directly
        await bot.send_document(
            chat_id=chat_id,
            document=file_path,
            caption=f"📎 {file_name} ({format_size(file_size)})",
            progress=upload_progress,
            progress_args=(message_id, chat_id, file_size)
        )
        
        # Final update
        await editMessage(message_id, f"✅ Upload complete: `{file_name}`", chat_id)
        
    except Exception as e:
        logger.error(f"Error in send_file_to_user: {e}")
        await editMessage(message_id, f"❌ Error during file upload: {str(e)}", chat_id)

async def upload_progress(current, total, message_id, chat_id, file_size):
    """Track and update upload progress"""
    try:
        percentage = current * 100 / total
        
        # Only update on significant progress to avoid API flooding
        if int(percentage) % 10 == 0:
            await editMessage(message_id, f"📤 Uploading...\nProgress: {percentage:.1f}%\nUploaded: {format_size(current)}/{format_size(file_size)}", chat_id)
            
    except Exception as e:
        logger.error(f"Error in upload_progress: {e}")

def format_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.1f} GB"

def format_time(seconds):
    """Format time in human-readable format"""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        return f"{int(seconds/60)} minutes, {int(seconds%60)} seconds"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours} hours, {minutes} minutes"