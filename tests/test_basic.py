"""Basic tests for CCW-MCP components"""

import tempfile
import shutil
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


@pytest.fixture
def tmp_path():
    """Create temporary directory"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
