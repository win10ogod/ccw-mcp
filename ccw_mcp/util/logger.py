"""Structured logging system with JSON support (optimized)"""

import sys
import json
import time
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


class LogLevel(Enum):
    """Log levels"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    level: str
    message: str
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


class StructuredLogger:
    """Structured logger with JSON output support (thread-safe)"""

    def __init__(
        self,
        name: str = "ccw-mcp",
        level: LogLevel = LogLevel.INFO,
        json_output: bool = False,
        file_handle: Optional[Any] = None
    ):
        """Initialize logger.

        Args:
            name: Logger name
            level: Minimum log level
            json_output: Output in JSON format
            file_handle: File handle for output (default: stderr)
        """
        self.name = name
        self.level = level
        self.json_output = json_output
        self.file_handle = file_handle or sys.stderr

    def _format_entry(self, entry: LogEntry) -> str:
        """Format log entry.

        Args:
            entry: Log entry

        Returns:
            Formatted string
        """
        if self.json_output:
            # JSON format
            return json.dumps(asdict(entry))
        else:
            # Human-readable format
            parts = [
                f"[{entry.timestamp}]",
                f"[{entry.level}]"
            ]

            if entry.module:
                parts.append(f"[{entry.module}]")

            parts.append(entry.message)

            if entry.extra:
                extra_str = " ".join(f"{k}={v}" for k, v in entry.extra.items())
                parts.append(f"({extra_str})")

            return " ".join(parts)

    def _log(
        self,
        level: LogLevel,
        message: str,
        module: Optional[str] = None,
        function: Optional[str] = None,
        line: Optional[int] = None,
        **extra: Any
    ):
        """Internal log method.

        Args:
            level: Log level
            message: Log message
            module: Module name
            function: Function name
            line: Line number
            extra: Additional fields
        """
        if level.value < self.level.value:
            return

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.name,
            message=message,
            module=module,
            function=function,
            line=line,
            extra=extra if extra else None
        )

        formatted = self._format_entry(entry)
        print(formatted, file=self.file_handle, flush=True)

    def debug(self, message: str, **extra: Any):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra: Any):
        """Log info message."""
        self._log(LogLevel.INFO, message, **extra)

    def warning(self, message: str, **extra: Any):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **extra)

    def error(self, message: str, **extra: Any):
        """Log error message."""
        self._log(LogLevel.ERROR, message, **extra)

    def critical(self, message: str, **extra: Any):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **extra)

    def set_level(self, level: LogLevel):
        """Set log level."""
        self.level = level

    def enable_json(self):
        """Enable JSON output."""
        self.json_output = True

    def disable_json(self):
        """Disable JSON output."""
        self.json_output = False


# Global logger instance
_default_logger: Optional[StructuredLogger] = None


def get_logger(
    name: str = "ccw-mcp",
    json_output: bool = False,
    level: LogLevel = LogLevel.INFO
) -> StructuredLogger:
    """Get or create logger instance.

    Args:
        name: Logger name
        json_output: Enable JSON output
        level: Log level

    Returns:
        Logger instance
    """
    global _default_logger

    if _default_logger is None:
        _default_logger = StructuredLogger(
            name=name,
            level=level,
            json_output=json_output
        )

    return _default_logger


def configure_logging(json_output: bool = False, level: LogLevel = LogLevel.INFO):
    """Configure global logging.

    Args:
        json_output: Enable JSON output
        level: Log level
    """
    global _default_logger
    _default_logger = StructuredLogger(
        name="ccw-mcp",
        level=level,
        json_output=json_output
    )


# Convenience functions
def debug(message: str, **extra: Any):
    """Log debug message."""
    get_logger().debug(message, **extra)


def info(message: str, **extra: Any):
    """Log info message."""
    get_logger().info(message, **extra)


def warning(message: str, **extra: Any):
    """Log warning message."""
    get_logger().warning(message, **extra)


def error(message: str, **extra: Any):
    """Log error message."""
    get_logger().error(message, **extra)


def critical(message: str, **extra: Any):
    """Log critical message."""
    get_logger().critical(message, **extra)
