"""
RemoteFlash — enums and data classes.

Pure data types with no UI or SSH dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ─── Logging ───────────────────────────────────────────────────────
class LogLevel(Enum):
    Info = "INFO"
    Success = "SUCCESS"
    Error = "ERROR"
    Warning = "WARNING"
    Debug = "DEBUG"
    Command = "COMMAND"


@dataclass
class LogEntry:
    level: LogLevel
    message: str
    timestamp: str

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = self._current_time()

    @staticmethod
    def _current_time() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def format_display(self) -> str:
        icon = self._get_icon()
        return f"[{self.timestamp}] {icon} {self.message}"

    def _get_icon(self) -> str:
        icons = {
            LogLevel.Info: "ℹ",
            LogLevel.Success: "✓",
            LogLevel.Error: "✗",
            LogLevel.Warning: "⚠",
            LogLevel.Debug: "·",
            LogLevel.Command: "›",
        }
        return icons.get(self.level, "·")


# ─── Connection ────────────────────────────────────────────────────
class AuthMethod(Enum):
    RsaKey = "key"
    Password = "password"
    Agent = "agent"


@dataclass
class ConnectionProfile:
    name: str = "New profile"
    ip: str = "192.168.1.1"
    username: str = "root"
    port: int = 22
    auth_method: str = AuthMethod.RsaKey.value
    rsa_key_path: Optional[str] = None
    password: str = ""
    port_labels: dict = field(default_factory=dict)  # Maps port paths to custom labels


@dataclass
class TaskState(Enum):
    Idle = "idle"
    Running = "running"
    Done = "done"
    Failed = "failed"
