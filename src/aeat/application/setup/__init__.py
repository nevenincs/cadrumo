"""Reusable first-run profile and bucket initialization.

This package exposes :func:`initialize_workspace`, a provisioner that accepts an
:class:`InitializeWorkspaceCommand`, mints the active
:class:`~aeat.core.identity.ProfileId`, provisions the matching storage
:class:`~aeat.core.identity.BucketId`, and returns an
:class:`InitializeWorkspaceResult`. The operator-supplied profile name remains
the display label; it is not used as the storage identity.

The live config CLI currently owns its command registration and shares the same
profile-create primitives rather than importing this facade directly. Keep this
module as the small application service boundary for callers that need atomic
workspace creation without rebuilding user-profile orchestration.

See Also:
    :func:`initialize_workspace`
        Service that writes profile facts, creates the active bucket, and
        reports whether the requested auth provider was configured.
    :class:`InitializeWorkspaceCommand`
        Typed first-run facts passed into the setup service.
    :class:`InitializeWorkspaceResult`
        UUID profile/bucket identity returned by successful setup.
    :func:`aeat.application.user_profile.profile_create_storage_span`
        Storage span that provisions the profile bucket before profile facts
        are committed.
    :func:`aeat.application.user_profile.register_active_profile`
        Workflow-state mutation used by both setup and config-profile create
        paths.
    :func:`aeat.application.auth.configure_operator_auth`
        Optional auth-provider configuration step invoked after bucket
        creation.
"""

from ._contracts import InitializeWorkspaceCommand, InitializeWorkspaceResult
from ._service import initialize_workspace

__all__ = [
    "InitializeWorkspaceCommand",
    "InitializeWorkspaceResult",
    "initialize_workspace",
]
