"""First-run configuration and initialization.

This package owns the :func:`initialize_workspace` application service that
accepts an :class:`InitializeWorkspaceCommand`, creates the active
profile/bucket state, and returns an :class:`InitializeWorkspaceResult` behind
``aeat config profile create NAME``.
"""

from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult
from ._service import initialize_workspace

__all__ = [
    "InitializeWorkspaceCommand",
    "InitializeWorkspaceResult",
    "initialize_workspace",
]
