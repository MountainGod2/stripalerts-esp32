"""Async Chaturbate Events API Client."""

import asyncio
import gc

import aiohttp  # type: ignore

from .constants import HTTP_REQUEST_TIMEOUT
from .utils import log_error, log_info


class ChaturbateAPI:
    """Handles connection to Chaturbate Events API."""

    def __init__(self, start_url: str, event_manager) -> None:
        """Initialize the API client.

        Args:
            start_url: Initial URL for the events API
            event_manager: Event manager instance for handling events

        """
        self.current_url = start_url
        self.events = event_manager
        self._running = False
        self._failure_count = 0
        self._retry_delay = 0.0
        self._base_host = self._host_for_url(start_url)

    @staticmethod
    def _host_for_url(url: str) -> str:
        """Return the host component for a URL, or an empty string when invalid."""
        if not url:
            return ""
        scheme_plus = url.split("://", 1)
        if len(scheme_plus) == 2:
            rest = scheme_plus[1]
        else:
            rest = url
        host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        return host.lower()

    def _is_safe_next_url(self, next_url: str) -> bool:
        """Allow only same-host nextUrl values to prevent redirecting to untrusted hosts."""
        if not next_url:
            return False
        next_host = self._host_for_url(next_url)
        return bool(next_host and next_host == self._base_host)

    def _schedule_retry(self, *, status: int | None = None) -> None:
        """Back off after errors instead of retrying every 5 seconds forever."""
        self._failure_count += 1
        if status in {401, 404}:
            self._retry_delay = 5.0
        else:
            self._retry_delay = min(30.0, 2.0 * (2 ** max(0, self._failure_count - 1)))

    async def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        log_info("Starting API polling task")

        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    await self._poll(session)
                    if self._retry_delay > 0:
                        delay = self._retry_delay
                        self._retry_delay = 0.0
                        await asyncio.sleep(delay)
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log_error(f"API Error: {e}")
                    delay = self._retry_delay or 5.0
                    self._retry_delay = 0.0
                    await asyncio.sleep(delay)
                gc.collect()

    async def _poll(self, session) -> None:
        """Execute a single poll request."""
        try:
            async with session.get(self.current_url, timeout=HTTP_REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    self._failure_count = 0
                    self._retry_delay = 0.0
                    data = await response.json()
                    self._process_response(data)
                    return

                self._schedule_retry(status=response.status)
                log_error(f"HTTP Error: {response.status}; retrying in {self._retry_delay}s")
                return

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._schedule_retry()
            log_error(f"Poll failed: {e}; retrying in {self._retry_delay}s")

    def _process_response(self, data: dict | None) -> None:
        """Process the JSON response."""
        if not isinstance(data, dict):
            return

        next_url = data.get("nextUrl")
        if next_url:
            if self._is_safe_next_url(next_url):
                self.current_url = next_url
            else:
                log_error(f"Rejecting untrusted nextUrl host for {next_url}")

        events = data.get("events", [])
        if not isinstance(events, list):
            return

        for event in events:
            if not isinstance(event, dict):
                continue

            method = event.get("method")
            if method:
                log_info(f"Event: {method}")
                self.events.emit("api_event", event)
