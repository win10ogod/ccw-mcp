"""Promote functionality - apply changes to real filesystem"""

import shutil
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

from ..policy import PolicyEngine, PolicyReport


@dataclass
class PromoteResult:
    """Result of promote operation"""
    promoted: bool
    applied: List[str]
    policy_report: Dict[str, Any]
    error: str = ""


class PromoteEngine:
    """Engine for promoting capsule changes to real filesystem"""

    def __init__(self, policy_engine: PolicyEngine):
        """Initialize promote engine.

        Args:
            policy_engine: Policy engine for validation
        """
        self.policy_engine = policy_engine

    def promote(
        self,
        capsule_mount: Path,
        target_dir: Path,
        changes: List[Path],
        policies: List[str],
        usage: Dict[str, int],
        replay_hash: str = None,
        expected_hash: str = None,
        dry_run: bool = False
    ) -> PromoteResult:
        """Promote capsule changes to target directory.

        Args:
            capsule_mount: Capsule mount point
            target_dir: Target directory to promote to
            changes: List of changed files
            policies: List of policy names to validate
            usage: Resource usage dict
            replay_hash: Hash from replay
            expected_hash: Expected hash
            dry_run: If True, don't actually apply changes

        Returns:
            PromoteResult with status and details
        """
        # Validate against policies
        report = self.policy_engine.validate(
            policy_names=policies,
            changed_paths=changes,
            usage=usage,
            replay_hash=replay_hash,
            expected_hash=expected_hash,
            workspace=target_dir
        )

        # Convert report to dict
        report_dict = {
            "passed": report.passed,
            "tests_ok": report.tests_ok,
            "replay_ok": report.replay_ok,
            "resource_ok": report.resource_ok,
            "paths_ok": report.paths_ok,
            "deny_paths": report.deny_paths,
            "resource_violations": report.resource_violations,
            "test_failures": report.test_failures,
            "details": report.details
        }

        # If policy failed, don't promote
        if not report.passed:
            return PromoteResult(
                promoted=False,
                applied=[],
                policy_report=report_dict,
                error=f"Policy validation failed: {report.details}"
            )

        # If dry run, stop here
        if dry_run:
            return PromoteResult(
                promoted=False,
                applied=[str(p) for p in changes],
                policy_report=report_dict,
                error="Dry run - no changes applied"
            )

        # Apply changes atomically
        applied = []
        try:
            for change in changes:
                src_file = capsule_mount / change
                dst_file = target_dir / change

                if not src_file.exists():
                    continue

                # Ensure parent directory exists
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # Atomic write: write to temp, then rename
                temp_file = dst_file.parent / f".{dst_file.name}.tmp"

                try:
                    # Copy to temp
                    shutil.copy2(src_file, temp_file)

                    # Atomic rename
                    temp_file.replace(dst_file)

                    applied.append(str(change))

                except (IOError, OSError) as e:
                    # Clean up temp file
                    if temp_file.exists():
                        temp_file.unlink()
                    raise e

            return PromoteResult(
                promoted=True,
                applied=applied,
                policy_report=report_dict,
                error=""
            )

        except Exception as e:
            return PromoteResult(
                promoted=False,
                applied=applied,
                policy_report=report_dict,
                error=f"Failed to apply changes: {str(e)}"
            )
