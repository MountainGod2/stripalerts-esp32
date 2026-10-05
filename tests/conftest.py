"""Pytest bootstrap: stub MicroPython-only modules so firmware code imports on CPython.

Stubs must be registered at import time (before test modules import the firmware),
which is why this lives at module level rather than in a fixture.
"""

from __future__ import annotations

import os
import sys
from types import ModuleType

ROOT = os.environ.get("STRIPALERTS_ROOT", "/config/stripalerts-esp32")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _noop(*_args, **_kwargs) -> None:
    return None


def _identity(value):
    return value


def _install(name: str, **attrs) -> ModuleType:
    """Create a stub module with the given attributes and register it in sys.modules."""
    module = ModuleType(name)
    vars(module).update(attrs)
    sys.modules[name] = module
    return module


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc_info) -> bool:
        return False


# --- machine / micropython -------------------------------------------------


class FakeWDT:
    def __init__(self, timeout=None):
        self.timeout = timeout

    feed = _noop


class FakePin:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


_install("machine", WDT=FakeWDT, Pin=FakePin, reset=_noop)
_install("micropython", const=_identity, native=_identity)


# --- network ---------------------------------------------------------------


class FakeWLAN:
    def __init__(self, *_args, **_kwargs):
        self._connected = False
        self._active = False

    def active(self, value=None):
        if value is not None:
            self._active = bool(value)
        return self._active

    def disconnect(self):
        self._connected = False

    def isconnected(self):
        return self._connected

    def scan(self):
        return []

    def ifconfig(self):
        return ("0.0.0.0",)

    connect = config = _noop


_install("network", WLAN=FakeWLAN, STA_IF=0)


# --- bluetooth / aioble ----------------------------------------------------


class UUID(str):
    """Stand-in for ``bluetooth.UUID``; behaves like its string form."""


class Service:
    def __init__(self, *args, **_kwargs):
        self.uuid = args[0] if args else None


class Characteristic:
    def __init__(self, *args, **kwargs):
        self.uuid = args[1] if len(args) > 1 else None
        self.kwargs = kwargs

    read = write = notify = _noop

    async def written(self):
        return None, b""


class _FakeConnection:
    device = "fake-device"

    async def disconnected(self):
        return None


async def _advertise(*_args, **_kwargs) -> _FakeConnection:
    return _FakeConnection()


_install("bluetooth", UUID=UUID)
_install(
    "aioble",
    Service=Service,
    Characteristic=Characteristic,
    register_services=_noop,
    advertise=_advertise,
)


# --- aiohttp ---------------------------------------------------------------


class _FakeResponse(_AsyncContext):
    status = 200

    async def json(self):
        return {"events": []}


class _ClientSession(_AsyncContext):
    def get(self, *_args, **_kwargs) -> _FakeResponse:
        return _FakeResponse()


_install("aiohttp", ClientSession=_ClientSession)


# --- neopixel --------------------------------------------------------------


class FakeNeoPixel:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pixels = [(0, 0, 0)]

    def fill(self, color):
        self.pixels = [color] * len(self.pixels)

    write = _noop


_install("neopixel", NeoPixel=FakeNeoPixel)
