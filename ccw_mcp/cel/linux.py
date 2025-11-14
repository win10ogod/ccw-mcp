"""Linux-specific Counterfactual Execution Layer using overlayfs"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from ..util import ProcessTracer, ResourceUsage


@dataclass
class LinuxCEL:
    """Linux Counterfactual Execution Layer using overlayfs and namespaces"""

    workspace: Path
    base_dir: Optional[Path] = None
    overlay_dir: Path = field(init=False)
    upper_dir: Path = field(init=False)
    work_dir: Path = field(init=False)
    mount_point: Path = field(init=False)
    _temp_root: Optional[Path] = None
    _is_mounted: bool = False

    def __post_init__(self):
        """Initialize overlay directories"""
        if self.base_dir is None:
            self.base_dir = self.workspace

        # Create temporary directory for overlay
        self._temp_root = Path(tempfile.mkdtemp(prefix="ccw-mcp-"))
        self.overlay_dir = self._temp_root / "overlay"
        self.upper_dir = self.overlay_dir / "upper"
        self.work_dir = self.overlay_dir / "work"
        self.mount_point = self.overlay_dir / "merged"

        self.upper_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.mount_point.mkdir(parents=True, exist_ok=True)

    def mount(self) -> Path:
        """Mount overlayfs.

        Returns:
            Path to mount point
        """
        if self._is_mounted:
            return self.mount_point

        # Try overlayfs mount (requires permissions)
        try:
            # overlayfs mount options
            options = (
                f"lowerdir={self.base_dir},"
                f"upperdir={self.upper_dir},"
                f"workdir={self.work_dir}"
            )

            result = subprocess.run(
                ["mount", "-t", "overlay", "overlay",
                 "-o", options, str(self.mount_point)],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                self._is_mounted = True
                return self.mount_point
            else:
                # Fallback: copy-on-write using directory copy
                return self._fallback_copy()

        except (subprocess.SubprocessError, PermissionError):
            # Fallback: copy-on-write using directory copy
            return self._fallback_copy()

    def _fallback_copy(self) -> Path:
        """Fallback to directory copy when overlayfs is not available"""
        # Copy base to mount point
        if self.base_dir.exists():
            shutil.copytree(
                self.base_dir,
                self.mount_point,
                dirs_exist_ok=True,
                symlinks=True
            )
        self._is_mounted = True
        return self.mount_point

    def unmount(self):
        """Unmount overlayfs"""
        if not self._is_mounted:
            return

        # Try to unmount
        try:
            subprocess.run(
                ["umount", str(self.mount_point)],
                capture_output=True,
                check=False
            )
        except subprocess.SubprocessError:
            pass

        self._is_mounted = False

    def execute(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_ms: int = 600000,
        stdin: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute command in counterfactual environment.

        Args:
            cmd: Command and arguments
            cwd: Working directory (relative to mount point)
            env: Environment variables
            timeout_ms: Timeout in milliseconds
            stdin: Standard input

        Returns:
            Execution result with stdout, stderr, exit_code, usage, touched
        """
        # Ensure mounted
        mount = self.mount()

        # Prepare working directory
        if cwd is None:
            work_cwd = mount
        elif cwd.is_absolute():
            # Map absolute path to mount
            work_cwd = mount / cwd.relative_to(cwd.anchor)
        else:
            work_cwd = mount / cwd

        work_cwd.mkdir(parents=True, exist_ok=True)

        # Prepare environment
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

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

        # Collect touched files
        touched = self._collect_touched_files()

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

    def _collect_touched_files(self) -> Dict[str, List[str]]:
        """Collect touched files in overlay.

        Returns:
            Dict with 'read' and 'written' file lists
        """
        written = []

        # Files in upper dir are written
        if self.upper_dir.exists():
            for item in self.upper_dir.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(self.upper_dir)
                    written.append(str(rel_path))

        # For reads, we would need strace or similar - simplified here
        read = []

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

        if self.upper_dir.exists():
            for item in self.upper_dir.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(self.upper_dir)
                    changes.append(rel_path)

        return changes

    def cleanup(self):
        """Clean up overlay and temporary files"""
        self.unmount()

        if self._temp_root and self._temp_root.exists():
            shutil.rmtree(self._temp_root, ignore_errors=True)

    @classmethod
    def rehydrate(
        cls,
        workspace: Path,
        base_dir: Optional[Path],
        mount_point: Path,
    ) -> "LinuxCEL":
        """Rehydrate a LinuxCEL from a persisted sandbox."""

        obj = cls.__new__(cls)
        obj.workspace = workspace
        obj.base_dir = base_dir or workspace
        obj.mount_point = mount_point
        obj.overlay_dir = mount_point.parent
        obj.upper_dir = obj.overlay_dir / "upper"
        obj.work_dir = obj.overlay_dir / "work"
        obj._temp_root = obj.overlay_dir.parent
        obj._is_mounted = mount_point.exists()
        return obj
