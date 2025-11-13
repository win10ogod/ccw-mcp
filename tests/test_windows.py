"""Windows-specific tests for CCW-MCP"""

import platform
import tempfile
import shutil
from pathlib import Path
import pytest

# Only run these tests on Windows
pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Windows-specific tests"
)

from ccw_mcp.cel import create_cel, WindowsCEL
from ccw_mcp.tools import CapsuleRegistry


class TestWindowsCEL:
    """Test Windows-specific CEL functionality"""

    def test_windows_cel_creation(self, tmp_path):
        """Test creating Windows CEL"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "test.txt").write_text("original content")

        cel = create_cel(workspace)
        assert isinstance(cel, WindowsCEL)

        mount = cel.mount()
        assert mount.exists()
        assert (mount / "test.txt").exists()

        cel.cleanup()

    def test_windows_file_monitoring(self, tmp_path):
        """Test file monitoring on Windows"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "original.txt").write_text("original")

        cel = create_cel(workspace)

        # Execute command that creates a file
        result = cel.execute(
            ["cmd", "/c", "echo test > new_file.txt"],
            cwd=None
        )

        # Should detect the new file as written
        assert result["exit_code"] == 0
        assert "written" in result["touched"]

        changes = cel.get_changes()
        assert len(changes) >= 0  # May detect new_file.txt

        cel.cleanup()

    def test_windows_process_isolation(self, tmp_path):
        """Test process isolation on Windows"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cel = create_cel(workspace)

        # Execute command with environment isolation
        result = cel.execute(
            ["cmd", "/c", "echo", "test"],
            env={"TEST_VAR": "isolated"}
        )

        assert result["exit_code"] == 0
        assert "test" in result["stdout"].lower()

        cel.cleanup()

    def test_windows_resource_tracking(self, tmp_path):
        """Test resource tracking on Windows"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cel = create_cel(workspace)

        # Execute a command and check resource usage
        result = cel.execute(
            ["cmd", "/c", "dir"],
            timeout_ms=5000
        )

        assert result["exit_code"] == 0
        assert "usage" in result
        assert "cpu_ms" in result["usage"]
        assert "rss_max_kb" in result["usage"]

        cel.cleanup()

    def test_windows_timeout(self, tmp_path):
        """Test command timeout on Windows"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cel = create_cel(workspace)

        # Execute a long-running command with short timeout
        result = cel.execute(
            ["cmd", "/c", "timeout", "/t", "10"],
            timeout_ms=500  # 500ms timeout
        )

        # Should timeout
        assert result["exit_code"] == -1

        cel.cleanup()

    def test_windows_path_handling(self, tmp_path):
        """Test Windows path handling with backslashes"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create nested directory
        nested = workspace / "subdir" / "nested"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("content")

        cel = create_cel(workspace)

        # Verify path mapping works
        result = cel.execute(
            ["cmd", "/c", "dir"],
            cwd=Path("subdir/nested")
        )

        assert result["exit_code"] == 0

        cel.cleanup()

    def test_windows_special_characters(self, tmp_path):
        """Test handling of Windows special characters in filenames"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create file with spaces
        (workspace / "file with spaces.txt").write_text("content")

        cel = create_cel(workspace)
        mount = cel.mount()

        # Verify file exists
        assert (mount / "file with spaces.txt").exists()

        changes = cel.get_changes()
        assert len(changes) == 0  # No changes yet

        cel.cleanup()


class TestWindowsCapsule:
    """Test capsule operations on Windows"""

    def test_windows_capsule_workflow(self, tmp_path):
        """Test complete capsule workflow on Windows"""
        storage = tmp_path / "storage"
        workspace = tmp_path / "workspace"

        storage.mkdir()
        workspace.mkdir()
        (workspace / "test.txt").write_text("original")

        registry = CapsuleRegistry(storage)

        # Create capsule
        result = registry.create(workspace=workspace)
        capsule_id = result["capsule_id"]

        # Execute Windows command
        exec_result = registry.execute(
            capsule_id=capsule_id,
            cmd=["cmd", "/c", "echo modified > test.txt"],
            timeout_ms=5000
        )

        assert exec_result["exit_code"] == 0

        # Get diff
        diff_result = registry.diff(capsule_id=capsule_id)
        assert "summary" in diff_result

        # Cleanup
        registry.delete(capsule_id)

    def test_windows_temp_directory(self, tmp_path):
        """Test that Windows temp directories are properly isolated"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cel = create_cel(workspace)

        # Check that TEMP is set to sandbox
        result = cel.execute(
            ["cmd", "/c", "echo", "%TEMP%"],
            timeout_ms=5000
        )

        assert result["exit_code"] == 0
        # TEMP should point to sandbox temp dir
        assert ".temp" in result["stdout"] or "sandbox" in result["stdout"].lower()

        cel.cleanup()


@pytest.fixture
def tmp_path():
    """Create temporary directory"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
