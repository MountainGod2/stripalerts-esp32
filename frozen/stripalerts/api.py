"""Async Chaturbate Events API Client."""

import json

import aiohttp
import uasyncio as asyncio

from .utils import log_error, log_info


class ChaturbateAPI:
    """Handles connection to Chaturbate Events API."""

    def __init__(self, start_url: str, event_manager) -> None:
        """Initialize API client.

        Args:
            start_url: The initial API URL with token.
            event_manager: The event manager to emit events to.

        """
        self.current_url = start_url
        self.events = event_manager
        self._running = False

    async def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        log_info(f"Starting API polling with URL: {self.current_url}")

        while self._running:
            try:
                # Use context manager for session
                async with aiohttp.ClientSession() as session:
                    while self._running:
                        await self._poll(session)
                        # Yield to other tasks
                        await asyncio.sleep(0)
            except Exception as e:
                log_error(f"Session Error: {e}")
                # Wait before retrying session creation
                await asyncio.sleep(5)

    async def _poll(self, session) -> None:
        """Single poll request."""
        try:
            # Server timeout is ~90s
            headers = {"User-Agent": "StripAlerts-ESP32"}
            async with session.get(self.current_url, headers=headers) as response:
                if response.status != 200:
                    log_error(f"HTTP Error: {response.status}")
                    await asyncio.sleep(5)
                    return

                try:
                    data = await response.json()
                except Exception:
                    text = await response.text()
                    data = json.loads(text)

                self._process_response(data)

        except Exception as e:
            log_error(f"Poll Error: {e}")
            await asyncio.sleep(2)

    def _process_response(self, data: dict) -> None:
        """Process the JSON response."""
        next_url = data.get("nextUrl")
        if next_url:
            self.current_url = next_url

        events = data.get("events", [])
        for event in events:
            method = event.get("method")
            if method:
                log_info(f"Event received: {method}")
                self.events.emit("api_event", event)
                self.events.emit(f"api:{method}", event)

    def stop(self) -> None:
        """Stop polling."""
        self._running = False
