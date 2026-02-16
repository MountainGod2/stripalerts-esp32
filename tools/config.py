"""Configuration management for StripAlerts ESP32 tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar


class ChipType(str, Enum):
    """ESP32 chip types supported."""

    ESP32 = "esp32"
    ESP32S2 = "esp32s2"
    ESP32S3 = "esp32s3"
    ESP32C3 = "esp32c3"
    ESP32C6 = "esp32c6"
    ESP32H2 = "esp32h2"

    @classmethod
    def from_board(cls, board: str) -> ChipType:
        """Determine chip type from board name."""
        board_upper = board.upper()
        if "S3" in board_upper:
            return cls.ESP32S3
        if "S2" in board_upper:
            return cls.ESP32S2
        if "C3" in board_upper:
            return cls.ESP32C3
        if "C6" in board_upper:
            return cls.ESP32C6
        if "H2" in board_upper:
            return cls.ESP32H2
        return cls.ESP32


@dataclass(frozen=True)
class FlashConfig:
    """Flash memory configuration constants."""

    BOOTLOADER_ADDR: ClassVar[int] = 0x0
    PARTITION_TABLE_ADDR: ClassVar[int] = 0x8000
    FIRMWARE_ADDR: ClassVar[int] = 0x10000

    DEFAULT_FLASH_BAUD: ClassVar[int] = 460800
    DEFAULT_MONITOR_BAUD: ClassVar[int] = 115200


@dataclass(frozen=True)
class RetryConfig:
    """Retry configuration for flaky operations."""

    MAX_RETRIES: ClassVar[int] = 3
    RETRY_DELAY: ClassVar[float] = 1.0
    OPERATION_TIMEOUT: ClassVar[int] = 30
    DEVICE_STABILIZE_DELAY: ClassVar[float] = 5.0


@dataclass
class ProjectPaths:
    """Project directory paths."""

    root: Path
    src: Path = field(init=False)
    dist: Path = field(init=False)
    boards: Path = field(init=False)
    micropython: Path = field(init=False)
    micropython_esp32: Path = field(init=False)
    mpy_cross: Path = field(init=False)

    def __post_init__(self) -> None:
        """Initialize derived paths."""
        self.src = self.root / "src"
        self.dist = self.root / "dist"
        self.boards = self.root / "boards"
        self.micropython = self.root / "micropython"
        self.micropython_esp32 = self.micropython / "ports" / "esp32"
        self.mpy_cross = self.micropython / "mpy-cross"

    def build_dir(self, board: str) -> Path:
        """Get build directory for specific board."""
        return self.micropython_esp32 / f"build-{board}"

    def board_dir(self, board: str) -> Path:
        """Get custom board directory."""
        return self.boards / board

    @classmethod
    def from_tools_dir(cls) -> ProjectPaths:
        """Create ProjectPaths from tools directory location."""
        tools_dir = Path(__file__).parent
        return cls(root=tools_dir.parent.resolve())


@dataclass
class BuildConfig:
    """Configuration for firmware building."""

    board: str = "STRIPALERTS_S3"
    clean: bool = False
    verbose: bool = False

    @property
    def chip_type(self) -> ChipType:
        """Get chip type for this board."""
        return ChipType.from_board(self.board)


@dataclass
class FlashingConfig:
    """Configuration for firmware flashing."""

    board: str = "STRIPALERTS_S3"
    port: str | None = None
    baud: int = FlashConfig.DEFAULT_FLASH_BAUD
    erase: bool = False

    @property
    def chip_type(self) -> ChipType:
        """Get chip type for this board."""
        return ChipType.from_board(self.board)


@dataclass
class MonitorConfig:
    """Configuration for serial monitoring."""

    port: str | None = None
    baud: int = FlashConfig.DEFAULT_MONITOR_BAUD


@dataclass
class UploadConfig:
    """Configuration for file uploading."""

    port: str | None = None
    files: list[str] = field(default_factory=lambda: ["boot.py", "main.py"])


@dataclass
class DeployConfig:
    """Configuration for full deployment workflow."""

    board: str = "STRIPALERTS_S3"
    port: str | None = None
    baud: int = FlashConfig.DEFAULT_FLASH_BAUD
    clean: bool = False
    erase: bool = False
    skip_build: bool = False
    skip_flash: bool = False
    skip_upload: bool = False
    skip_monitor: bool = False
    stabilize_seconds: float = RetryConfig.DEVICE_STABILIZE_DELAY
