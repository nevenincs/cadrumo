"""Typed application errors for modelo actions."""

from __future__ import annotations

from ...core.errors import CoreNotFoundError
from ...domain.modelos._errors import ModeloError
from ..workflow import WorkflowAbortReason, WorkflowResult

WORKFLOW_GATE_LEGAL_REFS: tuple[str, ...] = (
    "ley-58-2003:art-119",
    "ley-58-2003:art-120",
    "ley-58-2003:art-122",
)
"""Legal anchors for the modelo workflow gate."""


class WorkUnitNotFoundError(ModeloError, KeyError):
    """Raised when a work-unit lookup or mutation targets a missing id."""


class WorkUnitAlreadyDiscardedError(ModeloError):
    """Raised when discard is invoked on a work unit already discarded."""


class WorkUnitMutationRefusedError(ModeloError):
    """Raised when a mutation targets a discarded work unit."""


class CalculationRevisionNotFoundError(ModeloError, CoreNotFoundError):
    """Raised when a calculation revision lookup fails."""


class CalculationRevisionStateError(ModeloError):
    """Raised when a state transition is requested from an incompatible source state."""


class ModeloRecordNotFoundError(ModeloError, KeyError):
    """Raised when a filing record lookup fails."""


class VerificationReportNotFoundError(ModeloError, KeyError):
    """Raised when a verification report lookup fails."""


class AmendmentEvidenceMissingError(ModeloError):
    """Raised when the modelo-amend path lacks imported official evidence."""


class AmendmentTargetStateError(ModeloError):
    """Raised when the modelo-amend path targets a non-current filing record."""


class StoredCalculationDriftError(ModeloError):
    """Raised when a persisted calculation revision has drifted from its content-addressed id."""


class ExternalModeloImportError(ModeloError):
    """Raised when the external-filing import path cannot persist an imported baseline."""


class ModeloCrossPeriodCleanStateError(ModeloError):
    """Raised when a filing-grade workflow lacks clean prior-filing proof."""


class ModeloWorkflowGateError(ModeloError):
    """Raised when the workflow gate refuses an internal file transition."""

    def __init__(self, result: WorkflowResult) -> None:
        self._result = result
        reason = result.aborted_reason.value if result.aborted_reason is not None else "unknown"
        summary = result.summary.strip() or "the workflow gate aborted this transition"
        suggestion: str | None = None
        if result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION:
            suggestion = "aeat app modelo export <work-unit-id> --output <path>"
        super().__init__(
            summary,
            context={
                "abort_code": reason,
                "stage": result.final_stage.value,
            },
            suggestion=suggestion,
        )

    @property
    def result(self) -> WorkflowResult:
        """Return the live :class:`WorkflowResult` that triggered the abort."""
        return self._result


class AmendmentOverrideCasillaError(ModeloError):
    """Raised when an amendment override targets an undeclared casilla id."""


class ModeloLocalObservationError(ModeloError):
    """Raised when an operator-supplied local observation cannot be persisted."""


class AmendmentVerificationRefusedError(ModeloError):
    """Raised when the corrected casilla map fails verification."""


class CalculationRegistryUnavailableError(ModeloError):
    """Raised when the registry snapshot for a work unit cannot be resolved."""


class ModeloAggregationBindingError(ModeloError):
    """Raised when bucket-derived aggregation bindings conflict with caller input."""


class ModeloRequiredBindingsMissingError(ModeloError):
    """Raised when Modelo 202 lifecycle work lacks required calculation bindings."""


class ModeloProfileReadinessError(ModeloError):
    """Raised when filing-grade modelo work starts with missing active-profile facts."""


class CasillaProvenanceMissingError(ModeloError):
    """Raised when an engine-result casilla has no registry definition."""


class ModeloApplicabilityFilterError(ModeloError):
    """Raised when an unknown applicability filter name is encountered."""


class ModeloRefundElectionNotEligibleError(ModeloError):
    """Raised when an operator elects a Modelo 303 refund for an ineligible period.

    A non-REDEME taxpayer may request a negative Modelo 303 result back as a refund
    (devolución, Tipo de declaración ``D``) only in the last filing period of the
    year (the annual liquidación, Ley 37/1992 art. 116). Electing ``devolver`` for
    any earlier period is refused rather than silently downgraded to compensación —
    a silent downgrade would hide that the operator's refund request was discarded,
    and a silent upgrade would file a refund the law does not permit for the period.
    The fix is operator-driven: carry the credit forward (``compensar``), or make
    the election in the year's last period.
    """


class ModeloRefundAccountMissingError(ModeloError):
    """Raised when a refund-disposition export has no refund account on file.

    When the determined disposition is a refund (devolución, ``D`` / ``V`` /
    ``X``) the fichero must carry the cuenta-devolución block AEAT pays into —
    the IBAN, or the SWIFT-BIC plus foreign-bank block for a non-SEPA account.
    If the operator's profile carries no refund account (no ``iban``), the
    export REFUSES rather than emitting an empty or partial DID block: an empty
    refund block produces a devolución fichero AEAT cannot pay — a silent,
    defective filing. The fix is operator-driven: configure a refund account on
    the profile, or carry the credit forward (``compensar``) instead of
    requesting a refund. This is the no-silent-under-declaration sibling of the
    election's eligibility refusal.
    """


class WorkUnitRevisionDivergenceError(ModeloError):
    """Raised when the registry's law-determined revision diverges from the work unit's pinned revision.

    This can only happen when the registry's law-mapping was corrected after the
    work unit was created (the creation gate now enforces resolver-equality), or
    for work units persisted before the strengthened creation gate landed.  The
    resolution is to re-create the work unit so its identity reflects the
    corrected law-determined revision.
    """


__all__ = [
    "WORKFLOW_GATE_LEGAL_REFS",
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "ModeloAggregationBindingError",
    "ModeloApplicabilityFilterError",
    "ModeloCrossPeriodCleanStateError",
    "ModeloLocalObservationError",
    "ModeloProfileReadinessError",
    "ModeloRecordNotFoundError",
    "ModeloRefundAccountMissingError",
    "ModeloRefundElectionNotEligibleError",
    "ModeloRequiredBindingsMissingError",
    "ModeloWorkflowGateError",
    "StoredCalculationDriftError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "WorkUnitRevisionDivergenceError",
]
