"""Detection and refusal for a Modelo 193 revision carrying a settled prior-accrual row.

Income exigible in one year and paid in a later one is a pending row of the
accrual year's Modelo 193 and a settled prior-accrual row of the payment
year's. The withholding on it was declared in the accrual year's Modelo 123,
and no official source settles what the payment-year record declares as base
and withholding. The calculation carries an advisory beside those amounts;
filing or exporting the revision would turn that advisory into a declaration.

One detection serves every stage. Local filing and export refuse the revision
with one typed reason and no command action, because recovering needs that
authority, which is the operator's decision rather than a step this
application can offer. Verification reports the same detection as a
non-blocking finding, so the operator learns of it before exporting or filing.

The withholding resolver records every materialised disclosure phase row as a
contributor node linked to its annual row, and nothing else it records is a
contributor. A node persisted with its accrual year is settled exactly when
that year is earlier than the revision's filing year. A node persisted before
the accrual year was kept has no phase, so the filing year decides it through
the phase materialisation's own accrual-year bound, which over-refuses rather
than lets a settled row through.
"""

from __future__ import annotations

from enum import StrEnum

from ...core.aggregation import CalculationSourceLineageRole
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationSourceRef
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ..aggregation.m193_phase_materialization import modelo_193_phase_rows_may_settle_prior_accruals
from ..aggregation.withholding_source import WithholdingSourceResolver
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

_MODELO_193 = Modelo("193")

#: The capital withholding declared in the accrual period's Modelo 123 (RIRPF
#: art. 108) and the order approving Modelo 193 whose record design leaves the
#: payment-year amounts unstated.
_SETTLED_ROW_LEGAL_REFS: tuple[str, ...] = (
    "rd-439-2007:art-108",
    "orden-eha-3377-2011:art-1",
)
_SETTLED_ROW_SOURCE_REFS: tuple[str, ...] = ("aeat-dr-193-2025",)


class Modelo193SettledRowStage(StrEnum):
    """Operator leaf whose action a settled prior-accrual row refuses."""

    FILE = "modelo.work.file"
    EXPORT = "modelo.export"


class Modelo193SettledRowAmountAuthorityUnresolvedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a Modelo 193 revision carries a settled prior-accrual row whose amounts no source settles."""


def _phase_row_is_settled_prior_accrual(ref: CalculationSourceRef, *, filing_year: int) -> bool:
    if ref.source_filing_year is not None:
        return ref.source_filing_year < filing_year
    return modelo_193_phase_rows_may_settle_prior_accruals(filing_year)


def modelo_193_settled_prior_accrual_contributors(
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> tuple[CalculationSourceRef, ...]:
    """Return the persisted Modelo 193 phase contributors that are settled prior-accrual rows.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    if work_unit.modelo != _MODELO_193:
        return ()
    return tuple(
        ref
        for ref in revision.source_provenance
        if ref.resolver_id == WithholdingSourceResolver.resolver_id
        and ref.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
        and _phase_row_is_settled_prior_accrual(ref, filing_year=work_unit.filing_year)
    )


def require_modelo_193_settled_row_amount_authority(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    stage: Modelo193SettledRowStage,
) -> None:
    """Refuse to file or export a Modelo 193 revision that carries a settled prior-accrual row.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    settled = modelo_193_settled_prior_accrual_contributors(work_unit, revision)
    if not settled:
        return
    raise Modelo193SettledRowAmountAuthorityUnresolvedError(
        translated_message="errors.refused.canonical_modelo_193_settled_row_amount_authority_unresolved",
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "settled_prior_accrual_rows": str(len(settled)),
            "stage": stage.value,
        },
        precondition_failure=modelo_193_settled_row_amount_authority_unresolved_failure(
            work_unit,
            revision,
            settled_row_count=len(settled),
            stage=stage,
        ),
    )


def modelo_193_settled_row_amount_authority_unresolved_failure(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    settled_row_count: int,
    stage: Modelo193SettledRowStage,
) -> ModeloPreconditionFailure:
    """Build the declared no-action verdict for an unresolved settled-row amount at ``stage``.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    leaf = stage.value
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.m193_settled_row_amount_authority.unresolved",
        evidence_id=f"{leaf}.m193_settled_row_amount_authority",
        evidence_values={
            "calculation_revision_id": revision.calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "year": work_unit.filing_year,
            "settled_prior_accrual_rows": settled_row_count,
            "amount_authority_resolved": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def modelo_193_settled_row_verification_finding(
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> ModeloVerificationFinding | None:
    """Return the non-blocking verification finding for a revision that filing and export will refuse.

    Advisory rather than blocking: no recalculation or operator input clears
    the condition, since what the revision lacks is an official authority for
    the payment-year amounts. A blocking finding would leave the draft
    unverifiable for a reason verification cannot resolve, while filing and
    export already refuse the revision themselves; this finding tells the
    operator before they try.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    settled = modelo_193_settled_prior_accrual_contributors(work_unit, revision)
    if not settled:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.m193_settled_row_amount_authority_unresolved",
        message_facts={
            "filing_year": work_unit.filing_year,
            "settled_prior_accrual_rows": len(settled),
        },
        legal_refs=_SETTLED_ROW_LEGAL_REFS,
        source_refs=_SETTLED_ROW_SOURCE_REFS,
    )


__all__ = [
    "Modelo193SettledRowAmountAuthorityUnresolvedError",
    "Modelo193SettledRowStage",
    "modelo_193_settled_prior_accrual_contributors",
    "modelo_193_settled_row_amount_authority_unresolved_failure",
    "modelo_193_settled_row_verification_finding",
    "require_modelo_193_settled_row_amount_authority",
]
