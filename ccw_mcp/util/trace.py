"""Trace and resource monitoring utilities"""

import time
import psutil
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResourceUsage:
    """Resource usage statistics"""
    cpu_ms: int = 0
    rss_max_kb: int = 0
    io_read_kb: int = 0
    io_write_kb: int = 0


@dataclass
class ProcessTracer:
    """Trace process execution and resource usage (optimized)"""
    pid: Optional[int] = None
    start_time: float = field(default_factory=time.time)
    _process: Optional[psutil.Process] = None
    _max_rss: int = 0
    _io_start: Optional[tuple] = None
    _process_exists: bool = True  # Cache to avoid repeated NoSuchProcess checks

    def attach(self, pid: int):
        """Attach to a process for monitoring"""
        self.pid = pid
        try:
            self._process = psutil.Process(pid)
            self._process_exists = True
            # Try to get IO counters, but don't fail if unavailable
            try:
                self._io_start = self._get_io_counters()
            except Exception:
                self._io_start = None
        except psutil.NoSuchProcess:
            self._process_exists = False
            pass

    def _get_io_counters(self) -> Optional[tuple]:
        """Get IO counters if available"""
        if not self._process or not self._process_exists:
            return None
        try:
            io = self._process.io_counters()
            return (io.read_bytes, io.write_bytes)
        except (psutil.NoSuchProcess, AttributeError, KeyError, OSError):
            # Handle various errors: process gone, feature not supported, or proc format issues
            return None

    def sample(self):
        """Sample current resource usage (optimized with caching)"""
        if not self._process or not self._process_exists:
            return

        try:
            # Use oneshot() context manager for efficient batch queries
            with self._process.oneshot():
                mem_info = self._process.memory_info()
                self._max_rss = max(self._max_rss, mem_info.rss // 1024)
        except psutil.NoSuchProcess:
            self._process_exists = False
            pass

    def get_usage(self) -> ResourceUsage:
        """Get final resource usage statistics (optimized)"""
        usage = ResourceUsage()

        if self._process and self._process_exists:
            try:
                # Use oneshot() for efficient batch queries
                with self._process.oneshot():
                    # CPU time
                    cpu_times = self._process.cpu_times()
                    cpu_ms = int((cpu_times.user + cpu_times.system) * 1000)
                    usage.cpu_ms = cpu_ms

                    # Memory
                    usage.rss_max_kb = self._max_rss

                    # IO - get final counters
                    if self._io_start:
                        io_end = self._get_io_counters()
                        if io_end:
                            usage.io_read_kb = (io_end[0] - self._io_start[0]) // 1024
                            usage.io_write_kb = (io_end[1] - self._io_start[1]) // 1024

            except psutil.NoSuchProcess:
                self._process_exists = False
                pass

        return usage
