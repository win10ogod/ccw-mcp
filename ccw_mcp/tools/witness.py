"""Witness package generation and replay"""

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from ..util import hash_file, hash_bytes


@dataclass
class WitnessMetadata:
    """Metadata for a witness package"""
    witness_id: str
    capsule_id: str
    created_at: str
    root_hash: str
    compressed: bool
    size_bytes: int


class WitnessEngine:
    """Engine for creating and replaying witness packages"""

    def __init__(self, storage_dir: Path):
        """Initialize witness engine.

        Args:
            storage_dir: Directory for storing witnesses
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.witnesses: Dict[str, WitnessMetadata] = {}

    def create(
        self,
        capsule_id: str,
        capsule_mount: Path,
        changes: list,
        compress: str = "zstd",
        include_blobs: bool = True
    ) -> Dict[str, Any]:
        """Create witness package from capsule.

        Args:
            capsule_id: Source capsule ID
            capsule_mount: Mount point of capsule
            changes: List of changed files
            compress: Compression method ("zstd" or "none")
            include_blobs: Include file blobs

        Returns:
            Dict with witness_id, path, root_hash, size_bytes
        """
        # Generate witness ID
        timestamp = int(time.time() * 1000)
        witness_id = f"wit_{timestamp}"

        # Create witness directory
        witness_dir = self.storage_dir / witness_id
        witness_dir.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest = {
            "witness_id": witness_id,
            "capsule_id": capsule_id,
            "created_at": time.time(),
            "changes": [str(p) for p in changes],
            "compress": compress,
            "include_blobs": include_blobs
        }

        # Create hashes and blobs
        hashes = {}
        blobs_dir = witness_dir / "blobs"
        if include_blobs:
            blobs_dir.mkdir(exist_ok=True)

        for change in changes:
            file_path = capsule_mount / change
            if file_path.exists() and file_path.is_file():
                # Hash file
                file_hash = hash_file(file_path)
                hashes[str(change)] = file_hash

                # Copy blob (content-addressed)
                if include_blobs:
                    blob_name = file_hash.replace("blake3:", "")
                    blob_path = blobs_dir / blob_name
                    if not blob_path.exists():
                        shutil.copy2(file_path, blob_path)

        # Save hashes
        with open(witness_dir / "hashes.json", 'w') as f:
            json.dump(hashes, f, indent=2)

        # Save manifest
        with open(witness_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)

        # Calculate root hash
        root_hash = self._calculate_root_hash(witness_dir)

        # Compress if requested
        archive_path = witness_dir
        compressed = False
        if compress == "zstd":
            compressed = self._compress_witness(witness_dir)

        # Calculate size
        size_bytes = self._calculate_size(witness_dir)

        # Create metadata
        metadata = WitnessMetadata(
            witness_id=witness_id,
            capsule_id=capsule_id,
            created_at=manifest["created_at"],
            root_hash=root_hash,
            compressed=compressed,
            size_bytes=size_bytes
        )

        self.witnesses[witness_id] = metadata

        return {
            "witness_id": witness_id,
            "path": str(witness_dir),
            "root_hash": root_hash,
            "size_bytes": size_bytes
        }

    def replay(self, witness_id: str) -> Dict[str, Any]:
        """Replay witness package.

        Args:
            witness_id: Witness identifier

        Returns:
            Dict with replay_ok, root_hash, metrics
        """
        witness_dir = self.storage_dir / witness_id

        if not witness_dir.exists():
            return {
                "replay_ok": False,
                "root_hash": "",
                "metrics": {}
            }

        # Decompress if needed
        if (witness_dir / f"{witness_id}.tar.zst").exists():
            self._decompress_witness(witness_dir)

        # Load manifest
        with open(witness_dir / "manifest.json", 'r') as f:
            manifest = json.load(f)

        # Verify root hash
        root_hash = self._calculate_root_hash(witness_dir)
        metadata = self.witnesses.get(witness_id)
        expected_hash = metadata.root_hash if metadata else None

        replay_ok = (root_hash == expected_hash) if expected_hash else True

        return {
            "replay_ok": replay_ok,
            "root_hash": root_hash,
            "metrics": {
                "cpu_ms": 0,  # Simplified
                "rss_max_kb": 0
            }
        }

    def _calculate_root_hash(self, witness_dir: Path) -> str:
        """Calculate root hash of witness package.

        Args:
            witness_dir: Witness directory

        Returns:
            Root hash string
        """
        # Simple approach: hash the manifest + hashes
        components = []

        manifest_file = witness_dir / "manifest.json"
        if manifest_file.exists():
            with open(manifest_file, 'rb') as f:
                components.append(f.read())

        hashes_file = witness_dir / "hashes.json"
        if hashes_file.exists():
            with open(hashes_file, 'rb') as f:
                components.append(f.read())

        combined = b"".join(components)
        return hash_bytes(combined)

    def _compress_witness(self, witness_dir: Path) -> bool:
        """Compress witness directory using zstd.

        Args:
            witness_dir: Witness directory

        Returns:
            True if successful
        """
        archive_name = witness_dir / f"{witness_dir.name}.tar.zst"

        try:
            # Create tar archive
            subprocess.run(
                ["tar", "-cf", "-", "-C", str(witness_dir), "."],
                stdout=subprocess.PIPE,
                check=True
            )

            # Note: zstd compression would require zstd binary
            # For simplicity, we skip actual compression here
            return False

        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _decompress_witness(self, witness_dir: Path) -> bool:
        """Decompress witness archive.

        Args:
            witness_dir: Witness directory

        Returns:
            True if successful
        """
        # Simplified - would decompress .tar.zst
        return False

    def _calculate_size(self, witness_dir: Path) -> int:
        """Calculate total size of witness.

        Args:
            witness_dir: Witness directory

        Returns:
            Size in bytes
        """
        total = 0
        for item in witness_dir.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
        return total
