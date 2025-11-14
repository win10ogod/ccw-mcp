"""Basic tests for CCW-MCP components"""

import tempfile
import shutil
import sys
from pathlib import Path
import pytest

from ccw_mcp.util import hash_file, hash_bytes, generate_unified_diff
from ccw_mcp.cel import create_cel
from ccw_mcp.policy import PolicyEngine, PolicyRule
from ccw_mcp.tools import CapsuleRegistry


class TestHashing:
    """Test hashing utilities"""

    def test_hash_bytes(self):
        """Test hashing bytes"""
        data = b"Hello, World!"
        hash_result = hash_bytes(data)
        assert hash_result.startswith("blake3:")
        assert len(hash_result) > 10

    def test_hash_file(self, tmp_path):
        """Test hashing file"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        hash_result = hash_file(test_file)
        assert hash_result.startswith("blake3:")

        # Same content should produce same hash
        hash_result2 = hash_file(test_file)
        assert hash_result == hash_result2


class TestCEL:
    """Test Counterfactual Execution Layer"""

    def test_cel_creation(self, tmp_path):
        """Test creating CEL"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cel = create_cel(workspace)
        mount = cel.mount()

        assert mount.exists()
        cel.cleanup()

    def test_cel_execution(self, tmp_path):
        """Test executing command in CEL"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "test.txt").write_text("original")

        cel = create_cel(workspace)
        result = cel.execute(["echo", "test"])

        assert result["exit_code"] == 0
        assert "test" in result["stdout"]

        cel.cleanup()


class TestPolicy:
    """Test policy engine"""

    def test_policy_creation(self):
        """Test creating policy"""
        engine = PolicyEngine()

        policy = PolicyRule(
            name="test",
            max_rss_mb=1024,
            deny_paths=["~/.ssh/*"]
        )

        engine.add_policy(policy)
        retrieved = engine.get_policy("test")

        assert retrieved is not None
        assert retrieved.name == "test"
        assert retrieved.max_rss_mb == 1024

    def test_policy_validation(self):
        """Test policy validation"""
        engine = PolicyEngine()

        report = engine.validate(
            policy_names=["baseline"],
            changed_paths=[Path("test.txt")],
            usage={"cpu_ms": 100, "rss_max_kb": 1024}
        )

        assert report is not None
        assert isinstance(report.passed, bool)


class TestCapsule:
    """Test capsule management"""

    def test_capsule_lifecycle(self, tmp_path):
        """Test creating and managing capsule"""
        storage = tmp_path / "storage"
        storage.mkdir()

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "test.txt").write_text("content")

        registry = CapsuleRegistry(storage)

        # Create
        result = registry.create(workspace=workspace)
        assert "capsule_id" in result
        capsule_id = result["capsule_id"]

        # List
        capsules = registry.list()
        assert capsule_id in capsules

        # Delete
        deleted = registry.delete(capsule_id)
        assert deleted is True

        capsules = registry.list()
        assert capsule_id not in capsules

    def test_capsule_persistence_across_instances(self, tmp_path):
        """Capsules should be accessible after registry reinitialization."""

        storage = tmp_path / "storage"
        storage.mkdir()

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        registry1 = CapsuleRegistry(storage)
        create_result = registry1.create(workspace=workspace)
        capsule_id = create_result["capsule_id"]
        mount_path = Path(create_result["mount"])
        (mount_path / "marker.txt").write_text("hello")

        registry2 = CapsuleRegistry(storage)
        assert capsule_id in registry2.list()

        exec_result = registry2.execute(
            capsule_id,
            [sys.executable, "-c", "print('ping')"],
        )

        assert exec_result["exit_code"] == 0
        assert "ping" in exec_result["stdout"]

        diff_result = registry2.diff(capsule_id)
        assert "summary" in diff_result

        registry2.delete(capsule_id)

    def test_capsule_recreates_missing_mount_on_windows(self, tmp_path, monkeypatch):
        """Windows capsules should recreate sandboxes if the mount disappears."""

        storage = tmp_path / "storage"
        workspace = tmp_path / "workspace"

        storage.mkdir()
        workspace.mkdir()
        (workspace / "baseline.txt").write_text("baseline")

        import ccw_mcp.cel as cel_module

        monkeypatch.setattr(cel_module.platform, "system", lambda: "Windows")

        registry1 = CapsuleRegistry(storage)
        create_result = registry1.create(workspace=workspace)
        capsule_id = create_result["capsule_id"]
        mount_path = Path(create_result["mount"])
        assert mount_path.exists()

        shutil.rmtree(mount_path.parent, ignore_errors=True)

        registry2 = CapsuleRegistry(storage)
        exec_result = registry2.execute(
            capsule_id,
            [sys.executable, "-c", "print('ping')"],
        )

        assert exec_result["exit_code"] == 0
        assert "ping" in exec_result["stdout"]

        diff_result = registry2.diff(capsule_id)
        assert "summary" in diff_result

        metadata_entry = registry2.get(capsule_id)
        assert metadata_entry is not None
        metadata, _ = metadata_entry
        assert metadata.mount_point is not None
        assert metadata.mount_point.exists()

        registry2.delete(capsule_id)


@pytest.fixture
def tmp_path():
    """Create temporary directory"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
