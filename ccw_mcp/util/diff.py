"""Diff generation utilities (optimized)"""

import difflib
import json
from pathlib import Path
from typing import Optional, Any, Iterator
from .hashing import hash_file

# Large file threshold: files larger than this use optimized processing
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB


def files_identical(old_path: Path, new_path: Path) -> bool:
    """Fast check if two files are identical using hash comparison.

    Args:
        old_path: Original file path
        new_path: Modified file path

    Returns:
        True if files are identical, False otherwise
    """
    # Quick checks first
    if not old_path.exists() or not new_path.exists():
        return False

    # Size check (fastest)
    try:
        old_size = old_path.stat().st_size
        new_size = new_path.stat().st_size
        if old_size != new_size:
            return False
    except OSError:
        return False

    # Hash comparison for definitive answer
    try:
        old_hash = hash_file(old_path)
        new_hash = hash_file(new_path)
        return old_hash == new_hash
    except Exception:
        return False


def read_lines_chunked(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[str]:
    """Read file lines in chunks to reduce memory usage.

    Args:
        path: File path to read
        chunk_size: Size of chunks to read (default 1MB)

    Yields:
        Lines from the file
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            buffer = ""
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    if buffer:
                        yield buffer
                    break

                buffer += chunk
                lines = buffer.split('\n')
                # Keep last incomplete line in buffer
                buffer = lines[-1]

                # Yield complete lines
                for line in lines[:-1]:
                    yield line + '\n'
    except FileNotFoundError:
        return


def generate_unified_diff(
    old_path: Path,
    new_path: Path,
    context_lines: int = 3
) -> str:
    """Generate unified diff between two files (optimized).

    Args:
        old_path: Original file path
        new_path: Modified file path
        context_lines: Number of context lines

    Returns:
        Unified diff string
    """
    # Fast path: check if files are identical
    if old_path.exists() and new_path.exists():
        if files_identical(old_path, new_path):
            return ""  # No diff needed

    # Check file sizes to determine processing strategy
    old_size = old_path.stat().st_size if old_path.exists() else 0
    new_size = new_path.stat().st_size if new_path.exists() else 0
    is_large = max(old_size, new_size) > LARGE_FILE_THRESHOLD

    if is_large:
        # For large files, use chunked reading
        old_lines = list(read_lines_chunked(old_path))
        new_lines = list(read_lines_chunked(new_path))
    else:
        # For small files, read normally
        try:
            with open(old_path, 'r', encoding='utf-8', errors='replace') as f:
                old_lines = f.readlines()
        except FileNotFoundError:
            old_lines = []

        try:
            with open(new_path, 'r', encoding='utf-8', errors='replace') as f:
                new_lines = f.readlines()
        except FileNotFoundError:
            new_lines = []

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=str(old_path),
        tofile=str(new_path),
        lineterm='',
        n=context_lines
    )

    return '\n'.join(diff)


def generate_json_diff(old_data: Any, new_data: Any) -> dict:
    """Generate structural diff for JSON-serializable data.

    Args:
        old_data: Original data
        new_data: Modified data

    Returns:
        Dict with added, removed, modified keys
    """
    result = {
        "added": {},
        "removed": {},
        "modified": {}
    }

    if isinstance(old_data, dict) and isinstance(new_data, dict):
        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())

        for key in new_keys - old_keys:
            result["added"][key] = new_data[key]

        for key in old_keys - new_keys:
            result["removed"][key] = old_data[key]

        for key in old_keys & new_keys:
            if old_data[key] != new_data[key]:
                result["modified"][key] = {
                    "old": old_data[key],
                    "new": new_data[key]
                }

    return result


def count_changes(diff_text: str) -> dict:
    """Count additions and deletions in unified diff.

    Args:
        diff_text: Unified diff string

    Returns:
        Dict with added, deleted counts
    """
    added = 0
    deleted = 0

    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added += 1
        elif line.startswith('-') and not line.startswith('---'):
            deleted += 1

    return {"added": added, "deleted": deleted}
