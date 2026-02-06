"""Over-the-Air (OTA) update mechanism."""

from __future__ import annotations

import aiohttp
import esp32
import machine

from .utils import log_error, log_info, log_warning


class OTAUpdater:
    """Handles over-the-air firmware updates."""

    def __init__(self, url: str) -> None:
        """Initialize OTA updater.

        Args:
            url: URL to check for updates

        """
        self.url = url

    async def check_for_update(self) -> dict | None:
        """Check if an update is available.

        Returns:
            Update info dict or None if no update

        """
        try:
            log_info(f"Checking for updates: {self.url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.url}/version.json") as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            log_error(f"Failed to check for update: {e}")
        return None

    async def download_and_install(self, version: str) -> bool:
        """Download and install firmware update.

        Args:
            version: Version to download

        Returns:
            True if successful, False otherwise

        """
        try:
            log_info(f"Downloading firmware version {version}...")
            
            partition = esp32.Partition(esp32.Partition.RUNNING).get_next_update()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.url}/firmware-{version}.bin") as response:
                    if response.status != 200:
                        log_error(f"Failed to download firmware: HTTP {response.status}")
                        return False

                block_size = 4096
                buf = bytearray(block_size)
                buf_mv = memoryview(buf)
                buf_idx = 0
                block_num = 0
                
                reader = response.content
                
                while True:
                    chunk = await reader.read(1024)
                    if not chunk:
                        break
                        
                    chunk_len = len(chunk)
                    chunk_idx = 0
                    while chunk_idx < chunk_len:
                        to_copy = min(block_size - buf_idx, chunk_len - chunk_idx)
                        buf_mv[buf_idx : buf_idx + to_copy] = chunk[chunk_idx : chunk_idx + to_copy]
                        buf_idx += to_copy
                        chunk_idx += to_copy
                        
                        if buf_idx == block_size:
                            partition.ioctl(6, block_num)
                            partition.writeblocks(block_num, buf)
                            block_num += 1
                            buf_idx = 0

                if buf_idx > 0:
                    for i in range(buf_idx, block_size):
                        buf[i] = 0xFF
                    partition.ioctl(6, block_num)
                    partition.writeblocks(block_num, buf)

                partition.set_boot()
                return True

        except Exception as e:
            log_error(f"Failed to download/install update: {e}")
            return False

    async def perform_update(self) -> None:
        """Check for and perform update if available."""
        update_info = await self.check_for_update()
        if update_info:
            from .version import __version__

            remote_version = update_info.get("version")
            if remote_version and remote_version != __version__:
                log_info(f"Update available: {__version__} -> {remote_version}")
                if await self.download_and_install(remote_version):
                    log_info("Update installed, rebooting...")
                    machine.reset()
            else:
                log_info("Already on latest version")
        else:
            log_warning("No update information available")
