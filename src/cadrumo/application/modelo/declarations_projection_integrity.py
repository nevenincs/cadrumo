"""Terminal integrity transport shared by the Declarations projection refusals.

The Declarations calendar and workspace join stored authorities (schedule,
local filing records, AEAT evidence, revisions, work catalogue). When those do
not form one coherent view, no operator input at the refusal site corrects
them, so the refusal states the integrity fault as a terminal outcome and
names no command.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from ...core.errors.hierarchy import TerminalPreconditionErrorMixin
from ...core.operator_action_enums import NoRecoveryOutcome
from ..cli_exception_preconditions import CliExceptionPrecondition, cli_exception_no_recovery_verdict
from ..operator_actions.models import PreconditionVerdict


class DeclarationsProjectionIntegrityMixin(TerminalPreconditionErrorMixin[PreconditionVerdict]):
    """Attach the terminal stored-data integrity verdict to a projection refusal class."""

    integrity_record: ClassVar[str]

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Initialize the error with the caller's verdict or the terminal integrity default."""
        verdict = precondition_verdict or cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.STORED_DATA_VALID,
            facts={"record": self.integrity_record, "valid": False},
            outcome=NoRecoveryOutcome.TERMINAL,
        )
        super().__init__(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=verdict,
        )
