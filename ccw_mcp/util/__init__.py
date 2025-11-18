"""Utility modules"""

from .hashing import hash_file, hash_bytes, hash_stream, verify_hash
from .trace import ResourceUsage, ProcessTracer
from .diff import generate_unified_diff, generate_json_diff, count_changes, files_identical
from .filesystem import FileSystemCache, FileInfo, scan_directory_parallel, find_changed_files
from .logger import (
    StructuredLogger, LogLevel, LogEntry,
    get_logger, configure_logging,
    debug, info, warning, error, critical
)

__all__ = [
    'hash_file',
    'hash_bytes',
    'hash_stream',
    'verify_hash',
    'ResourceUsage',
    'ProcessTracer',
    'generate_unified_diff',
    'generate_json_diff',
    'count_changes',
    'files_identical',
    'FileSystemCache',
    'FileInfo',
    'scan_directory_parallel',
    'find_changed_files',
    'StructuredLogger',
    'LogLevel',
    'LogEntry',
    'get_logger',
    'configure_logging',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
]
