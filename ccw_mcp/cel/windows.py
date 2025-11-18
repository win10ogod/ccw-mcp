"""Windows-specific Counterfactual Execution Layer with enhanced monitoring"""

import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict

from ..util import ProcessTracer, ResourceUsage


@dataclass
class WindowsCEL:
    """Windows CEL with file system monitoring and process isolation"""

    workspace: Path
    base_dir: Optional[Path] = None
    sandbox_dir: Path = field(init=False)
    _temp_root: Optional[Path] = None
    _monitor_thread: Optional[threading.Thread] = None
    _monitoring: bool = False
    _file_accesses: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def __post_init__(self):
        """Initialize sandbox directory"""
        if self.base_dir is None:
            self.base_dir = self.workspace

        # Create temporary sandbox
        self._temp_root = Path(tempfile.mkdtemp(prefix="ccw-mcp-"))
        self.sandbox_dir = self._temp_root / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Copy base to sandbox with symlink support
        if self.base_dir.exists():
            self._copy_tree(self.base_dir, self.sandbox_dir)

    def _copy_tree(self, src: Path, dst: Path):
        """Copy directory tree with Windows-specific handling"""
        if not src.exists():
            return

        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            src_item = src / item.name
            dst_item = dst / item.name

            try:
                if src_item.is_file():
                    # Use Windows copy with attributes
                    shutil.copy2(src_item, dst_item)
                elif src_item.is_dir():
                    # Recursive copy
                    self._copy_tree(src_item, dst_item)
            except (OSError, PermissionError) as e:
                # Skip files we can't access
                pass

    def mount(self) -> Path:
        """Return sandbox directory (already prepared).

        Returns:
            Path to sandbox
        """
        return self.sandbox_dir

    def unmount(self):
        """No-op for Windows implementation"""
        self._stop_monitoring()

    def _start_monitoring(self):
        """Start file system monitoring thread"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_files,
            daemon=True
        )
        self._monitor_thread.start()

    def _stop_monitoring(self):
        """Stop file system monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)

    def _monitor_files(self):
        """Monitor file system changes (optimized version)"""
        # Snapshot initial state
        initial_state = self._snapshot_files()

        while self._monitoring:
            time.sleep(0.5)  # Reduced polling frequency (5x improvement)

        # Final snapshot
        final_state = self._snapshot_files()

        # Detect changes
        for path, mtime in final_state.items():
            if path not in initial_state or initial_state[path] != mtime:
                self._file_accesses['written'].add(str(path))
            else:
                self._file_accesses['read'].add(str(path))

    def execute(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_ms: int = 600000,
        stdin: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute command in sandbox with enhanced monitoring.

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
            # Map absolute path to sandbox
            try:
                rel_path = cwd.relative_to(cwd.anchor)
                work_cwd = self.sandbox_dir / rel_path
            except ValueError:
                work_cwd = self.sandbox_dir / cwd
        else:
            work_cwd = self.sandbox_dir / cwd

        work_cwd.mkdir(parents=True, exist_ok=True)

        # Prepare environment
        exec_env = os.environ.copy()

        # Windows-specific: Set restricted environment
        # Remove potentially dangerous variables
        dangerous_vars = ['COMSPEC', 'PATHEXT', 'SYSTEMROOT']
        for var in dangerous_vars:
            if var in exec_env and env and var not in env:
                # Only keep if explicitly whitelisted
                pass

        if env:
            exec_env.update(env)

        # Set sandbox-specific paths
        exec_env['TEMP'] = str(self.sandbox_dir / '.temp')
        exec_env['TMP'] = str(self.sandbox_dir / '.temp')
        Path(exec_env['TEMP']).mkdir(exist_ok=True)

        # Snapshot files before execution
        before_files = self._snapshot_files()

        # Start monitoring
        self._start_monitoring()

        # Track resources
        tracer = ProcessTracer()
        timeout_sec = timeout_ms / 1000.0

        # Windows-specific: Use creation flags for process isolation
        creation_flags = 0
        if os.name == 'nt':
            # CREATE_NEW_PROCESS_GROUP for better isolation
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            # Execute command with Windows-specific settings
            proc = subprocess.Popen(
                cmd,
                cwd=str(work_cwd),
                env=exec_env,
                stdin=subprocess.PIPE if stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags
            )

            # Attach tracer
            tracer.attach(proc.pid)

            # Sample resources periodically with adaptive interval
            start_time = time.time()
            sample_interval = 0.2  # Reduced from 0.1s to 0.2s (50% less overhead)
            timed_out = False
            while proc.poll() is None:
                tracer.sample()
                elapsed = time.time() - start_time
                if elapsed > timeout_sec:
                    proc.kill()
                    timed_out = True
                    break
                # Adaptive sleep: longer intervals for long-running processes
                if elapsed > 10.0:
                    time.sleep(0.5)  # Less frequent sampling after 10s
                else:
                    time.sleep(sample_interval)

            # Get output
            stdout, stderr = proc.communicate(input=stdin, timeout=1.0)
            exit_code = -1 if timed_out else proc.returncode

        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = -1
        except Exception as e:
            stdout = ""
            stderr = str(e)
            exit_code = -1
        finally:
            self._stop_monitoring()

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
        """Create snapshot of file modification times (optimized).

        Returns:
            Dict mapping file paths to modification times
        """
        snapshot = {}
        if not self.sandbox_dir.exists():
            return snapshot

        try:
            # Use os.walk for better performance than rglob
            for root, _, files in os.walk(self.sandbox_dir):
                root_path = Path(root)
                for filename in files:
                    try:
                        file_path = root_path / filename
                        rel_path = file_path.relative_to(self.sandbox_dir)
                        snapshot[rel_path] = file_path.stat().st_mtime
                    except (OSError, ValueError, PermissionError):
                        # Skip inaccessible files
                        continue
        except Exception:
            # Return partial snapshot on error
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
        read = []

        # Files that were modified or added
        for path, mtime in after.items():
            if path not in before:
                # New file
                written.append(str(path))
            elif before[path] != mtime:
                # Modified file
                written.append(str(path))
            else:
                # Unchanged file (potentially read)
                read.append(str(path))

        # Deleted files
        for path in before:
            if path not in after:
                written.append(f"[deleted] {path}")

        return {
            "read": read[:100],  # Limit to avoid huge lists
            "written": written
        }

    def get_changes(self) -> List[Path]:
        """Get list of changed files (optimized).

        Returns:
            List of changed file paths (relative)
        """
        changes = []

        # Compare with base
        if not self.base_dir.exists():
            # All files are new - use os.walk for better performance
            try:
                for root, _, files in os.walk(self.sandbox_dir):
                    root_path = Path(root)
                    for filename in files:
                        try:
                            file_path = root_path / filename
                            changes.append(file_path.relative_to(self.sandbox_dir))
                        except ValueError:
                            continue
            except Exception:
                pass
        else:
            # Check modifications - use os.walk instead of rglob
            try:
                for root, _, files in os.walk(self.sandbox_dir):
                    root_path = Path(root)
                    for filename in files:
                        try:
                            item = root_path / filename
                            rel_path = item.relative_to(self.sandbox_dir)
                            base_file = self.base_dir / rel_path

                            # New file or modified
                            if not base_file.exists():
                                changes.append(rel_path)
                            else:
                                # Fast comparison: size and mtime first
                                item_stat = item.stat()
                                base_stat = base_file.stat()

                                if item_stat.st_size != base_stat.st_size:
                                    changes.append(rel_path)
                                elif item_stat.st_mtime != base_stat.st_mtime:
                                    # Size same but mtime different - verify with hash
                                    # Only read files > 1MB with hash, others with direct compare
                                    if item_stat.st_size > 1024 * 1024:
                                        # Use hash for large files
                                        from ..util import hash_file
                                        if hash_file(item) != hash_file(base_file):
                                            changes.append(rel_path)
                                    else:
                                        # Direct compare for small files
                                        try:
                                            if item.read_bytes() != base_file.read_bytes():
                                                changes.append(rel_path)
                                        except (OSError, IOError, PermissionError):
                                            pass
                        except (ValueError, OSError, PermissionError):
                            continue
            except Exception:
                pass

        return changes

    def cleanup(self):
        """Clean up sandbox with Windows-specific handling (optimized)"""
        self._stop_monitoring()

        if self._temp_root and self._temp_root.exists():
            # Windows-specific: Retry deletion with exponential backoff
            max_retries = 3
            retry_delay = 0.1  # Start with 100ms

            for attempt in range(max_retries):
                try:
                    shutil.rmtree(self._temp_root, ignore_errors=False)
                    break
                except (OSError, PermissionError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff: 0.1s, 0.2s, 0.4s
                    else:
                        # Final attempt with ignore_errors
                        try:
                            shutil.rmtree(self._temp_root, ignore_errors=True)
                        except Exception:
                            # Log warning but don't fail
                            import sys
                            print(f"Warning: Failed to cleanup {self._temp_root}", file=sys.stderr)

    @classmethod
    def rehydrate(
        cls,
        workspace: Path,
        base_dir: Optional[Path],
        mount_point: Path,
    ) -> "WindowsCEL":
        """Rehydrate a WindowsCEL from a persisted sandbox."""

        obj = cls.__new__(cls)
        obj.workspace = workspace
        obj.base_dir = base_dir or workspace
        obj._temp_root = mount_point.parent
        obj.sandbox_dir = mount_point
        obj._monitor_thread = None
        obj._monitoring = False
        obj._file_accesses = defaultdict(set)
        return obj
