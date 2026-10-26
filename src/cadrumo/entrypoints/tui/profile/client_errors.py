"""Settled profile mutations that need truthful UI wording."""

from __future__ import annotations

from cadrumo_client.transport.profile_mutations import ProfileMutationCompletion, ProfileMutationRunError

from ....application.user_profile.capsule_record import ProfileRecordConflictError
from ....core.errors.error_codes import get_registered_error_code
from ....core.errors.hierarchy import CadrumoError
from ....core.operations import OperationEffect, OperationTerminalCondition


def is_profile_edit_conflict(error: BaseException | None) -> bool:
    """Recognize a local or settled remote refusal before any profile write."""
    return isinstance(error, ProfileRecordConflictError) or (
        isinstance(error, ProfileMutationRunError)
        and error.reason == get_registered_error_code(ProfileRecordConflictError).code
        and error.terminal_condition is OperationTerminalCondition.FAILED
        and error.effect is OperationEffect.NONE
    )


class ProfileManagerCompletedViewUnavailableError(CadrumoError):
    """The operation settled successfully, but its current view could not be verified."""

    def __init__(self, completion: ProfileMutationCompletion) -> None:
        """Retain the settled operation identity and observed effect."""
        self.operation_id = completion.operation_id
        self.record_revision = completion.projection.record_revision
        self.effect = completion.effect
        super().__init__("completed_profile_view_unavailable")


__all__ = ["ProfileManagerCompletedViewUnavailableError"]
