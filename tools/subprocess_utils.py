"""Subprocess helpers."""

from __future__ import annotations

import subprocess
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from .config import RetryConfig
from .console import print_command, print_error, print_warning
from .exceptions import CommandError, OperationTimeoutError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

T = TypeVar("T")


def retry(
    max_attempts: int = RetryConfig.MAX_RETRIES,
    delay: float = RetryConfig.RETRY_DELAY,
    exceptions: tuple[type[Exception], ...] = (subprocess.CalledProcessError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry a function on failure."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if max_attempts < 1:
                msg = "max_attempts must be >= 1"
                raise ValueError(msg)
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        print_warning(
                            f"Attempt {attempt}/{max_attempts} failed, retrying in {delay}s...",
                        )
                        time.sleep(delay)
                    else:
                        print_error(f"All {max_attempts} attempts failed")

            if last_exception is None:
                msg = "Retry logic failed without capturing an exception"
                raise RuntimeError(msg)
            raise last_exception

        return wrapper

    return decorator


def run_command(  # noqa: PLR0913
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = RetryConfig.OPERATION_TIMEOUT,
    check: bool = True,
    capture_output: bool = False,
    verbose: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """Run a command with consistent error handling."""
    if verbose:
        print_command(cmd)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            timeout=timeout,
            check=False,
            capture_output=capture_output,
        )

        if check and result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore") if capture_output else None
            raise CommandError(cmd, result.returncode, stderr)

    except subprocess.TimeoutExpired as e:
        msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
        raise OperationTimeoutError(msg) from e
    else:
        return result


def run_command_quiet(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 5,
) -> tuple[bool, str]:
    """Run command quietly and return `(success, output)`."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, ""


def check_command_available(
    command: str,
    version_flag: str = "--version",
    timeout: int = 5,
) -> bool:
    """Return whether a command-line tool is available."""
    success, _ = run_command_quiet([command, version_flag], timeout=timeout)
    return success


def run_interactive(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run command interactively and return exit code."""
    try:
        result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=False)
    except KeyboardInterrupt:
        print_warning("Interrupted by user")
        return 130
    else:
        return result.returncode


def get_command_output(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 5,
) -> str | None:
    """Return command output text or `None` on failure."""
    success, output = run_command_quiet(cmd, cwd=cwd, timeout=timeout)
    return output.strip() if success else None
