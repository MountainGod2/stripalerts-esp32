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
            True if connected, False otherwise

        """
        self.enable_sta()

        if self.sta.isconnected():
            log_info("Already connected to WiFi")
            return True

        log_info(f"Connecting to WiFi: {ssid}")
        self.sta.config(reconnects=3)
        self.sta.connect(ssid, password)

        iterations = (timeout * 1000) // _CONNECT_CHECK_INTERVAL_MS
        for _ in range(iterations):
            if wdt:
                wdt.feed()
            if self.sta.isconnected():
                ip_addr = self.sta.ifconfig()[0]
                log_info(f"Connected! IP: {ip_addr}")
                return True
            await asyncio.sleep_ms(_CONNECT_CHECK_INTERVAL_MS)

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
