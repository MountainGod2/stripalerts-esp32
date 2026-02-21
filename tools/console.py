"""Console output helpers."""

from __future__ import annotations

import shlex
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType

    from typing_extensions import Self

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.theme import Theme

STRIPALERTS_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "header": "bold magenta",
        "code": "bold blue",
        "path": "italic cyan",
    },
)

console = Console(theme=STRIPALERTS_THEME)


def print_header(title: str, subtitle: str | None = None) -> None:
    """Print a styled header panel."""
    content = f"[header]{title}[/header]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(content, border_style="header", expand=False))


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[success]{message}[/success]")


def print_error(message: str, detail: str | None = None) -> None:
    """Print an error message with optional detail."""
    console.print(f"[error]ERROR:[/error] {message}")
    if detail:
        console.print(f"  [dim]{detail}[/dim]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[warning]WARNING:[/warning] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[info]INFO:[/info] {message}")


def print_file_operation(operation: str, path: str, success: bool = True) -> None:
    """Print a file operation result."""
    style = "success" if success else "error"
    console.print(f"[{style}]{operation}[/{style}] [path]{path}[/path]")


def print_command(cmd: list[str]) -> None:
    """Print a command being executed."""
    cmd_str = shlex.join(cmd)
    console.print(f"[dim]$ [code]{cmd_str}[/code][/dim]")


def print_keyval(key: str, value: Any) -> None:
    """Print a key-value pair."""
    console.print(f"  [bold]{key}:[/bold] {value}")


@contextmanager
def progress_bar() -> Iterator[Progress]:
    """Create a progress bar context manager."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        yield progress


class StatusLogger:
    """Context manager for operation status."""

    def __init__(self, operation: str) -> None:
        """Initialize status logger."""
        self.operation = operation
        self.start_msg = f"[info]{operation}...[/info]"

    def __enter__(self) -> Self:
        """Start operation."""
        console.print(self.start_msg)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Complete operation."""
        if exc_type is None:
            print_success(f"{self.operation} completed")
        else:
            print_error(f"{self.operation} failed", detail=str(exc_val) if exc_val else None)
