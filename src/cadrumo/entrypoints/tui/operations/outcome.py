"""A submitted operation whose outcome the frontend could not establish."""

from __future__ import annotations

from ....core.errors.hierarchy import CadrumoError
from ....core.operations import OperationEffect


class OperationOutcomeUnknownError(CadrumoError):
    """A submitted operation may have changed records although no success was observed.

    Raised once an operation has been submitted and either its settlement was
    not observed in time, or its terminal receipt did not succeed yet reports
    an effect other than none. Neither is a refusal: the change may be saved,
    partly saved or still settling, so repeating it before reading the records
    again could apply it twice.

    ``effect`` is the terminal receipt's effect, or ``None`` when no terminal
    receipt was observed. ``reason`` is the registered error the operation
    recorded, when it recorded one.
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


__all__ = ["OperationOutcomeUnknownError"]
