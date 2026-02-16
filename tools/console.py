"""Rich console output utilities for StripAlerts ESP32 tools."""

from __future__ import annotations

from contextlib import contextmanager
from types import TracebackType
from typing import TYPE_CHECKING, Any

try:
    from typing import Self
except ImportError:
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
from rich.table import Table
from rich.theme import Theme

if TYPE_CHECKING:
    from collections.abc import Iterator

# Custom theme for StripAlerts branding
STRIPALERTS_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "header": "bold magenta",
        "code": "bold blue",
        "path": "italic cyan",
    }
)

# Global console instance
console = Console(theme=STRIPALERTS_THEME)


def print_header(title: str, subtitle: str | None = None) -> None:
    """Print a styled header panel."""
    content = f"[header]{title}[/header]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(content, border_style="header", expand=False))


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f":white_check_mark: [success]{message}[/success]")


def print_error(message: str, detail: str | None = None) -> None:
    """Print an error message with optional detail."""
    console.print(f":x: [error]ERROR:[/error] {message}")
    if detail:
        console.print(f"  [dim]{detail}[/dim]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f":warning: [warning]WARNING:[/warning] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f":information: [info]INFO:[/info] {message}")


def print_step(step: str, message: str) -> None:
    """Print a step in a multi-step process."""
    console.print(f"[bold]{step}[/bold] {message}")


def print_file_operation(operation: str, path: str, success: bool = True) -> None:
    """Print a file operation result."""
    status = ":white_check_mark:" if success else ":x:"
    style = "success" if success else "error"
    console.print(f"{status} [{style}]{operation}[/{style}] [path]{path}[/path]")


def print_table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    """Print a formatted table."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def print_command(cmd: list[str]) -> None:
    """Print a command being executed."""
    cmd_str = " ".join(cmd)
    console.print(f"[dim]$ [code]{cmd_str}[/code][/dim]")


def print_keyval(key: str, value: Any) -> None:
    """Print a key-value pair."""
    console.print(f"  [bold]{key}:[/bold] {value}")


@contextmanager
def progress_bar(description: str) -> Iterator[Progress]:
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


@contextmanager
def spinner(description: str) -> Iterator[None]:
    """Create a spinner for long-running operations."""
    with console.status(f"[info]{description}[/info]", spinner="dots"):
        yield


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask user for confirmation."""
    from rich.prompt import Confirm

    return Confirm.ask(prompt, default=default, console=console)


def prompt(question: str, default: str | None = None) -> str:
    """Prompt user for input."""
    from rich.prompt import Prompt

    return Prompt.ask(question, default=default, console=console)


class StatusLogger:
    """Context manager for tracking operation status."""

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
            print_error(f"{self.operation} failed")


def format_size(size_bytes: int) -> str:
    """Format byte size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m {secs}s"
