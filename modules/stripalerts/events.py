"""Event handling system for StripAlerts."""

import asyncio
from collections import deque

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

from .constants import MAX_EVENT_QUEUE_SIZE
from .utils import log_error


class EventManager:
    """Simple event bus for decoupling components."""

    def __init__(self) -> None:
        """Initialize event manager."""
        self._handlers: dict[str, list[Callable[[Any], Coroutine[Any, Any, None]]]] = {}
        # MicroPython's deque stub lacks generic subscripts, so type: ignore is needed
        self._queue: deque = deque((), MAX_EVENT_QUEUE_SIZE)  # type: ignore[type-arg]

    def on(self, event_type: str, handler: "Callable[[Any], Coroutine[Any, Any, None]]") -> None:
        """Register event handler.

        Args:
            event_type: Type of event to handle
            handler: Async callable to handle event

        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: "Callable[[Any], Coroutine[Any, Any, None]]") -> None:
        """Unregister event handler.

        Args:
            event_type: Type of event
            handler: Handler to remove

        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                log_error(f"Handler not found for event '{event_type}'")

    def emit(self, event_type: str, data: "Any | None" = None) -> None:
        """Emit an event.

        Args:
            event_type: Type of event
            data: Event data (optional)

        """
        self._queue.append((event_type, data))

    async def process(self) -> None:
        """Process queued events."""
        queue = self._queue
        handlers = self._handlers
        while queue:
            event_tuple: tuple[str, Any] = queue.popleft()
            event_type: str = event_tuple[0]
            data = event_tuple[1]
            if event_type in handlers:
                for handler in handlers[event_type]:
                    try:
                        await handler(data)
                    except asyncio.CancelledError:  # noqa: PERF203 - Must re-raise to properly cancel
                        raise
                    except Exception as e:
                        log_error(f"Error in event handler for '{event_type}': {e}")

    async def run(self) -> None:
        """Run event processing loop."""
        while True:
            await self.process()
            await asyncio.sleep(0.1)
