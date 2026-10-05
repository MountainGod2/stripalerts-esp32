"""Unit tests for the StripAlerts firmware (App, API, BLE, Config, WiFi).

Async tests run under pytest-asyncio in ``auto`` mode (see ``pytest.ini``).
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import os
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.stripalerts import config as config_module
from modules.stripalerts.api import ChaturbateAPI
from modules.stripalerts.app import App
from modules.stripalerts.ble import _CHAR_SSID, BLEManager
from modules.stripalerts.config import Config, settings
from modules.stripalerts.constants import MAX_WIFI_SSID_LEN
from modules.stripalerts.events import EventManager
from modules.stripalerts.wifi import WiFiManager

EVENTS_URL = "https://events.example.com/events/test/"


# --- Fakes -----------------------------------------------------------------


class FakeLED:
    def __init__(self):
        self.pattern = None
        self.rainbow_hue = 0

    def set_pattern(self, pattern):
        self.pattern = pattern

    async def run(self):
        return None


class FakeWLAN:
    """Associated with 'old'; only connects to 'target' with password 'correct'."""

    def __init__(self):
        self.disconnect_calls = 0
        self.connected = True
        self.connected_ssid = "old"
        self.last_requested = "old"

    def active(self, value=None):
        return value

    def isconnected(self):
        return self.connected and self.connected_ssid == self.last_requested

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False
        self.connected_ssid = None

    def config(self, key=None, **_kwargs):
        return self.connected_ssid if key == "essid" else None

    def connect(self, ssid, password):
        self.last_requested = ssid
        self.connected = (ssid, password) == ("target", "correct")
        if self.connected:
            self.connected_ssid = ssid

    def ifconfig(self):
        return ("10.0.0.7",)


class DroppingWLAN:
    """Starts disconnected; connects only with the 'recovery'/'secret' credentials."""

    def __init__(self):
        self.connected = False
        self.connect_calls = []

    def active(self, value=None):
        return True

    def config(self, *_args, **_kwargs):
        return None

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        self.connected = (ssid, password) == ("recovery", "secret")

    def disconnect(self):
        self.connected = False

    def isconnected(self):
        return self.connected

    def ifconfig(self):
        return ("10.0.0.5",)


# --- Helpers ---------------------------------------------------------------


async def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    """Yield to the event loop until ``predicate()`` is true, or fail after ``timeout``."""

    async def poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(poll(), timeout)


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def app():
    """A bare ``App`` (no hardware init) with just the attributes tip handling needs."""
    instance = object.__new__(App)
    instance.led = FakeLED()
    instance._current_effect_task = None
    instance._current_hold_color = None
    instance._process_tip_effect = AsyncMock()
    return instance


@pytest.fixture
def api():
    return ChaturbateAPI(EVENTS_URL, EventManager())


@pytest.fixture
def wifi():
    return WiFiManager()


@pytest.fixture
def ble(wifi):
    return BLEManager(wifi_manager=wifi)


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Point the config module at a temporary file and return its path."""
    path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", str(path))
    return path


# --- App -------------------------------------------------------------------


@pytest.mark.parametrize("message", [None, 123], ids=["none", "non-string"])
async def test_tip_message_is_normalized_without_crashing(app, message):
    await app._handle_tip({"tokens": 35, "message": message})


@pytest.mark.parametrize(
    "payload",
    [{"method": "tip", "object": None}, {"method": "tip", "object": {"tip": None}}],
    ids=["null-object", "null-tip"],
)
async def test_tip_event_with_missing_or_null_object_does_not_crash(app, payload):
    await app._handle_api_event(payload)


def test_app_prunes_done_tasks_without_task_exception_api():
    app = object.__new__(App)
    app._tasks = [SimpleNamespace(done=lambda: True)]

    app._prune_done_tasks()

    assert app._tasks == []


async def test_start_creates_watchdog_before_setup():
    app = App()
    app.settings = None
    app.wdt = None
    wdt_seen_in_setup = []

    async def fake_setup():
        wdt_seen_in_setup.append(app.wdt)

    app.setup = fake_setup
    app.run = AsyncMock()

    await app.start()

    assert wdt_seen_in_setup
    assert wdt_seen_in_setup[0] is not None


# --- WiFi ------------------------------------------------------------------


async def test_wifi_connect_disconnects_before_reconnecting(wifi):
    wifi.sta = FakeWLAN()

    assert await wifi.connect("target", "wrong") is False
    assert wifi.sta.disconnect_calls >= 1


async def test_wifi_monitor_reconnects_when_link_drops(wifi):
    wifi.sta = DroppingWLAN()

    await wifi.monitor("recovery", "secret", attempts_before_reset=1, max_cycles=1)

    assert wifi.sta.connect_calls[0] == ("recovery", "secret")


# --- Config ----------------------------------------------------------------


def test_config_save_is_atomic(config_file, monkeypatch):
    opened, renamed = [], []
    real_open = builtins.open

    def spy_open(file, mode="r", *args, **kwargs):
        opened.append((str(file), mode))
        return real_open(file, mode, *args, **kwargs)

    config = Config()
    config._data = {"wifi_ssid": "ssid"}
    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(os, "rename", lambda src, dst: renamed.append((src, dst)))

    config.save()

    assert opened[0][0].endswith(".tmp")
    assert renamed[0][1] == str(config_file)


def test_config_load_ignores_non_object_json(config_file):
    config_file.write_text("[]")

    config = Config()

    assert config["wifi_ssid"] == ""
    assert config["api_url"].startswith("https://")


def test_config_load_rejects_non_string_critical_settings(config_file):
    config_file.write_text('{"wifi_ssid": 123, "wifi_password": false, "api_url": ["https://bad"]}')

    config = Config()

    assert config["wifi_ssid"] == ""
    assert config["wifi_password"] == ""
    assert config["api_url"] == ""


# --- API -------------------------------------------------------------------


def test_api_rejects_next_url_on_different_host(api):
    api._process_response({"nextUrl": "https://evil.example.net/events/test/", "events": []})

    assert api.current_url == EVENTS_URL


def test_api_ignores_malformed_or_null_payloads(api):
    api._process_response(None)
    api._process_response(
        {
            "nextUrl": None,
            "events": [
                None,
                {"method": "tip", "object": {"tip": {"tokens": 12, "message": "ok"}}},
            ],
        },
    )

    assert api.current_url == EVENTS_URL
    assert len(api.events._queue) == 1


def test_api_emits_each_event_only_once(api):
    api._process_response(
        {"events": [{"method": "tip", "object": {"tip": {"tokens": 35, "message": "red"}}}]},
    )

    assert len(api.events._queue) == 1


# --- BLE -------------------------------------------------------------------


def test_ble_truncates_oversized_wifi_ssid(ble):
    ssid = "a" * 200
    ble._buffers[_CHAR_SSID] = bytearray(ssid.encode())

    ble._apply_buffer_to_settings(_CHAR_SSID, "wifi_ssid")

    assert settings["wifi_ssid"] == ssid[:MAX_WIFI_SSID_LEN]


async def test_ble_rescan_clears_done_task(wifi, ble):
    scan_called = asyncio.Event()
    block_forever = asyncio.Event()
    pending_writes = [(None, b"\x01rescan")]

    async def fake_scan():
        scan_called.set()
        return []

    async def fake_written():
        if pending_writes:
            return pending_writes.pop()
        await block_forever.wait()

    wifi.scan = fake_scan
    ble.char_wifitest.written = fake_written

    monitor = asyncio.create_task(ble._monitor_wifi_test())
    try:
        await asyncio.wait_for(scan_called.wait(), timeout=2)
        await wait_until(lambda: ble._rescan_task is None)  # cleared once the scan finishes
    finally:
        monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor


async def test_ble_disconnect_cancels_pending_rescan_task(ble):
    task = asyncio.create_task(asyncio.sleep(30))
    ble._rescan_task = task
    ble._tasks = [task]

    await ble._cancel_rescan_task()

    assert ble._rescan_task is None
    assert task.done()
