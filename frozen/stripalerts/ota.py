"""Over-the-Air (OTA) update mechanism."""
from __future__ import annotations

import contextlib

with contextlib.suppress(ImportError):
    pass

import aiohttp
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
            async with aiohttp.ClientSession() as session, session.get(
                f"{self.url}/firmware-{version}.bin"
            ) as response:
                if response.status != 200:
                    log_error(
                        f"Failed to download firmware: HTTP {response.status}"
                    )
                    return False

                log_warning("OTA installation not fully implemented yet")
                return False

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
