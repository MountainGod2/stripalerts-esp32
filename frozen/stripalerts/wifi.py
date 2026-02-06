"""WiFi connection management."""

from __future__ import annotations

import contextlib

with contextlib.suppress(ImportError):
    pass

import asyncio

import network
from micropython import const

from .constants import WIFI_CONNECT_TIMEOUT
from .utils import log_error, log_info

# Connection check interval
_CONNECT_CHECK_INTERVAL_MS = const(100)


class WiFiManager:
    """Manages WiFi connections."""

    def __init__(self) -> None:
        """Initialize WiFi manager."""
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self._connected = False

    def enable_sta(self) -> None:
        """Enable station mode."""
        self.sta.active(is_active=True)
        log_info("WiFi station mode enabled")

    def disable_sta(self) -> None:
        """Disable station mode."""
        self.sta.active(is_active=False)
        log_info("WiFi station mode disabled")

    def enable_ap(self, ssid: str, password: str = "") -> None:
        """Enable access point mode.

        Args:
            ssid: SSID for access point
            password: Password (optional)

        """
        self.ap.active(is_active=True)

        if password:
            self.ap.config(
                essid=ssid, password=password, authmode=network.AUTH_WPA_WPA2_PSK
            )
        else:
            self.ap.config(essid=ssid, authmode=network.AUTH_OPEN)

        log_info(f"WiFi AP '{ssid}' enabled")

    def disable_ap(self) -> None:
        """Disable access point mode."""
        self.ap.active(is_active=False)
        log_info("WiFi AP mode disabled")

    async def connect(
        self, ssid: str, password: str, timeout: int = WIFI_CONNECT_TIMEOUT
    ) -> bool:
        """Connect to WiFi network.

        Args:
            ssid: Network SSID
            password: Network password
            timeout: Connection timeout in seconds

        Returns:
            True if connected, False otherwise

        """
        self.enable_sta()

        if self.sta.isconnected():
            log_info("Already connected to WiFi")
            self._connected = True
            return True

        log_info(f"Connecting to WiFi: {ssid}")
        self.sta.config(reconnects=3)
        self.sta.connect(ssid, password)

        iterations = (timeout * 1000) // _CONNECT_CHECK_INTERVAL_MS
        for _ in range(iterations):
            if self.sta.isconnected():
                ip_addr = self.sta.ifconfig()[0]
                log_info(f"Connected! IP: {ip_addr}")
                self._connected = True
                return True
            await asyncio.sleep_ms(_CONNECT_CHECK_INTERVAL_MS)

        log_error(f"Failed to connect to WiFi: {ssid}")
        self._connected = False
        return False

    def disconnect(self) -> None:
        """Disconnect from WiFi."""
        if self.sta.isconnected():
            self.sta.disconnect()
            log_info("Disconnected from WiFi")
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to WiFi.

        Returns:
            True if connected, False otherwise

        """
        return self.sta.isconnected()

    def get_ip(self) -> str | None:
        """Get current IP address.

        Returns:
            IP address string or None if not connected

        """
        if self.sta.isconnected():
            ip_config = self.sta.ipconfig("addr4")
            if ip_config:
                return str(ip_config[0])
        return None

    def scan(self) -> list:
        """Scan for available networks.

        Returns:
            List of tuples (ssid, rssi) for available networks

        """
        self.enable_sta()
        log_info("Scanning for networks...")
        try:
            networks = self.sta.scan()
            return [(net[0].decode("utf-8"), net[3]) for net in networks]
        except Exception as e:
            log_error(f"WiFi scan failed: {e}")
            return []

    def get_status(self) -> list:
        """Get WiFi connection status.

        Returns:
            Status code (network.STAT_* constants)

        """
        return self.sta.status()

    def get_mac(self) -> list:
        """Get the MAC address of the WiFi interface.

        Returns:
            MAC address as list of integers

        """
        return self.sta.config("mac")
