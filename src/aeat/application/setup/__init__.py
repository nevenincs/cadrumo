"""First-run configuration and initialization.

This package owns the ``initialize_workspace`` application service
that orchestrates atomic bucket/profile creation, authentication setup,
and legacy state migration behind ``aeat config profile create NAME``.
"""

from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult
from ._service import initialize_workspace

__all__ = [
    "InitializeWorkspaceCommand",
    "InitializeWorkspaceResult",
    "initialize_workspace",
]
