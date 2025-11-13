"""Portable Counterfactual Execution Layer (fallback for non-Linux)"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from ..util import ProcessTracer, ResourceUsage


@dataclass
class PortableCEL:
    """Portable CEL using directory copy (macOS/Windows fallback)"""

    workspace: Path
    base_dir: Optional[Path] = None
    sandbox_dir: Path = field(init=False)
    _temp_root: Optional[Path] = None

    def __post_init__(self):
        """Initialize sandbox directory"""
        if self.base_dir is None:
            self.base_dir = self.workspace

        # Create temporary sandbox
        self._temp_root = Path(tempfile.mkdtemp(prefix="ccw-mcp-"))
        self.sandbox_dir = self._temp_root / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Copy base to sandbox
        if self.base_dir.exists():
            shutil.copytree(
                self.base_dir,
                self.sandbox_dir,
                dirs_exist_ok=True,
                symlinks=True
            )

    def mount(self) -> Path:
        """Return sandbox directory (already prepared).

        Returns:
            Path to sandbox
        """
        return self.sandbox_dir

    def unmount(self):
        """No-op for portable implementation"""
        pass

    def execute(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_ms: int = 600000,
        stdin: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute command in sandbox.

        Args:
            cmd: Command and arguments
            cwd: Working directory (relative to sandbox)
            env: Environment variables
            timeout_ms: Timeout in milliseconds
            stdin: Standard input

        Returns:
            Execution result with stdout, stderr, exit_code, usage, touched
        """
        # Prepare working directory
        if cwd is None:
            work_cwd = self.sandbox_dir
        elif cwd.is_absolute():
            work_cwd = self.sandbox_dir / cwd.relative_to(cwd.anchor)
        else:
            work_cwd = self.sandbox_dir / cwd

        work_cwd.mkdir(parents=True, exist_ok=True)

        # Prepare environment
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        # Snapshot files before execution
        before_files = self._snapshot_files()

        # Track resources
        tracer = ProcessTracer()
        timeout_sec = timeout_ms / 1000.0

        try:
            # Execute command
            proc = subprocess.Popen(
                cmd,
                cwd=str(work_cwd),
                env=exec_env,
                stdin=subprocess.PIPE if stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Attach tracer
            tracer.attach(proc.pid)

            # Communicate with timeout
            stdout, stderr = proc.communicate(input=stdin, timeout=timeout_sec)
            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = -1
        except Exception as e:
            stdout = ""
            stderr = str(e)
            exit_code = -1

        # Get resource usage
        usage = tracer.get_usage()

        # Snapshot files after execution
        after_files = self._snapshot_files()

        # Detect touched files
        touched = self._detect_changes(before_files, after_files)

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "usage": {
                "cpu_ms": usage.cpu_ms,
                "rss_max_kb": usage.rss_max_kb,
                "io_read_kb": usage.io_read_kb,
                "io_write_kb": usage.io_write_kb,
            },
            "touched": touched
        }

    def _snapshot_files(self) -> Dict[Path, float]:
        """Create snapshot of file modification times.

        Returns:
            Dict mapping file paths to modification times
        """
        snapshot = {}
        if self.sandbox_dir.exists():
            for item in self.sandbox_dir.rglob('*'):
                if item.is_file():
                    try:
                        snapshot[item.relative_to(self.sandbox_dir)] = item.stat().st_mtime
                    except (OSError, ValueError):
                        pass
        return snapshot

    def _detect_changes(
        self,
        before: Dict[Path, float],
        after: Dict[Path, float]
    ) -> Dict[str, List[str]]:
        """Detect file changes between snapshots.

        Args:
            before: Snapshot before execution
            after: Snapshot after execution

        Returns:
            Dict with 'read' and 'written' file lists
        """
        written = []

        # New or modified files
        for path, mtime in after.items():
            if path not in before or before[path] != mtime:
                written.append(str(path))

        # For reads, we approximate as all existing files (simplified)
        read = [str(p) for p in before.keys()]

        return {
            "read": read,
            "written": written
        }

    def get_changes(self) -> List[Path]:
        """Get list of changed files.

        Returns:
            List of changed file paths (relative)
        """
        changes = []

        # Compare with base
        if not self.base_dir.exists():
            # All files are new
            for item in self.sandbox_dir.rglob('*'):
                if item.is_file():
                    changes.append(item.relative_to(self.sandbox_dir))
        else:
            # Check modifications
            for item in self.sandbox_dir.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(self.sandbox_dir)
                    base_file = self.base_dir / rel_path

                    # New file or modified
                    if not base_file.exists():
                        changes.append(rel_path)
                    else:
                        # Compare content
                        try:
                            if item.read_bytes() != base_file.read_bytes():
                                changes.append(rel_path)
                        except (OSError, IOError):
                            pass

        return changes

    def cleanup(self):
        """Clean up sandbox"""
        if self._temp_root and self._temp_root.exists():
            shutil.rmtree(self._temp_root, ignore_errors=True)

    @classmethod
    def rehydrate(
        cls,
        workspace: Path,
        base_dir: Optional[Path],
        mount_point: Path,
    ) -> "PortableCEL":
        """Rehydrate a PortableCEL from a persisted sandbox."""

        obj = cls.__new__(cls)
        obj.workspace = workspace
        obj.base_dir = base_dir or workspace
        obj._temp_root = mount_point.parent
        obj.sandbox_dir = mount_point
        return obj
