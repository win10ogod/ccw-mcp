"""Delta minimization - find minimal change set that reproduces failure"""

import re
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class DeltaMinResult:
    """Result of delta minimization"""
    minimal_patch: str
    replay_ok: bool
    root_hash: str
    iterations: int


class DeltaMinimizer:
    """Delta minimization engine using delta debugging"""

    def __init__(self):
        pass

    def minimize(
        self,
        changes: List[Path],
        test_func: Callable[[List[Path]], bool],
        budget_ms: int = 120000
    ) -> DeltaMinResult:
        """Minimize change set to smallest that reproduces failure.

        Args:
            changes: List of changed files
            test_func: Function that returns True if change set causes failure
            budget_ms: Time budget in milliseconds

        Returns:
            DeltaMinResult with minimal change set
        """
        import time
        start_time = time.time()
        budget_sec = budget_ms / 1000.0

        # Delta debugging algorithm
        minimal = changes.copy()
        iterations = 0

        while True:
            iterations += 1

            # Check budget
            if (time.time() - start_time) > budget_sec:
                break

            # Try to reduce by removing each file
            reduced = False
            for i in range(len(minimal)):
                # Try without this file
                candidate = minimal[:i] + minimal[i+1:]

                if len(candidate) == 0:
                    continue

                # Test
                if test_func(candidate):
                    # Still fails without this file - remove it
                    minimal = candidate
                    reduced = True
                    break

            # If no reduction, we're done
            if not reduced:
                break

        # Generate minimal patch (simplified)
        minimal_patch = "\n".join([f"--- {p}" for p in minimal])

        return DeltaMinResult(
            minimal_patch=minimal_patch,
            replay_ok=test_func(minimal),
            root_hash="",  # Would calculate actual hash
            iterations=iterations
        )
