"""Async Chaturbate Events API Client."""

import asyncio
import gc

import aiohttp  # type: ignore

from .utils import log_error, log_info


class ChaturbateAPI:
    """Handles connection to Chaturbate Events API."""

    def __init__(self, start_url: str, event_manager) -> None:
        self.current_url = start_url
        self.events = event_manager
        self._running = False

    async def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        log_info("Starting API polling task")

        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    await self._poll(session)
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log_error(f"API Error: {e}")
                    await asyncio.sleep(5)
                gc.collect()

    async def _poll(self, session) -> None:
        """Execute a single poll request."""
        try:
            async with session.get(self.current_url) as response:
                if response.status != 200:
                    log_error(f"HTTP Error: {response.status}")
                    await asyncio.sleep(5)
                    return

                data = await response.json()
                self._process_response(data)

        except Exception as e:
            log_error(f"Poll failed: {e}")
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
                log_info(f"Event: {method}")
                self.events.emit("api_event", event)
                self.events.emit(f"api:{method}", event)

    def stop(self) -> None:
        """Stop polling."""
        self._running = False
