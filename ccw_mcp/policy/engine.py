"""Policy Engine for validation and gating"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from fnmatch import fnmatch


@dataclass
class PolicyRule:
    """Policy rule definition"""
    name: str = "baseline"
    max_rss_mb: Optional[int] = None
    max_cpu_ms: Optional[int] = None
    deny_paths: List[str] = field(default_factory=list)
    require_tests: List[str] = field(default_factory=list)
    require_replay_ok: bool = True


@dataclass
class PolicyReport:
    """Policy validation report"""
    passed: bool = False
    tests_ok: bool = False
    replay_ok: bool = False
    resource_ok: bool = True
    paths_ok: bool = True
    deny_paths: List[str] = field(default_factory=list)
    resource_violations: List[str] = field(default_factory=list)
    test_failures: List[str] = field(default_factory=list)
    details: str = ""


class PolicyEngine:
    """Policy engine for validation"""

    def __init__(self):
        self.policies: Dict[str, PolicyRule] = {
            "baseline": PolicyRule(
                name="baseline",
                max_rss_mb=2048,
                deny_paths=["~/.ssh/*", "~/.aws/*", "/etc/passwd"],
                require_tests=[],
                require_replay_ok=False
            ),
            "strict": PolicyRule(
                name="strict",
                max_rss_mb=1024,
                max_cpu_ms=60000,
                deny_paths=["~/.ssh/*", "~/.aws/*", "/etc/*", "~/.config/*"],
                require_tests=["uv run pytest -q"],
                require_replay_ok=True
            )
        }

    def add_policy(self, policy: PolicyRule):
        """Add or update a policy rule.

        Args:
            policy: Policy rule to add
        """
        self.policies[policy.name] = policy

    def get_policy(self, name: str) -> Optional[PolicyRule]:
        """Get policy by name.

        Args:
            name: Policy name

        Returns:
            Policy rule or None
        """
        return self.policies.get(name)

    def validate(
        self,
        policy_names: List[str],
        changed_paths: List[Path],
        usage: Dict[str, int],
        replay_hash: Optional[str] = None,
        expected_hash: Optional[str] = None,
        workspace: Optional[Path] = None
    ) -> PolicyReport:
        """Validate against policies.

        Args:
            policy_names: List of policy names to validate against
            changed_paths: List of changed file paths
            usage: Resource usage dict (cpu_ms, rss_max_kb, etc.)
            replay_hash: Hash from replay
            expected_hash: Expected hash
            workspace: Workspace path for running tests

        Returns:
            Policy validation report
        """
        report = PolicyReport()

        # Merge policies
        merged = self._merge_policies(policy_names)
        if not merged:
            report.details = f"No valid policies found in {policy_names}"
            return report

        # Check paths
        deny_violations = []
        for path in changed_paths:
            for pattern in merged.deny_paths:
                if self._match_path(path, pattern):
                    deny_violations.append(str(path))
                    break

        report.deny_paths = deny_violations
        report.paths_ok = len(deny_violations) == 0

        # Check resources
        resource_violations = []
        if merged.max_rss_mb:
            rss_mb = usage.get("rss_max_kb", 0) / 1024
            if rss_mb > merged.max_rss_mb:
                resource_violations.append(
                    f"RSS {rss_mb:.1f}MB exceeds limit {merged.max_rss_mb}MB"
                )

        if merged.max_cpu_ms:
            cpu_ms = usage.get("cpu_ms", 0)
            if cpu_ms > merged.max_cpu_ms:
                resource_violations.append(
                    f"CPU {cpu_ms}ms exceeds limit {merged.max_cpu_ms}ms"
                )

        report.resource_violations = resource_violations
        report.resource_ok = len(resource_violations) == 0

        # Check replay
        if merged.require_replay_ok:
            if replay_hash and expected_hash:
                report.replay_ok = replay_hash == expected_hash
            else:
                report.replay_ok = False
        else:
            report.replay_ok = True

        # Run tests
        test_failures = []
        if merged.require_tests and workspace:
            for test_cmd in merged.require_tests:
                success = self._run_test(test_cmd, workspace)
                if not success:
                    test_failures.append(test_cmd)

        report.test_failures = test_failures
        report.tests_ok = len(test_failures) == 0 or len(merged.require_tests) == 0

        # Overall pass
        report.passed = (
            report.paths_ok and
            report.resource_ok and
            report.replay_ok and
            report.tests_ok
        )

        # Build details
        details = []
        if not report.paths_ok:
            details.append(f"Denied paths: {', '.join(deny_violations)}")
        if not report.resource_ok:
            details.append(f"Resource violations: {'; '.join(resource_violations)}")
        if not report.replay_ok:
            details.append("Replay hash mismatch")
        if not report.tests_ok:
            details.append(f"Test failures: {', '.join(test_failures)}")

        report.details = "; ".join(details) if details else "All checks passed"

        return report

    def _merge_policies(self, names: List[str]) -> Optional[PolicyRule]:
        """Merge multiple policies (most restrictive wins).

        Args:
            names: List of policy names

        Returns:
            Merged policy rule or None
        """
        policies = [self.policies.get(name) for name in names]
        policies = [p for p in policies if p is not None]

        if not policies:
            return None

        # Start with first policy
        merged = PolicyRule(name="+".join(names))

        # Merge max values (minimum wins - most restrictive)
        rss_values = [p.max_rss_mb for p in policies if p.max_rss_mb]
        merged.max_rss_mb = min(rss_values) if rss_values else None

        cpu_values = [p.max_cpu_ms for p in policies if p.max_cpu_ms]
        merged.max_cpu_ms = min(cpu_values) if cpu_values else None

        # Merge deny paths (union)
        deny_set = set()
        for p in policies:
            deny_set.update(p.deny_paths)
        merged.deny_paths = list(deny_set)

        # Merge tests (union)
        test_set = set()
        for p in policies:
            test_set.update(p.require_tests)
        merged.require_tests = list(test_set)

        # Merge replay requirement (any requires -> require)
        merged.require_replay_ok = any(p.require_replay_ok for p in policies)

        return merged

    def _match_path(self, path: Path, pattern: str) -> bool:
        """Match path against pattern (supports wildcards).

        Args:
            path: Path to check
            pattern: Pattern (may contain * and ?)

        Returns:
            True if path matches pattern
        """
        # Expand home directory
        if pattern.startswith("~/"):
            pattern = str(Path.home() / pattern[2:])

        return fnmatch(str(path), pattern)

    def _run_test(self, cmd: str, workspace: Path) -> bool:
        """Run test command in workspace.

        Args:
            cmd: Test command
            workspace: Workspace directory

        Returns:
            True if test passed
        """
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                timeout=300  # 5 minutes max
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False
