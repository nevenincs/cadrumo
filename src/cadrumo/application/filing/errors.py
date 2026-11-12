"""Typed terminal-refusal transport for :mod:`application.filing`.

The domain filing package owns record, import, export, amendment, and builder
error taxonomy.  This application boundary owns the operator-facing outcome of
its own refusals: every reachable application refusal carries the shared typed
precondition record and a fact-only, explicitly non-actionable disposition.
The classes below still inherit their corresponding domain error, preserving
the established catch boundary without making the domain import application or
CLI authority.

See Also:
    :mod:`domain.filing.errors`
        Domain filing error hierarchy raised by draft, import, and export
        records.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar

from ...core.errors.hierarchy import TerminalPreconditionErrorMixin
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...domain.filing.errors import (
    FilingExportCasillaValueRefusedError,
    FilingExportError,
    ModeloBuilderError,
    ModeloImportError,
)
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict


class FilingPreconditionCondition(StrEnum):
    """Application-owned failed conditions for filing-boundary refusals."""

    OPERATION_ADMISSIBLE = "filing.application.operation.admissible"


def filing_no_recovery_verdict(
    condition: FilingPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> PreconditionVerdict:
    """Return the terminal, fact-only outcome for one filing refusal.

    Filing can identify the rejected record, receipt, or configuration fact,
    but none of these direct application services owns a safely executable
    recovery command.  The operator-surface resolver therefore receives an
    explicit no-recovery outcome instead of an application-authored command.
    """
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=outcome,
    )


def casilla_value_refusal(
    casilla_id: str, *, translated_message: str, context: Mapping[str, object]
) -> FilingExportCasillaValueRefusedError:
    """Refuse an export because the box ``casilla_id`` the filer states holds a value it cannot write.

    Filing owns no recovery command, so the verdict states the facts only; the
    Modelo export boundary, which knows the declaration, names the action that
    states that box again.
    """
    return FilingExportCasillaValueRefusedError(
        casilla_id=casilla_id,
        translated_message=translated_message,
        context=dict(context),
        precondition_verdict=filing_no_recovery_verdict(
            FilingPreconditionCondition.OPERATION_ADMISSIBLE,
            facts={"error_type": "FilingExportCasillaValueRefusedError", "casilla_id": casilla_id},
        ),
    )


class _FilingTerminalErrorMixin(TerminalPreconditionErrorMixin[PreconditionVerdict]):
    """Attach one declared filing outcome while retaining a domain error type."""

    precondition_condition: ClassVar[FilingPreconditionCondition]

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        verdict = precondition_verdict or filing_no_recovery_verdict(
            self.precondition_condition,
            facts={
                "error_type": type(self).__name__,
            },
        )
        super().__init__(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=verdict,
        )


class ModeloApplicationError(
    _FilingTerminalErrorMixin,
    ModeloBuilderError,
    ModeloImportError,
    FilingExportError,
):
    """Base class for errors raised by the filing application layer.

    The class remains an instance of the domain builder, import, and export
    catch families.  Those direct application boundaries share one registered
    error envelope, and changing their concrete type must not discard a
    caller's established domain catch while adding terminal transport.
    """

    precondition_condition = FilingPreconditionCondition.OPERATION_ADMISSIBLE


__all__ = [
    "FilingPreconditionCondition",
    "ModeloApplicationError",
    "casilla_value_refusal",
    "filing_no_recovery_verdict",
]
