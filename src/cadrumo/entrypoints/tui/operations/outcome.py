"""A submitted operation whose outcome the frontend could not establish."""

from __future__ import annotations

from ....core.errors.hierarchy import CadrumoError
from ....core.operations import OperationEffect
from ..account import AccountSessionExpiredError, AccountSessionUnavailableError


class OperationOutcomeUnknownError(CadrumoError):
    """A submitted operation may have changed records although no success was observed.

    Raised once an operation that may change records has been submitted and
    any later step failed without a terminal receipt that committed nothing:
    the settlement was not observed, the receipt did not succeed yet reports
    an effect, or the result could not be read or did not agree with the
    receipt. None of these is a refusal: the change may be saved, partly saved
    or still settling, so repeating it before reading the records again could
    apply it twice.

    ``effect`` is the terminal receipt's effect, or ``None`` when no terminal
    receipt was observed. ``reason`` is the error that ended the wait or the
    read, or the registered error the operation recorded, when there is one.
    """

    def __init__(
        self,
        *,
        operation_id: str,
        effect: OperationEffect | None,
        reason: CadrumoError | None = None,
    ) -> None:
        """Keep the operation's identity and whatever its receipt said about its effect."""
        super().__init__(
            translated_message="errors.error.canonical_tui_operation_outcome_unknown",
            context={
                "operation_id": operation_id,
                "effect": "unobserved" if effect is None else effect.value,
            },
        )
        self.operation_id = operation_id
        self.effect = effect
        self.reason = reason


class SessionExpiredOutcomeUnknownError(AccountSessionExpiredError):
    """The session expired while a submitted operation's outcome was still unknown.

    It stays a session error, so every screen drops what it retained for the
    session and the operator is sent to sign in again. Its message also names
    the operation and says its change may have been saved, so the unknown
    outcome is not hidden behind the sign-in. Signing in composes every screen
    again from the current records, which is the re-read an unknown outcome
    needs before the change is offered again.
    """

    def __init__(self, outcome: OperationOutcomeUnknownError) -> None:
        """Carry the unknown outcome the expiry interrupted."""
        super().__init__(
            translated_message="errors.fail.canonical_tui_session_expired_outcome_unknown",
            context=dict(outcome.context or {}),
        )
        self.outcome = outcome


class SessionUnavailableOutcomeUnknownError(AccountSessionUnavailableError):
    """The runtime stopped answering while a submitted operation's outcome was still unknown.

    Like :class:`SessionExpiredOutcomeUnknownError`, but the session's state
    could not be observed at all, so nothing says it expired: the operator is
    told the runtime is unavailable and that the named operation's change may
    have been saved.
    """

    def __init__(self, outcome: OperationOutcomeUnknownError) -> None:
        """Carry the unknown outcome the lost connection interrupted."""
        super().__init__(
            translated_message="errors.fail.canonical_tui_session_unavailable_outcome_unknown",
            context=dict(outcome.context or {}),
        )
        self.outcome = outcome


__all__ = [
    "OperationOutcomeUnknownError",
    "SessionExpiredOutcomeUnknownError",
    "SessionUnavailableOutcomeUnknownError",
]
