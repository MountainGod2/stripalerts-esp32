"""Tool configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar


class ChipType(str, Enum):
    """Supported ESP32 chip types."""

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
    """Flash layout constants."""

    BOOTLOADER_ADDR_MAP: ClassVar[dict[str, int]] = {
        "esp32": 0x1000,
        "esp32s2": 0x1000,
        "esp32s3": 0x0,
        "esp32c3": 0x0,
        "esp32c6": 0x0,
        "esp32h2": 0x0,
    }

    PARTITION_TABLE_ADDR: ClassVar[int] = 0x8000
    FIRMWARE_ADDR: ClassVar[int] = 0x10000

    DEFAULT_FLASH_BAUD: ClassVar[int] = 460800
    DEFAULT_MONITOR_BAUD: ClassVar[int] = 115200

    @classmethod
    def get_bootloader_addr(cls, chip_type: ChipType) -> int:
        """Return bootloader address for chip type."""
        return cls.BOOTLOADER_ADDR_MAP.get(chip_type.value, 0x0)


@dataclass(frozen=True)
class RetryConfig:
    """Retry and timeout constants."""

    MAX_RETRIES: ClassVar[int] = 3
    RETRY_DELAY: ClassVar[float] = 1.0
    OPERATION_TIMEOUT: ClassVar[int] = 60
    DEVICE_STABILIZE_DELAY: ClassVar[float] = 5.0


@dataclass
class ChipTypeMixin:
    """Adds a chip type derived from board name."""

    board: str

    @property
    def chip_type(self) -> ChipType:
        """Get chip type for this board."""
        return ChipType.from_board(self.board)


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
class BuildConfig(ChipTypeMixin):
    """Build command options."""

    board: str = "STRIPALERTS_S3"
    clean: bool = False
    verbose: bool = False


@dataclass
class FlashingConfig(ChipTypeMixin):
    """Flash command options."""

    board: str = "STRIPALERTS_S3"
    port: str | None = None
    baud: int = FlashConfig.DEFAULT_FLASH_BAUD
    erase: bool = False


@dataclass
class MonitorConfig:
    """Monitor command options."""

    port: str | None = None
    baud: int = FlashConfig.DEFAULT_MONITOR_BAUD


@dataclass
class UploadConfig:
    """Upload command options."""

    port: str | None = None
    files: list[str] = field(default_factory=lambda: ["boot.py", "main.py"])
