"""Bluetooth Low Energy (BLE) services and characteristics."""

import asyncio

import aioble

from .utils import log_error, log_info


class BLEManager:
    """Manages BLE services and characteristics using aioble."""

    def __init__(self, name: str = "StripAlerts") -> None:
        """Initialize BLE manager.

        Args:
            name: Device name for BLE advertisement

        """
        self.name = name
        self._connection = None
        self._running = False
        log_info(f"BLE manager initialized: {name}")

    async def advertise_and_wait(self) -> None:
        """Advertise and wait for a connection."""
        while self._running:
            try:
                log_info(f"BLE advertising as '{self.name}'")
                async with await aioble.advertise(
                    interval_us=250000,
                    name=self.name,
                    services=[],
                ) as connection:
                    self._connection = connection
                    log_info(f"BLE connected: {connection.device}")

                    # Wait for disconnection
                    await connection.disconnected()
                    log_info("BLE disconnected")
                    self._connection = None

            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(f"BLE error: {e}")
                await asyncio.sleep(1)

    def is_connected(self) -> bool:
        """Check if a BLE device is connected.

        Returns:
            True if connected, False otherwise

        """
        return self._connection is not None

    async def start(self) -> None:
        """Start BLE advertising."""
        self._running = True
        await self.advertise_and_wait()

    def stop(self) -> None:
        """Stop BLE advertising."""
        self._running = False
        if self._connection:
            try:
                self._connection.disconnect()
            except Exception as e:
                log_error(f"Error disconnecting BLE: {e}")
        log_info("BLE stopped")

    def deinit(self) -> None:
        """Deinitialize BLE."""
        self.stop()
        log_info("BLE deinitialized")
