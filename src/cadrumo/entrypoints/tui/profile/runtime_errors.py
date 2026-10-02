"""Settled runtime-manager outcomes that need truthful UI wording."""

from __future__ import annotations

from ....adapters.local_runtime.profile_mutations import ProfileMutationCompletion
from ....core.errors.hierarchy import CadrumoError


class ProfileManagerCompletedViewUnavailableError(CadrumoError):
    """The operation settled successfully, but its current view could not be verified."""

    def __init__(self, completion: ProfileMutationCompletion) -> None:
        """Retain the settled operation identity and observed effect."""
        self.operation_id = completion.operation_id
        self.record_revision = completion.projection.record_revision
        self.effect = completion.effect
        super().__init__("completed_profile_view_unavailable")


__all__ = ["ProfileManagerCompletedViewUnavailableError"]
