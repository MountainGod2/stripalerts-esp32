"""WiFi connection management."""

import asyncio

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import Optional, TypedDict

    import machine

    class NetworkInfo(TypedDict):
        """WiFi network information."""

        ssid: str
        rssi: int
        auth: int
else:
    NetworkInfo = dict

import network

from micropython import const

from .constants import WIFI_CONNECT_TIMEOUT
from .utils import log_error, log_info

_CONNECT_CHECK_INTERVAL_MS = const(100)


class WiFiManager:
    """Manages WiFi connections."""

    def __init__(self) -> None:
        """Initialize WiFi manager."""
        self.sta = network.WLAN(network.STA_IF)

    async def monitor(
        self,
        ssid: str = "",
        password: str = "",
        *,
        timeout: int = WIFI_CONNECT_TIMEOUT,
        attempts_before_reset: int = 3,
        wdt=None,
        max_cycles: int | None = None,
    ) -> None:
        """Keep the STA link alive and trigger a reset after repeated failure."""
        if not ssid:
            return

        failures = 0
        cycles = 0
        while True:
            if max_cycles is not None and cycles >= max_cycles:
                return

            await asyncio.sleep(5)
            cycles += 1

            if self.sta.isconnected():
                failures = 0
                continue

            failures += 1
            log_error(f"WiFi link lost ({failures}/{attempts_before_reset})")
            if not await self.connect(ssid, password, timeout=timeout, wdt=wdt):
                if failures >= attempts_before_reset:
                    log_error("Too many WiFi failures; resetting device")
                    try:
                        import machine

                        if hasattr(machine, "reset"):
                            machine.reset()
                        else:
                            raise RuntimeError("No reset available")
                    except Exception as exc:
                        log_error(f"WiFi recovery reset failed: {exc}")
                        raise RuntimeError("WiFi recovery failed")
                continue

            failures = 0

    def _current_ssid(self) -> str:
        """Return the currently connected SSID when available."""
        try:
            value = self.sta.config("essid")
        except Exception:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value or "")

    def enable_sta(self) -> None:
        """Enable station mode."""
        self.sta.active(True)  # noqa: FBT003 - MicroPython API requires positional bool
        log_info("WiFi station mode enabled")

    async def connect(
        self,
        ssid: str,
        password: str,
        timeout: int = WIFI_CONNECT_TIMEOUT,
        wdt: "Optional[machine.WDT]" = None,
    ) -> bool:
        """Connect to WiFi network.

        Args:
            ssid: Network SSID
            password: Network password
            timeout: Connection timeout in seconds
            wdt: Optional watchdog timer to feed during connection

        Returns:
            True if connected to the requested SSID, False otherwise

        """
        self.enable_sta()

        current_ssid = self._current_ssid()
        if self.sta.isconnected() and current_ssid == ssid:
            log_info(f"Already connected to WiFi: {ssid}")
            return True

        if self.sta.isconnected() and current_ssid:
            log_info(f"Disconnecting from {current_ssid} before connecting to {ssid}")
            self.sta.disconnect()

        log_info(f"Connecting to WiFi: {ssid}")
        self.sta.config(reconnects=3)
        self.sta.connect(ssid, password)

        iterations = (timeout * 1000) // _CONNECT_CHECK_INTERVAL_MS
        for _ in range(iterations):
            if wdt:
                wdt.feed()
            if self.sta.isconnected() and self._current_ssid() == ssid:
                ip_addr = self.sta.ifconfig()[0]
                log_info(f"Connected! IP: {ip_addr}")
                return True
            await asyncio.sleep(_CONNECT_CHECK_INTERVAL_MS / 1000)

        log_error(f"Failed to connect to WiFi: {ssid}")
        return False

    async def scan(self) -> "list[NetworkInfo]":
        """Scan for available WiFi networks.

        Returns:
            List of NetworkInfo dictionaries containing network info:
            [{'ssid': 'name', 'rssi': -60, 'auth': 3}, ...]

        """
        self.enable_sta()
        try:
            log_info("Scanning for networks...")
            # scan() blocks for a bit, but that's usually okay in MP if not too long
            # async scan is not always available or consistent across ports
            networks = self.sta.scan()
            unique_nets: "dict[str, NetworkInfo]" = {}

            for n in networks:
                ssid = n[0].decode("utf-8")
                if not ssid:
                    continue
                rssi = n[3]
                authmode = n[4]

                # Keep strongest signal for dupes
                if ssid not in unique_nets or unique_nets[ssid]["rssi"] < rssi:
                    unique_nets[ssid] = {"ssid": ssid, "rssi": rssi, "auth": authmode}

            # Sort by RSSI
            return sorted(unique_nets.values(), key=lambda x: x["rssi"], reverse=True)

        except Exception as e:
            log_error(f"Scan failed: {e}")
            return []
