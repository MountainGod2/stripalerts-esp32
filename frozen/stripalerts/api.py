"""Async Chaturbate Events API Client."""

import asyncio
import gc
import json

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
        while self._running:
            try:
                await self._poll()
                # Yield to let other tasks run
                await asyncio.sleep(0.1)
            except Exception as e:
                log_error(f"API Error: {e}")
                await asyncio.sleep(5)
            gc.collect()

    async def _poll(self) -> None:
        """Execute a single poll request."""
        # Simple URL parsing
        try:
            proto, dummy, host, path = self.current_url.split("/", 3)
            use_ssl = proto == "https:"
            port = 443 if use_ssl else 80
            # Remove trailing part from path if needed or keep it
            path = "/" + path
        except ValueError:
            log_error(f"Invalid URL: {self.current_url}")
            await asyncio.sleep(5)
            return

        reader = writer = None
        try:
            reader, writer = await asyncio.open_connection(host, port, ssl=use_ssl)

            # Send GET request
            request = (
                f"GET {path} HTTP/1.0\r\n"
                f"Host: {host}\r\n"
                "User-Agent: StripAlerts-ESP32\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            writer.write(request.encode())
            await writer.drain()

            # Read Status Line
            line = await reader.readline()
            if not line:
                raise ValueError("Empty response")

            parts = line.split(b" ")
            if len(parts) > 1 and parts[1] != b"200":
                log_error(f"HTTP Error: {parts[1].decode()}")
                await asyncio.sleep(5)
                return

            # Skip Headers
            while True:
                line = await reader.readline()
                if line == b"\r\n" or line == b"\n" or not line:
                    break

            # Read Body
            # Limit size to prevent OOM
            body = await reader.read(4096)
            if body:
                try:
                    data = json.loads(body)
                    self._process_response(data)
                except ValueError:
                    log_error("Invalid JSON response")

        except Exception as e:
            log_error(f"Connection failed: {e}")
            await asyncio.sleep(2)
        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

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
