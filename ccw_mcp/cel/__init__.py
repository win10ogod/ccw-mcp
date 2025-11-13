"""Counterfactual Execution Layer - Platform abstraction"""

import platform
from pathlib import Path
from typing import Union, Optional

from .linux import LinuxCEL
from .windows import WindowsCEL
from .portable import PortableCEL

# Type alias for CEL implementations
CEL = Union[LinuxCEL, WindowsCEL, PortableCEL]


def create_cel(workspace: Path, base_dir: Path = None) -> CEL:
    """Create appropriate CEL for current platform.

    Args:
        workspace: Workspace directory
        base_dir: Base directory (defaults to workspace)

    Returns:
        CEL instance (LinuxCEL, WindowsCEL, or PortableCEL)
    """
    system = platform.system()

    if system == "Linux":
        return LinuxCEL(workspace=workspace, base_dir=base_dir)
    elif system == "Windows":
        return WindowsCEL(workspace=workspace, base_dir=base_dir)
    else:
        # macOS or other - use portable
        return PortableCEL(workspace=workspace, base_dir=base_dir)


def rehydrate_cel(workspace: Path, base_dir: Optional[Path], mount_point: Path) -> CEL:
    """Rehydrate a CEL instance from existing sandbox state."""

    system = platform.system()

    if system == "Linux":
        return LinuxCEL.rehydrate(workspace=workspace, base_dir=base_dir, mount_point=mount_point)
    elif system == "Windows":
        return WindowsCEL.rehydrate(workspace=workspace, base_dir=base_dir, mount_point=mount_point)
    else:
        return PortableCEL.rehydrate(workspace=workspace, base_dir=base_dir, mount_point=mount_point)


__all__ = [
    'CEL',
    'LinuxCEL',
    'WindowsCEL',
    'PortableCEL',
    'create_cel',
    'rehydrate_cel',
]
