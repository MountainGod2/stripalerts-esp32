"""Main entry point for StripAlerts."""

import asyncio
import sys

from stripalerts.app import App
from stripalerts.utils import log_error, log_info


async def main() -> None:
    """Application entry point."""
    app = App()
    try:
        await app.start()
    except KeyboardInterrupt:
        log_info("Application interrupted by user")
    except Exception as e:
        log_error(f"Fatal error: {e}")
        sys.print_exception(e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log_error(f"Failed to start application: {e}")
        sys.print_exception(e)
