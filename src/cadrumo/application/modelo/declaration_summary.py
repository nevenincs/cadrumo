"""Lightweight declaration state from current revisions and verification facts.

The portfolio reads preloaded catalogues and the pinned registry. It never
builds a form, reruns a calculation, or invents a result for an unreadable row.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.verification_report import ModeloVerificationFindingSeverity, VerificationReportCatalogue
from ...domain.modelos.work_unit import WorkUnitState
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .work_form_models import ModeloFormResult
from .work_form_result import settlement_result_values

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from .declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1


class DeclarationSummaryState(StrEnum):
    """The persisted work and verification state of a declaration."""

    DRAFT = "draft"
    CALCULATED = "calculated"
    BLOCKED = "blocked"
    CHECKED = "checked"
    RECORDED = "recorded"
    SUPERSEDED = "superseded"
    DISCARDED = "discarded"
    UNREADABLE = "unreadable"


class DeclarationSummary(BaseModel):
    """A row's current result and checking state, without constructing its form."""

    model_config = STRICT_FROZEN_CONFIG

    state: DeclarationSummaryState
    blocking_count: int | None = None
    checked: bool = False
    result: ModeloFormResult | None = None
    is_correction: bool = False
    technical_reason: str | None = Field(default=None, exclude=True, repr=False)


def declaration_summary(
    declaration: DeclarationsWorkspaceDeclarationRefV1,
    *,
    revisions: Mapping[str, CalculationRevision],
    verification: VerificationReportCatalogue | None,
    operation: PinnedAuthorityOperation,
) -> DeclarationSummary:
    """Project one row; a registry refusal cannot erase its neighbours.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    heads = [item for item in revisions.values() if item.work_unit_id == declaration.work_unit_id]
    # The caller passes only current revisions, selected by work-unit pointers.
    if len(heads) > 1:
        return DeclarationSummary(
            state=DeclarationSummaryState.UNREADABLE,
            technical_reason="declaration summary requires one current revision",
        )
    head = heads[0] if heads else None
    try:
        snapshot = operation.snapshot(
            str(declaration.modelo), filing_year=declaration.filing_year, period=declaration.period.registry_token
        )
        if head is not None:
            _require_selected_calculation_coordinate(head, declaration, snapshot, operation)
    except (CadrumoError, ValueError, LookupError) as exc:
        return DeclarationSummary(state=DeclarationSummaryState.UNREADABLE, technical_reason=str(exc))
    if declaration.state is WorkUnitState.DESCARTADO:
        return DeclarationSummary(state=DeclarationSummaryState.DISCARDED)
    if head is None:
        return DeclarationSummary(state=DeclarationSummaryState.DRAFT)
    blockers, checked = _verification_summary(head, verification)
    state = _summary_state(declaration, head, blockers, checked)
    try:
        result = settlement_result_values(
            str(declaration.modelo), snapshot.revision, head.casilla_values, declaration.period
        )
    except (CadrumoError, ValueError, LookupError) as exc:
        return DeclarationSummary(state=DeclarationSummaryState.UNREADABLE, technical_reason=str(exc))
    return DeclarationSummary(
        state=state,
        blocking_count=blockers,
        checked=checked,
        result=result,
        is_correction=head.amendment_identity is not None,
    )


def _verification_summary(
    head: CalculationRevision, verification: VerificationReportCatalogue | None
) -> tuple[int | None, bool]:
    """Read the latest verification for this exact calculation revision."""
    reports = (
        []
        if verification is None
        else [
            report
            for report in verification.reports.values()
            if report.calculation_revision_id == head.calculation_revision_id
        ]
    )
    report = max(reports, key=lambda item: (item.run_at, item.verification_report_id), default=None)
    blockers = (
        None
        if report is None
        else sum(finding.severity is ModeloVerificationFindingSeverity.BLOCKING for finding in report.findings)
    )
    checked = head.state in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}
    return blockers, checked


def _summary_state(
    declaration: DeclarationsWorkspaceDeclarationRefV1, head: CalculationRevision, blockers: int | None, checked: bool
) -> DeclarationSummaryState:
    """Preserve filing, supersession, blockers and checked-state precedence."""
    if declaration.has_current_filing:
        state = DeclarationSummaryState.RECORDED
    elif head.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO:
        state = DeclarationSummaryState.SUPERSEDED
    elif blockers:
        state = DeclarationSummaryState.BLOCKED
    elif checked:
        state = DeclarationSummaryState.CHECKED
    else:
        state = DeclarationSummaryState.CALCULATED
    return state


def _require_selected_calculation_coordinate(
    head: CalculationRevision,
    declaration: DeclarationsWorkspaceDeclarationRefV1,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
) -> None:
    """Validate current authority before comparing the exact declaration coordinate."""
    require_calculation_revision_coordinates_current(head, operation=operation)
    coordinate = head.registry_snapshot_ref
    if (str(coordinate.modelo), coordinate.modelo_year, str(coordinate.period), coordinate.revision_id) != (
        str(declaration.modelo),
        declaration.filing_year,
        declaration.period.registry_token,
        snapshot.revision.id,
    ):
        raise ValueError("current calculation and selected declaration coordinates disagree")
