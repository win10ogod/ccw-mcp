"""Hashing utilities using BLAKE3"""

import blake3
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024  # 1 MiB


def hash_file(path: Path) -> str:
    """Calculate BLAKE3 hash of a file.

    Args:
        path: Path to the file

    Returns:
        Hex-encoded BLAKE3 hash with 'blake3:' prefix
    """
    hasher = blake3.blake3()
    with open(path, 'rb') as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return f"blake3:{hasher.hexdigest()}"


def hash_bytes(data: bytes) -> str:
    """Calculate BLAKE3 hash of bytes.

    Args:
        data: Bytes to hash

    Returns:
        Hex-encoded BLAKE3 hash with 'blake3:' prefix
    """
    hasher = blake3.blake3(data)
    return f"blake3:{hasher.hexdigest()}"


def hash_stream(stream: BinaryIO) -> str:
    """Calculate BLAKE3 hash of a stream.

    Args:
        stream: Binary stream to hash

    Returns:
        Hex-encoded BLAKE3 hash with 'blake3:' prefix
    """
    hasher = blake3.blake3()
    while chunk := stream.read(CHUNK_SIZE):
        hasher.update(chunk)
    return f"blake3:{hasher.hexdigest()}"


def verify_hash(path: Path, expected_hash: str) -> bool:
    """Verify file hash matches expected value.

    Args:
        path: Path to the file
        expected_hash: Expected hash (with 'blake3:' prefix)

    Returns:
        True if hash matches, False otherwise
    """
    actual = hash_file(path)
    return actual == expected_hash
