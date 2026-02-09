"""WiFi connection management."""

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
        self.sta.active(True)  # noqa: FBT003
        log_info("WiFi station mode enabled")

    def disable_sta(self) -> None:
        """Disable station mode."""
        self.sta.active(False)  # noqa: FBT003
        log_info("WiFi station mode disabled")

    def enable_ap(self, ssid: str, password: str = "") -> None:
        """Enable access point mode.

        Args:
            ssid: SSID for access point
            password: Password (optional)

        """
        self.ap.active(True)  # noqa: FBT003

        if password:
            self.ap.config(
                essid=ssid, password=password, authmode=network.AUTH_WPA_WPA2_PSK
            )
        else:
            self.ap.config(essid=ssid, authmode=network.AUTH_OPEN)

        log_info(f"WiFi AP '{ssid}' enabled")

    def disable_ap(self) -> None:
        """Disable access point mode."""
        self.ap.active(False)  # noqa: FBT003
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
            self._connected = False
            log_info("Disconnected from WiFi")

    async def scan(self) -> list:
        """Scan for available WiFi networks.

        Returns:
            List of dictionaries containing network info:
            [{'ssid': 'name', 'rssi': -60, 'auth': 3}, ...]

        """
        self.enable_sta()
        try:
            log_info("Scanning for networks...")
            # scan() blocks for a bit, but that's usually okay in MP if not too long
            # async scan is not always available or consistent across ports
            networks = self.sta.scan()
            unique_nets: dict[str, dict] = {}

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

    def is_connected(self) -> bool:
        """Check if connected to WiFi.

        Returns:
            True if connected, False otherwise

        """
        return self.sta.isconnected()

    def get_ip(self) -> "str | None":
        """Get current IP address.

        Returns:
            IP address string or None if not connected

        """
        if self.sta.isconnected():
            try:
                ip_config = self.sta.ifconfig()
                return str(ip_config[0])
            except Exception:
                pass
        return None

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
