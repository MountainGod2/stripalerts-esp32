"""Bluetooth Low Energy (BLE) services for provisioning."""

import asyncio
import json

import aioble
import bluetooth
from micropython import const

from .config import settings
from .utils import log_error, log_info

# UUIDs
_SERVICE_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_SSID = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_PASS = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_API = bluetooth.UUID("6e400004-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_STATUS = bluetooth.UUID("6e400005-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_NETWORKS = bluetooth.UUID("6e400006-b5a3-f393-e0a9-e50e24dcca9e")
_CHAR_WIFITEST = bluetooth.UUID("6e400007-b5a3-f393-e0a9-e50e24dcca9e")

# Flags for chunked writes
_FLAG_START = const(0x01)
_FLAG_APPEND = const(0x02)


def decode_utf8(data):
    try:
        if isinstance(data, (bytes, bytearray)):
            return data.decode("utf-8")
        return str(data)
    except Exception:
        return ""


class BLEManager:
    def __init__(self, app_instance, name="StripAlerts-Setup"):
        self.app = app_instance
        self.name = name
        self._connection = None
        self._buffers = {
            _CHAR_SSID: bytearray(),
            _CHAR_PASS: bytearray(),
            _CHAR_API: bytearray(),
            _CHAR_WIFITEST: bytearray(),
        }

        # Service Definition
        self.service = aioble.Service(_SERVICE_UUID)

        self.char_ssid = aioble.Characteristic(
            self.service, _CHAR_SSID, write=True, capture=True
        )
        self.char_pass = aioble.Characteristic(
            self.service, _CHAR_PASS, write=True, capture=True
        )
        self.char_api = aioble.Characteristic(
            self.service, _CHAR_API, write=True, capture=True
        )
        self.char_status = aioble.Characteristic(
            self.service, _CHAR_STATUS, read=True, notify=True
        )
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

    async def start(self):
        """Start advertising and handling connections."""
        log_info("Starting BLE task...")
        # Start handler tasks
        asyncio.create_task(self._monitor_write(self.char_ssid, "wifi_ssid"))
        asyncio.create_task(self._monitor_write(self.char_pass, "wifi_password"))
        asyncio.create_task(self._monitor_write(self.char_api, "api_url"))
        asyncio.create_task(self._monitor_wifi_test())

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

                    # On connection, maybe send current status or networks?
                    # Trigger a background scan and send networks
                    asyncio.create_task(self._send_networks())

                    await connection.disconnected()
                    self._connection = None
                    log_info("BLE Disconnected")
            except asyncio.CancelledError:
                log_info("BLE task cancelled")
                break
            except Exception as e:
                log_error(f"BLE Advertise error: {e}")
                await asyncio.sleep(1)

    async def _monitor_write(self, char, config_key):
        """Monitor characteristic for writes and update config."""
        uuid = char.uuid
        while True:
            try:
                conn, value = await char.written()
                if not value or len(value) < 1:
                    continue

                flag = value[0]
                data = value[1:]

                if flag == _FLAG_START:
                    self._buffers[uuid] = bytearray(data)
                elif flag == _FLAG_APPEND:
                    self._buffers[uuid].extend(data)

                try:
                    decoded = self._buffers[uuid].decode("utf-8")
                    settings[config_key] = decoded
                    # Do not save on every chunk to avoid flash wear

                    val_log = "***" if "password" in config_key else decoded[:10]
                    log_info(f"Updated {config_key}: {val_log}...")
                except Exception:
                    # Might be incomplete UTF-8 if split mid-multibyte
                    pass

            except Exception as e:
                log_error(f"Write error on {config_key}: {e}")

    async def _monitor_wifi_test(self):
        """Listen for WiFi test commands."""
        while True:
            try:
                conn, value = await self.char_wifitest.written()
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
                    await self._send_networks()

                elif command == "test":
                    await self._notify_status("Testing WiFi...")
                    # Notify logic in app.js expects "success" or "failed"
                    # for the TEST result
                    # BUT it *also* listens to status updates for UI.
                    # Wait, onWifiTestNotify checks for "success" / "failed".

                    ssid = settings["wifi_ssid"]
                    password = settings["wifi_password"]

                    if not ssid:
                        await self._write_test_result("failed")
                        continue

                    # Try to connect
                    success = await self.app.wifi.connect(ssid, password)
                    if success:
                        await self._write_test_result("success")
                    else:
                        await self._notify_status("WiFi failed")
                        await self._write_test_result("failed")

                elif command == "save":
                    # Persist settings to disk
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

    async def _send_networks(self):
        """Scan and send networks."""
        await self._notify_status("Scanning Networks...")
        networks = await self.app.wifi.scan()

        try:
            # Prepare networks list, fitting into one BLE packet (max ~250 bytes)
            # Frontend only displays top 5 anyway.
            simple_list: list[dict] = []
            for n in networks:
                # Build entry (auth is unused by frontend, omitting to save space)
                entry = {"ssid": n["ssid"], "rssi": n["rssi"]}

                # Test if adding this keeps us under the limit
                temp_list = simple_list + [entry]
                json_str = json.dumps(temp_list)

                # Check length (using 240 as safe limit for default MTU/packet size)
                if len(json_str) > 240:
                    break

                simple_list.append(entry)
                if len(simple_list) >= 5:
                    break

            json_str = json.dumps(simple_list)

            # Send as one chunk if possible, otherwise truncate/split?
            # Assuming MTU ~512 on ESP32 S3, this might fit.
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
