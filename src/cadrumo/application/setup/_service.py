"""Retired passwordless workspace provisioning surface.

Current capsules may only be created by credential registration, which binds
the new envelope and record session before staging revision one.  This older
command carries no passphrase and is therefore deliberately unavailable.
"""

from __future__ import annotations

from ..user_profile import ProfileRegistrationError
from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult


def initialize_workspace(command: InitializeWorkspaceCommand) -> InitializeWorkspaceResult:
    """Refuse passwordless workspace creation."""
    del command
    raise ProfileRegistrationError(
        "workspace initialization requires credential registration before profile setup",
    )


__all__ = ["initialize_workspace"]
