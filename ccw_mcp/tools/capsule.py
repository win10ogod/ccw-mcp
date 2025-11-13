"""Capsule management - core abstraction for counterfactual environments"""

import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from ..cel import create_cel, CEL
from ..util import hash_file, generate_unified_diff, count_changes


@dataclass
class CapsuleMetadata:
    """Metadata for a capsule"""
    capsule_id: str
    workspace: Path
    base_dir: Optional[Path]
    created_at: str
    clock_offset_sec: int = 0
    env_whitelist: List[str] = field(default_factory=list)
    mount_point: Optional[Path] = None


class CapsuleRegistry:
    """Registry for managing capsules"""

    def __init__(self, storage_dir: Path):
        """Initialize capsule registry.

        Args:
            storage_dir: Directory for storing capsule data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.capsules: Dict[str, tuple[CapsuleMetadata, CEL]] = {}

    def create(
        self,
        workspace: Path,
        base: Optional[Path] = None,
        clock_offset_sec: int = 0,
        env_whitelist: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new capsule.

        Args:
            workspace: Workspace directory path
            base: Base directory (defaults to workspace)
            clock_offset_sec: Clock offset in seconds
            env_whitelist: Environment variable whitelist

        Returns:
            Dict with capsule_id, mount, clock
        """
        # Generate capsule ID
        timestamp = int(time.time() * 1000)
        capsule_id = f"cap_{timestamp}"

        # Resolve paths
        workspace = Path(workspace).resolve()
        if base:
            base = Path(base).resolve()

        # Create CEL
        cel = create_cel(workspace=workspace, base_dir=base)
        mount = cel.mount()

        # Create metadata
        metadata = CapsuleMetadata(
            capsule_id=capsule_id,
            workspace=workspace,
            base_dir=base,
            created_at=datetime.now(timezone.utc).isoformat(),
            clock_offset_sec=clock_offset_sec,
            env_whitelist=env_whitelist or [],
            mount_point=mount
        )

        # Store
        self.capsules[capsule_id] = (metadata, cel)

        # Save metadata
        self._save_metadata(capsule_id, metadata)

        return {
            "capsule_id": capsule_id,
            "mount": str(mount),
            "clock": metadata.created_at
        }

    def get(self, capsule_id: str) -> Optional[tuple[CapsuleMetadata, CEL]]:
        """Get capsule by ID.

        Args:
            capsule_id: Capsule identifier

        Returns:
            Tuple of (metadata, cel) or None
        """
        return self.capsules.get(capsule_id)

    def list(self) -> List[str]:
        """List all capsule IDs.

        Returns:
            List of capsule IDs
        """
        return list(self.capsules.keys())

    def delete(self, capsule_id: str) -> bool:
        """Delete a capsule.

        Args:
            capsule_id: Capsule identifier

        Returns:
            True if deleted, False if not found
        """
        entry = self.capsules.get(capsule_id)
        if not entry:
            return False

        metadata, cel = entry

        # Cleanup CEL
        cel.cleanup()

        # Remove from registry
        del self.capsules[capsule_id]

        # Remove metadata
        meta_file = self.storage_dir / capsule_id / "metadata.json"
        if meta_file.exists():
            shutil.rmtree(self.storage_dir / capsule_id, ignore_errors=True)

        return True

    def execute(
        self,
        capsule_id: str,
        cmd: List[str],
        cwd: Optional[Path] = None,
        timeout_ms: int = 600000,
        stdin: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute command in capsule.

        Args:
            capsule_id: Capsule identifier
            cmd: Command and arguments
            cwd: Working directory
            timeout_ms: Timeout in milliseconds
            stdin: Standard input

        Returns:
            Execution result
        """
        entry = self.capsules.get(capsule_id)
        if not entry:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Capsule {capsule_id} not found",
                "usage": {},
                "touched": {"read": [], "written": []}
            }

        metadata, cel = entry

        # Prepare environment with whitelist and clock offset
        env = {}
        if metadata.env_whitelist:
            import os
            for var in metadata.env_whitelist:
                if var in os.environ:
                    env[var] = os.environ[var]

        # Add clock offset (simplified - application should check this)
        if metadata.clock_offset_sec != 0:
            env["CCW_CLOCK_OFFSET"] = str(metadata.clock_offset_sec)

        # Execute
        return cel.execute(
            cmd=cmd,
            cwd=cwd,
            env=env,
            timeout_ms=timeout_ms,
            stdin=stdin
        )

    def diff(self, capsule_id: str, format: str = "unified") -> Dict[str, Any]:
        """Generate diff for capsule changes.

        Args:
            capsule_id: Capsule identifier
            format: Diff format ("unified" or "json")

        Returns:
            Dict with summary and diff
        """
        entry = self.capsules.get(capsule_id)
        if not entry:
            return {
                "summary": {"added": 0, "deleted": 0, "modified": 0},
                "diff": ""
            }

        metadata, cel = entry
        changes = cel.get_changes()

        # Generate diffs
        all_diffs = []
        added = 0
        deleted = 0
        modified = 0

        for rel_path in changes:
            base_file = metadata.base_dir / rel_path if metadata.base_dir else None
            new_file = cel.mount() / rel_path

            # Check if new or modified
            if base_file is None or not base_file.exists():
                added += 1
            else:
                modified += 1

            # Generate diff
            if format == "unified":
                diff = generate_unified_diff(
                    base_file if base_file and base_file.exists() else Path("/dev/null"),
                    new_file
                )
                all_diffs.append(diff)

        combined_diff = "\n".join(all_diffs) if format == "unified" else {}

        # Count changes from diff
        if format == "unified" and combined_diff:
            counts = count_changes(combined_diff)
            added = counts.get("added", added)
            deleted = counts.get("deleted", deleted)

        return {
            "summary": {
                "added": added,
                "deleted": deleted,
                "modified": modified
            },
            "diff": combined_diff
        }

    def _save_metadata(self, capsule_id: str, metadata: CapsuleMetadata):
        """Save capsule metadata to disk.

        Args:
            capsule_id: Capsule identifier
            metadata: Metadata to save
        """
        capsule_dir = self.storage_dir / capsule_id
        capsule_dir.mkdir(parents=True, exist_ok=True)

        meta_file = capsule_dir / "metadata.json"

        # Convert to dict, handling Path objects
        meta_dict = asdict(metadata)
        for key, value in meta_dict.items():
            if isinstance(value, Path):
                meta_dict[key] = str(value)

        with open(meta_file, 'w') as f:
            json.dump(meta_dict, f, indent=2)
