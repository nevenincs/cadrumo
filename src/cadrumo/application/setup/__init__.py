"""Reusable first-run profile and bucket initialization.

This legacy passwordless provisioner is intentionally fail-closed. Credential
registration is the only profile creation door.
"""

from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult
from ._service import initialize_workspace

__all__ = [
    "InitializeWorkspaceCommand",
    "InitializeWorkspaceResult",
    "initialize_workspace",
]
