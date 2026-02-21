#!/usr/bin/env python3
"""StripAlerts CLI."""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Annotated, ParamSpec, TypeVar

import typer
from rich.traceback import install as install_rich_traceback

from .builder import FirmwareBuilder
from .cleaner import BuildCleaner
from .config import (
    BuildConfig,
    FlashConfig,
    FlashingConfig,
    MonitorConfig,
    ProjectPaths,
    RetryConfig,
    UploadConfig,
)
from .console import print_error, print_header, print_info, print_success
from .exceptions import StripAlertsError
from .monitor import SerialMonitor
from .uploader import FileUploader, FirmwareUploader

if TYPE_CHECKING:
    from collections.abc import Callable

install_rich_traceback(show_locals=True)

app = typer.Typer(
    name="stripalerts",
    help="StripAlerts ESP32 Firmware Development CLI",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

P = ParamSpec("P")
R = TypeVar("R")


def _paths() -> ProjectPaths:
    """Return workspace paths for CLI commands."""
    return ProjectPaths.from_tools_dir()


def handle_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to handle common CLI errors with consistent messaging."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except StripAlertsError as e:
            print_error(str(e))
            raise typer.Exit(1) from e
        except KeyboardInterrupt:
            print_info(f"{func.__name__.capitalize()} stopped by user")
            raise typer.Exit(130) from None
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            raise typer.Exit(1) from e

    return wrapper


@app.command()
@handle_errors
def build(
    board: Annotated[
        str,
        typer.Option("--board", "-b", help="ESP32 board variant"),
    ] = "STRIPALERTS_S3",
    clean: Annotated[
        bool,
        typer.Option("--clean", "-c", help="Clean before building"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show verbose output"),
    ] = False,
) -> None:
    """Build firmware for ESP32 board."""
    paths = _paths()
    config = BuildConfig(board=board, clean=clean, verbose=verbose)
    builder = FirmwareBuilder(config, paths)
    builder.build()


@app.command()
@handle_errors
def flash(
    board: Annotated[
        str,
        typer.Option("--board", "-b", help="ESP32 board variant"),
    ] = "STRIPALERTS_S3",
    port: Annotated[
        str | None,
        typer.Option("--port", "-p", help="Serial port (auto-detect if not set)"),
    ] = None,
    baud: Annotated[
        int,
        typer.Option("--baud", help="Baud rate for flashing"),
    ] = FlashConfig.DEFAULT_FLASH_BAUD,
    erase: Annotated[
        bool,
        typer.Option("--erase", "-e", help="Erase flash before flashing"),
    ] = False,
) -> None:
    """Flash firmware to ESP32 device."""
    paths = _paths()
    config = FlashingConfig(board=board, port=port, baud=baud, erase=erase)
    uploader = FirmwareUploader(config, paths)
    uploader.upload()


@app.command()
@handle_errors
def upload(
    port: Annotated[
        str | None,
        typer.Option("--port", "-p", help="Serial port (auto-detect if not set)"),
    ] = None,
) -> None:
    """Upload application files to ESP32 device."""
    paths = _paths()
    config = UploadConfig(port=port)
    uploader = FileUploader(config, paths)
    uploader.upload_files()


@app.command()
@handle_errors
def monitor(
    port: Annotated[
        str | None,
        typer.Option("--port", "-p", help="Serial port (auto-detect if not set)"),
    ] = None,
    baud: Annotated[
        int,
        typer.Option("--baud", help="Baud rate for monitoring"),
    ] = FlashConfig.DEFAULT_MONITOR_BAUD,
) -> None:
    """Monitor serial output from ESP32 device."""
    config = MonitorConfig(port=port, baud=baud)
    serial_monitor = SerialMonitor(config)
    serial_monitor.monitor()


@app.command()
@handle_errors
def clean(
    deep: Annotated[
        bool,
        typer.Option("--all", "-a", help="Deep clean including MicroPython artifacts"),
    ] = False,
) -> None:
    """Clean build artifacts and caches."""
    paths = _paths()
    cleaner = BuildCleaner(paths, deep_clean=deep)
    cleaner.clean()


@app.command()
@handle_errors
def deploy(  # noqa: PLR0913
    board: Annotated[
        str,
        typer.Option("--board", "-b", help="ESP32 board variant"),
    ] = "STRIPALERTS_S3",
    port: Annotated[
        str | None,
        typer.Option("--port", "-p", help="Serial port (auto-detect if not set)"),
    ] = None,
    baud: Annotated[
        int,
        typer.Option("--baud", help="Baud rate for flashing"),
    ] = FlashConfig.DEFAULT_FLASH_BAUD,
    clean: Annotated[
        bool,
        typer.Option("--clean", "-c", help="Clean before building"),
    ] = False,
    erase: Annotated[
        bool,
        typer.Option("--erase", "-e", help="Erase flash before flashing"),
    ] = False,
    skip_build: Annotated[
        bool,
        typer.Option("--skip-build", help="Skip build step"),
    ] = False,
    skip_flash: Annotated[
        bool,
        typer.Option("--skip-flash", help="Skip flash step"),
    ] = False,
    skip_upload: Annotated[
        bool,
        typer.Option("--skip-upload", help="Skip upload step"),
    ] = False,
    skip_monitor: Annotated[
        bool,
        typer.Option("--skip-monitor", help="Skip monitor step"),
    ] = False,
    stabilize_seconds: Annotated[
        float,
        typer.Option("--stabilize-seconds", help="Seconds to wait after flash"),
    ] = RetryConfig.DEVICE_STABILIZE_DELAY,
) -> None:
    """Full deployment: build + flash + upload + monitor."""
    paths = _paths()
    steps_run = 0

    def run_step(step_label: str, enabled: bool, action: Callable[[], None]) -> None:
        nonlocal steps_run
        if not enabled:
            return
        print_header(step_label)
        action()
        steps_run += 1

    run_step(
        "STEP 1/4: Building Firmware",
        not skip_build,
        lambda: FirmwareBuilder(BuildConfig(board=board, clean=clean), paths).build(),
    )

    run_step(
        "STEP 2/4: Flashing Firmware",
        not skip_flash,
        lambda: FirmwareUploader(
            FlashingConfig(board=board, port=port, baud=baud, erase=erase),
            paths,
        ).upload(),
    )

    def _upload_step() -> None:
        if not skip_flash:
            print_info(f"Waiting {stabilize_seconds}s for device stabilization...")
            time.sleep(stabilize_seconds)
        FileUploader(UploadConfig(port=port), paths).upload_files()

    run_step("STEP 3/4: Uploading Application Files", not skip_upload, _upload_step)

    run_step(
        "STEP 4/4: Monitoring Device",
        not skip_monitor,
        lambda: SerialMonitor(MonitorConfig(port=port)).monitor(),
    )

    if steps_run:
        print_success("Deployment completed successfully!")
    else:
        print_info("No deployment steps were executed.")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
