"""Bluetooth Low Energy (BLE) services for provisioning."""

import asyncio
import json

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    pass

import aioble
import bluetooth

from micropython import const

from .config import settings
from .constants import BLE_MAX_NETWORKS_LIST, BLE_MAX_PAYLOAD_SIZE
from .utils import log_error, log_info

_SERVICE_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_SSID = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_PASS = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_API = bluetooth.UUID("6e400004-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_STATUS = bluetooth.UUID("6e400005-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_NETWORKS = bluetooth.UUID("6e400006-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_WIFITEST = bluetooth.UUID("6e400007-b5a3-f393-e0a9-e50e24dcca9e")

_FLAG_START = const(0x01)
_FLAG_APPEND = const(0x02)


def decode_utf8(data):
    """Decode UTF-8 data to string.

    Args:
        data: Bytes or string data to decode

    Returns:
        Decoded string or empty string on error

    """
    try:
        if isinstance(data, (bytes, bytearray)):
            return data.decode("utf-8")
        return str(data)
    except Exception:
        return ""


class BLEManager:
    """Manages BLE provisioning and WiFi configuration."""

    def __init__(self, wifi_manager, name="StripAlerts-Setup", initial_networks=None):
        """Initialize BLE manager.

        Args:
            wifi_manager: WiFi manager instance
            name: BLE device name for advertising
            initial_networks: Optional list of cached networks

        """
        self.wifi = wifi_manager
        self.name = name
        self.cached_networks = initial_networks if initial_networks else []
        self._connection = None
        self._tasks = []
        self._buffers = {
            _CHAR_SSID: bytearray(),
            _CHAR_PASS: bytearray(),
            _CHAR_API: bytearray(),
            _CHAR_WIFITEST: bytearray(),
        }
        self._debounce_events = {}

        # Service Definition
        self.service = aioble.Service(_SERVICE_UUID)

        self.char_ssid = aioble.Characteristic(self.service, _CHAR_SSID, write=True, capture=True)
        self.char_pass = aioble.Characteristic(self.service, _CHAR_PASS, write=True, capture=True)
        self.char_api = aioble.Characteristic(self.service, _CHAR_API, write=True, capture=True)
        self.char_status = aioble.Characteristic(self.service, _CHAR_STATUS, read=True, notify=True)
        self.char_networks = aioble.Characteristic(
            self.service, _CHAR_NETWORKS, read=True, notify=True
        )
        self.char_wifitest = aioble.Characteristic(
            self.service,
            _CHAR_WIFITEST,
            read=True,
            write=True,
            notify=True,
            capture=True,
        )

        aioble.register_services(self.service)
        log_info(f"BLE Service registered: {_SERVICE_UUID}")

    def _apply_buffer_to_settings(self, uuid, config_key) -> None:
        if not self._buffers[uuid]:
            return

        try:
            decoded = self._buffers[uuid].decode("utf-8")
        except Exception:
            return

        settings[config_key] = decoded

    def _flush_pending_writes(self) -> None:
        """Apply latest buffered values immediately."""
        key_map = {
            _CHAR_SSID: "wifi_ssid",
            _CHAR_PASS: "wifi_password",
            _CHAR_API: "api_url",
        }

        for uuid, config_key in key_map.items():
            self._apply_buffer_to_settings(uuid, config_key)

    def _has_required_config(self) -> bool:
        return bool(settings["wifi_ssid"]) and bool(settings["api_url"])

    async def start(self):
        """Start advertising and handling connections."""
        log_info("Starting BLE task...")
        # Start handler tasks
        self._tasks = [
            asyncio.create_task(self._monitor_write(self.char_ssid, "wifi_ssid")),
            asyncio.create_task(self._monitor_write(self.char_pass, "wifi_password")),
            asyncio.create_task(self._monitor_write(self.char_api, "api_url")),
            asyncio.create_task(self._monitor_wifi_test()),
        ]

        try:
            # Main advertising loop
            while True:
                try:
                    log_info(f"BLE Advertising as {self.name}")
                    async with await aioble.advertise(
                        interval_us=250000,
                        name=self.name,
                        services=[_SERVICE_UUID],
                    ) as connection:
                        self._connection = connection
                        log_info(f"BLE Connected: {connection.device}")

                        # On connection, immediately send cached or fresh networks
                        self._tasks.append(
                            asyncio.create_task(self._send_networks(allow_cache=True))
                        )

                        await connection.disconnected()
                        self._connection = None
                        log_info("BLE Disconnected")
                except asyncio.CancelledError:  # noqa: PERF203 - Must re-raise to properly cancel
                    raise
                except Exception as e:
                    log_error(f"BLE Advertise error: {e}")
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            log_info("BLE task cancelled")
        finally:
            for t in self._tasks:
                t.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks = []

    async def _monitor_write(self, char, config_key):
        """Monitor characteristic for writes and update config."""
        uuid = char.uuid
        self._debounce_events[uuid] = asyncio.Event()

        async def _save_worker():
            try:
                while True:
                    await self._debounce_events[uuid].wait()
                    self._debounce_events[uuid].clear()

                    # Debounce: Wait until silence for 0.5s
                    while True:
                        await asyncio.sleep(0.5)
                        if self._debounce_events[uuid].is_set():
                            self._debounce_events[uuid].clear()
                            continue
                        break

                    # Update setting
                    try:
                        decoded = self._buffers[uuid].decode("utf-8")
                        settings[config_key] = decoded
                        val_log = "***" if "password" in config_key else decoded[:10]
                        log_info(f"Updated {config_key}: {val_log}...")
                    except Exception:
                        pass
            except asyncio.CancelledError:
                pass

        worker_task = asyncio.create_task(_save_worker())
        self._tasks.append(worker_task)

        while True:
            try:
                _conn, value = await char.written()
                if not value or len(value) < 1:
                    continue

                flag = value[0]
                data = value[1:]

                if flag == _FLAG_START:
                    self._buffers[uuid] = bytearray(data)
                elif flag == _FLAG_APPEND:
                    self._buffers[uuid].extend(data)
                else:
                    continue

                # Signal update
                self._debounce_events[uuid].set()

            except Exception as e:
                log_error(f"Write error on {config_key}: {e}")

    async def _monitor_wifi_test(self):
        """Listen for WiFi test commands."""
        while True:
            try:
                _conn, value = await self.char_wifitest.written()
                if not value or len(value) < 1:
                    continue

                flag = value[0]
                data = value[1:]
                uuid = _CHAR_WIFITEST

                if flag == _FLAG_START:
                    self._buffers[uuid] = bytearray(data)
                elif flag == _FLAG_APPEND:
                    self._buffers[uuid].extend(data)

                try:
                    command = self._buffers[uuid].decode("utf-8").strip().lower()
                except Exception:
                    continue

                log_info(f"Received command: {command}")

                if command == "rescan":
                    await self._send_networks(allow_cache=False)

                elif command == "test":
                    await self._notify_status("Testing WiFi...")
                    # Notify logic in app.js expects "success" or "failed"

                    self._flush_pending_writes()

                    ssid = settings["wifi_ssid"]
                    password = settings["wifi_password"]

                    if not ssid:
                        await self._write_test_result("failed")
                        continue

                    # Try to connect
                    success = await self.wifi.connect(ssid, password)
                    if success:
                        await self._write_test_result("success")
                    else:
                        await self._notify_status("WiFi failed")
                        await self._write_test_result("failed")

                elif command == "save":
                    # Persist settings to disk
                    await self._notify_status("Saving")
                    self._flush_pending_writes()

                    if not self._has_required_config():
                        await self._notify_status("Save failed: missing fields")
                        continue

                    settings.save()
                    await self._notify_status("Saved")
                    log_info("Configuration complete. Rebooting in 3s...")
                    await asyncio.sleep(3)
                    import machine

                    machine.reset()

            except Exception as e:
                log_error(f"Command Error: {e}")

    async def _write_test_result(self, result):
        """Write result to wifiTest char and notify."""
        self.char_wifitest.write(result.encode("utf-8"))
        if self._connection:
            self.char_wifitest.notify(self._connection)

    async def _send_networks(self, *, allow_cache: bool = False):
        """Scan and send networks."""
        networks = []  # type: list[dict]

        if allow_cache and self.cached_networks:
            log_info("Using cached networks")
            networks = self.cached_networks
            # Clear cache so next request (e.g. rescan button) forces fresh scan
            self.cached_networks = []
        else:
            await self._notify_status("Scanning Networks...")
            networks = await self.wifi.scan()

        try:
            # Prepare networks list, fitting into one BLE packet
            simple_list = []  # type: list[dict]
            for n in networks:
                entry = {"ssid": n["ssid"], "rssi": n["rssi"]}
                temp_list = simple_list + [entry]
                json_str = json.dumps(temp_list)

                # Check length using safe BLE payload limit
                if len(json_str) > BLE_MAX_PAYLOAD_SIZE:
                    break

                simple_list.append(entry)
                if len(simple_list) >= BLE_MAX_NETWORKS_LIST:
                    break

            json_str = json.dumps(simple_list)

            # MTU size varies by device/stack; keep payload small.
            encoded = json_str.encode("utf-8")
            self.char_networks.write(encoded)
            if self._connection:
                self.char_networks.notify(self._connection)

            await self._notify_status("Scan Complete")

            # Signal that we are ready for user interaction
            await asyncio.sleep(0.5)
            await self._notify_status("Ready")
        except Exception as e:
            log_error(f"Send networks error: {e}")
            await self._notify_status("Ready")

    async def _notify_status(self, message):
        """Send status update."""
        log_info(f"BLE Status: {message}")
        try:
            self.char_status.write(message.encode("utf-8"))
            if self._connection:
                self.char_status.notify(self._connection)
        except Exception as e:
            log_error(f"Notify error: {e}")
