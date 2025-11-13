"""Capsule management - core abstraction for counterfactual environments"""

import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from ..cel import create_cel, rehydrate_cel, CEL
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
        self._load_existing_capsules()

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

    def _load_existing_capsules(self):
        """Load capsules from persisted metadata."""

        if not self.storage_dir.exists():
            return

        for capsule_dir in self.storage_dir.iterdir():
            if not capsule_dir.is_dir():
                continue

            meta_file = capsule_dir / "metadata.json"
            metadata = self._read_metadata(meta_file)
            if metadata is None:
                continue

            entry = self._initialize_capsule_from_metadata(metadata)
            if entry is None:
                continue

            self.capsules[metadata.capsule_id] = entry

    def get(self, capsule_id: str) -> Optional[tuple[CapsuleMetadata, CEL]]:
        """Get capsule by ID.

        Args:
            capsule_id: Capsule identifier

        Returns:
            Tuple of (metadata, cel) or None
        """
        entry = self.capsules.get(capsule_id)
        if entry:
            return entry

        return self._load_capsule(capsule_id)

    def _load_capsule(self, capsule_id: str) -> Optional[tuple[CapsuleMetadata, CEL]]:
        """Load capsule on demand from disk."""

        meta_file = self.storage_dir / capsule_id / "metadata.json"
        metadata = self._read_metadata(meta_file)
        if metadata is None:
            return None

        entry = self._initialize_capsule_from_metadata(metadata)
        if entry is None:
            return None

        self.capsules[capsule_id] = entry
        return entry

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
        entry = self.get(capsule_id)
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
        entry = self.get(capsule_id)
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
        entry = self.get(capsule_id)
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

    def _read_metadata(self, meta_file: Path) -> Optional[CapsuleMetadata]:
        """Read capsule metadata from disk."""

        if not meta_file.exists():
            return None

        try:
            with open(meta_file, 'r') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        capsule_id = data.get("capsule_id")
        workspace = data.get("workspace")
        if not capsule_id or not workspace:
            return None

        base_dir = data.get("base_dir")
        mount_point = data.get("mount_point")

        metadata = CapsuleMetadata(
            capsule_id=capsule_id,
            workspace=Path(workspace),
            base_dir=Path(base_dir) if base_dir else None,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            clock_offset_sec=int(data.get("clock_offset_sec", 0)),
            env_whitelist=data.get("env_whitelist", []),
            mount_point=Path(mount_point) if mount_point else None,
        )

        return metadata

    def _initialize_capsule_from_metadata(
        self,
        metadata: CapsuleMetadata,
    ) -> Optional[tuple[CapsuleMetadata, CEL]]:
        """Initialize CEL from metadata, restoring sandbox if possible."""

        try:
            if metadata.mount_point and metadata.mount_point.exists():
                cel = rehydrate_cel(
                    workspace=metadata.workspace,
                    base_dir=metadata.base_dir,
                    mount_point=metadata.mount_point,
                )
            else:
                cel = create_cel(
                    workspace=metadata.workspace,
                    base_dir=metadata.base_dir,
                )
                metadata.mount_point = cel.mount()
                self._save_metadata(metadata.capsule_id, metadata)
        except Exception:
            return None

        return metadata, cel
