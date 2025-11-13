"""Commutativity analysis - detect independent change sets"""

from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass


@dataclass
class CommutativityResult:
    """Result of commutativity analysis"""
    independent_sets: List[List[str]]
    conflict_pairs: List[List[str]]


class CommutativityAnalyzer:
    """Analyze change commutativity for safe parallelization"""

    def __init__(self):
        pass

    def analyze(self, changes: List[Path]) -> CommutativityResult:
        """Analyze which changes can be applied independently.

        Args:
            changes: List of changed file paths

        Returns:
            CommutativityResult with independent sets and conflicts
        """
        # Build dependency graph
        # Two files conflict if they:
        # 1. Are in the same directory
        # 2. Have overlapping path components
        # Otherwise they're independent

        # Group by directory
        by_dir: Dict[Path, List[Path]] = {}
        for change in changes:
            parent = change.parent
            if parent not in by_dir:
                by_dir[parent] = []
            by_dir[parent].append(change)

        # Find independent sets
        independent_sets = []
        conflict_pairs = []

        # Files in different directories are independent
        dirs = list(by_dir.keys())
        for i, dir1 in enumerate(dirs):
            files1 = by_dir[dir1]

            # Check if this directory conflicts with others
            conflicts = False
            for j, dir2 in enumerate(dirs):
                if i == j:
                    continue

                # Check if directories overlap
                if self._paths_overlap(dir1, dir2):
                    # These directories conflict
                    files2 = by_dir[dir2]
                    for f1 in files1:
                        for f2 in files2:
                            conflict_pairs.append([str(f1), str(f2)])
                    conflicts = True

            if not conflicts and len(files1) > 0:
                # This directory is independent
                independent_sets.append([str(f) for f in files1])

        # If no independent sets found, each file is its own set
        if len(independent_sets) == 0 and len(changes) > 0:
            independent_sets = [[str(c)] for c in changes]

        return CommutativityResult(
            independent_sets=independent_sets,
            conflict_pairs=conflict_pairs
        )

    def _paths_overlap(self, p1: Path, p2: Path) -> bool:
        """Check if two paths overlap (one is ancestor of other).

        Args:
            p1: First path
            p2: Second path

        Returns:
            True if paths overlap
        """
        try:
            # Check if one is relative to the other
            p1.relative_to(p2)
            return True
        except ValueError:
            pass

        try:
            p2.relative_to(p1)
            return True
        except ValueError:
            pass

        return False
