"""Version and project information utilities."""

from __future__ import annotations

import sys
from typing import Any


def get_project_info(project_name: str) -> dict[str, Any]:
    """Get project information.
    
    Args:
        project_name: Name of the project/package
        
    Returns:
        Dictionary with project metadata
    """
    return {
        "project": project_name,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def get_runtime_info() -> dict[str, Any]:
    """Get runtime information.
    
    Returns:
        Dictionary with runtime metadata
    """
    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
    }
