"""Diff generation utilities"""

import difflib
import json
from pathlib import Path
from typing import Optional, Any


def generate_unified_diff(
    old_path: Path,
    new_path: Path,
    context_lines: int = 3
) -> str:
    """Generate unified diff between two files.

    Args:
        old_path: Original file path
        new_path: Modified file path
        context_lines: Number of context lines

    Returns:
        Unified diff string
    """
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
