import asyncio
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove
from aiohttp import ClientSession
from torrentp import TorrentDownloader
from bot.core.func_utils import handle_logs
import os
import time
import libtorrent as lt
import logging

logger = logging.getLogger(__name__)

# Dictionary to store active downloads and their progress
active_downloads = {}

class TorDownloader:
    def __init__(self, save_path):
        self.save_path = save_path
        os.makedirs(self.save_path, exist_ok=True)
        
    async def download(self, link, name=None):
        """Download a torrent or magnet link and return the file path"""
        download_id = f"dl_{int(time.time())}"
        
        if link.startswith('magnet:?'):
            return await self._download_magnet(link, download_id, name)
        elif link.startswith('http'):
            return await self._download_torrent(link, download_id, name)
        else:
            logger.error("Invalid link format")
            return None
    
    async def _download_magnet(self, magnet_link, download_id, name=None):
        """Download from magnet link with progress tracking"""
        try:
            # Create libtorrent session
            ses = lt.session()
            ses.listen_on(6881, 6891)
            
            # Add magnet link to session
            params = lt.parse_magnet_uri(magnet_link)
            params.save_path = self.save_path
            torrent_handle = ses.add_torrent(params)
            
            # Register download in active downloads
            active_downloads[download_id] = {
                'handle': torrent_handle,
                'progress': 0,
                'speed': 0,
                'eta': 'Unknown',
                'cancelled': False,
                'name': name or 'Unknown'
            }
            
            # Wait for download to complete with progress tracking
            file_path = await self._wait_for_download(ses, torrent_handle, download_id)
            return file_path
            
        except Exception as e:
            logger.error(f"Error in _download_magnet: {e}")
            if download_id in active_downloads:
                del active_downloads[download_id]
            return None
    
    async def _download_torrent(self, torrent_url, download_id, name=None):
        """Download from torrent URL with progress tracking"""
        try:
            import requests
            
            # Download torrent file
            response = requests.get(torrent_url)
            if response.status_code != 200:
                logger.error(f"Failed to download torrent file: {response.status_code}")
                return None
            
            # Save torrent file
            torrent_path = os.path.join(self.save_path, f"temp_{download_id}.torrent")
            with open(torrent_path, "wb") as f:
                f.write(response.content)
            
            # Create libtorrent session
            ses = lt.session()
            ses.listen_on(6881, 6891)
            
            # Add torrent to session
            info = lt.torrent_info(torrent_path)
            torrent_handle = ses.add_torrent({'ti': info, 'save_path': self.save_path})
            
            # Register download in active downloads
            active_downloads[download_id] = {
                'handle': torrent_handle,
                'progress': 0,
                'speed': 0,
                'eta': 'Unknown',
                'cancelled': False,
                'name': name or info.name()
            }
            
            # Wait for download to complete with progress tracking
            file_path = await self._wait_for_download(ses, torrent_handle, download_id)
            
            # Clean up temporary torrent file
            os.remove(torrent_path)
            return file_path
            
        except Exception as e:
            logger.error(f"Error in _download_torrent: {e}")
            if download_id in active_downloads:
                del active_downloads[download_id]
            return None
    
    async def _wait_for_download(self, session, handle, download_id):
        """Wait for download to complete with progress tracking"""
        try:
            while True:
                # Check if download was cancelled
                if download_id in active_downloads and active_downloads[download_id]['cancelled']:
                    session.remove_torrent(handle, True)  # True to also delete files
                    if download_id in active_downloads:
                        del active_downloads[download_id]
                    return None
                
                # Get torrent status
                status = handle.status()
                
                # Calculate progress
                progress = status.progress * 100
                download_speed = status.download_rate / 1024  # KB/s
                
                # Calculate ETA
                eta = "Unknown"
                if download_speed > 0:
                    remaining_bytes = (1 - status.progress) * status.total_wanted
                    seconds_left = remaining_bytes / status.download_rate
                    eta = self._format_time(seconds_left)
                
                # Update active_downloads dictionary
                if download_id in active_downloads:
                    active_downloads[download_id].update({
                        'progress': progress,
                        'speed': download_speed,
                        'eta': eta,
                        'name': handle.name() if handle.has_metadata() else active_downloads[download_id]['name']
                    })
                
                # Check if download is complete
                if status.is_seeding or progress >= 99.9:
                    # Download is complete
                    file_path = os.path.join(self.save_path, handle.name())
                    
                    # Remove download from active_downloads
                    if download_id in active_downloads:
                        del active_downloads[download_id]
                    
                    return file_path
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in _wait_for_download: {e}")
            if download_id in active_downloads:
                del active_downloads[download_id]
            return None
    
    @staticmethod
    def _format_time(seconds):
        """Format time in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            return f"{int(seconds/60)} minutes, {int(seconds%60)} seconds"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours} hours, {minutes} minutes"
    
    @staticmethod
    def get_progress(download_id=None):
        """Get progress for a specific download or all downloads"""
        if download_id:
            download_info = active_downloads.get(download_id)
            if download_info:
                return {
                    'progress': download_info['progress'],
                    'speed': download_info['speed'],
                    'eta': download_info['eta'],
                    'name': download_info['name']
                }
            return None
        
        return {
            download_id: {
                'progress': info['progress'],
                'speed': info['speed'],
                'eta': info['eta'],
                'name': info['name']
            }
            for download_id, info in active_downloads.items()
        }
    
    @staticmethod
    def cancel_download(download_id):
        """Cancel an active download"""
        if download_id in active_downloads:
            active_downloads[download_id]['cancelled'] = True
            return True
        return False