"""Durable revision issues projected from the source diagnostics a bucket aggregation leaves unrouted."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from ...domain.modelos.calculation_revision_sources import (
    CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT,
    CalculationSourceIssue,
)
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .calculation_notes import (
    PRINTED_BOX_REASONS,
    durable_binding_source,
)
from .printed_boxes import PrintedBoxes

if TYPE_CHECKING:
    pass
from .calculation_resolution import (
    precedence_tier_issue,
)


def _durable_invoice_source_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Keep explicit literal narrowing for absent invoice-source facts."""
    if diagnostic.reason == "source_domain_not_ready":
        return "source_domain_not_ready"
    if diagnostic.reason == "invoice_reverse_charge_cuota_not_derivable":
        return "invoice_reverse_charge_cuota_not_derivable"
    if diagnostic.reason == "m349_operation_unclassified":
        return "m349_operation_unclassified"
    if diagnostic.reason == "ledger_amortization_row_unregistered":
        return "ledger_amortization_row_unregistered"
    if diagnostic.reason == "activity_asset_foral_territory":
        return "activity_asset_foral_territory"
    if diagnostic.reason == "activity_asset_residence_unresolved":
        return "activity_asset_residence_unresolved"
    return _durable_asset_note_reason(diagnostic)


def _durable_asset_note_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Keep what the calculation knew about the register with the filed record; none of these withholds anything."""
    if diagnostic.reason == "activity_asset_claim_gap":
        return "activity_asset_claim_gap"
    if diagnostic.reason == "activity_asset_accrual_unavailable":
        return "activity_asset_accrual_unavailable"
    if diagnostic.reason == "activity_asset_activity_undeclared":
        return "activity_asset_activity_undeclared"
    if diagnostic.reason == "activity_asset_agrarian_excluded":
        return "activity_asset_agrarian_excluded"
    if diagnostic.reason == "activity_asset_residence_period_unknown":
        return "activity_asset_residence_period_unknown"
    return _durable_register_note_reason(diagnostic)


def _durable_register_note_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    if diagnostic.reason == "activity_asset_disposal_finding":
        return "activity_asset_disposal_finding"
    if diagnostic.reason == "register_acquisition_exceeds_ledger":
        return "register_acquisition_exceeds_ledger"
    if diagnostic.reason == "register_acquisition_partly_accounted":
        return "register_acquisition_partly_accounted"
    if diagnostic.reason == "register_acquisition_row_missing":
        return "register_acquisition_row_missing"
    if diagnostic.reason == "register_owned_capital_acquisition":
        return "register_owned_capital_acquisition"
    if diagnostic.reason == "ledger_expense_may_be_durable":
        return "ledger_expense_may_be_durable"
    if diagnostic.reason == "household_rows_incomplete":
        return "household_rows_incomplete"
    return None


def _durable_source_issue_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Narrow a diagnostic reason to the durable subset, or ``None``.

    Every durable reason describes a value ABSENT from the filing, or present
    but short of filing grade, which is what a verification or export gate
    reading the persisted revision needs; every
    other reason is calculate-time operator feedback that dies with the
    response. Written as explicit comparisons rather than a set membership test
    so the narrowing is one the type checker can follow — a mismatch between the
    durable set and the persisted model's own ``Literal`` then fails to compile
    instead of at the first calculation that raises the new reason.
    """
    if diagnostic.reason == "unrouted_observation":
        return "unrouted_observation"
    if diagnostic.reason == "unrouted_declarable_quantity":
        return "unrouted_declarable_quantity"
    if diagnostic.reason == "iva_selected_scope_evidence_failure":
        return "iva_selected_scope_evidence_failure"
    if diagnostic.reason == "iva_compensation_annual_source_evidence_failure":
        return "iva_compensation_annual_source_evidence_failure"
    return _durable_binding_gate_reason(diagnostic)


def _durable_binding_gate_reason(diagnostic: CalculationSourceDiagnostic) -> _DurableSourceIssueReason | None:
    """Keep explicit literal narrowing for the binding-keyed durable reasons."""
    if diagnostic.reason == "withholding_detail_absent":
        return "withholding_detail_absent"
    if diagnostic.reason == "unresolved_binding":
        return "unresolved_binding"
    if diagnostic.reason == "terminal_origin_mismatch":
        return "terminal_origin_mismatch"
    if diagnostic.reason == "unhandled_binding_source":
        return "unhandled_binding_source"
    if diagnostic.reason == "advisory_binding_value":
        # A proven zero persists with its stated outcome, which keeps it from withholding anything.
        return "advisory_binding_value"
    return _durable_invoice_source_reason(diagnostic)


def unrouted_source_issues(
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...],
    boxes: PrintedBoxes,
) -> tuple[CalculationSourceIssue, ...]:
    """Project unrouted source conditions into durable revision issues.

    The application diagnostic remains the calculate response, while the domain
    issue keeps the same source kind and actionable text available to a later
    verification/export lifecycle gate.  Provenance intentionally excludes
    these rows because no binding consumed the value they describe.

    Both unrouted reasons are carried. Projecting only the ROW condition would
    leave the quantity condition evaporating with the calculate response, so a
    later gate would see a clean persisted revision for exactly the case the
    row-keyed screens cannot report — the silence the quantity screen exists to
    break.

    Every other reason that withholds filing persists the same way, so a
    reopened declaration still says what blocks it. A box whose source
    produced no value persists only when the form prints it, as ``boxes`` reads
    the published layout: a working figure that could not be worked out is worth
    checking, not a filed figure missing.
    """
    issues = (_unrouted_source_issue(diagnostic, boxes) for diagnostic in source_diagnostics)
    return tuple(issue for issue in issues if issue is not None)


def _unrouted_source_issue(
    diagnostic: CalculationSourceDiagnostic,
    boxes: PrintedBoxes,
) -> CalculationSourceIssue | None:
    """Return the durable issue one source diagnostic persists as, or ``None`` when it persists nothing."""
    precedence_issue = precedence_tier_issue(diagnostic)
    if precedence_issue is not None:
        return precedence_issue
    reason = _durable_source_issue_reason(diagnostic)
    if reason is None:
        return None
    binding_source = durable_binding_source(diagnostic)
    if reason in _BINDING_SOURCE_KEYED_REASONS and binding_source is None:
        return None
    if reason in PRINTED_BOX_REASONS and not boxes.prints(diagnostic.casilla_id):
        return None
    return CalculationSourceIssue(
        reason=reason,
        binding_source=binding_source,
        casilla_id=diagnostic.casilla_id,
        message=(
            "selected-scope IVA evidence failure"
            if reason == "iva_selected_scope_evidence_failure"
            else diagnostic.message[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT]
        ),
        resolver_id=diagnostic.resolver_id,
        source_ref=diagnostic.source_ref,
        fact=diagnostic.fact,
        value_outcome=diagnostic.value_outcome if reason == "advisory_binding_value" else None,
    )


#: The reason a persisted :class:`CalculationSourceIssue` may carry.
_DurableSourceIssueReason = Literal[
    "unrouted_observation",
    "unrouted_declarable_quantity",
    "iva_selected_scope_evidence_failure",
    "iva_compensation_annual_source_evidence_failure",
    "withholding_detail_absent",
    "unresolved_binding",
    "terminal_origin_mismatch",
    "unhandled_binding_source",
    "source_domain_not_ready",
    "invoice_reverse_charge_cuota_not_derivable",
    "m349_operation_unclassified",
    "ledger_amortization_row_unregistered",
    "activity_asset_foral_territory",
    "activity_asset_residence_unresolved",
    "activity_asset_claim_gap",
    "activity_asset_accrual_unavailable",
    "activity_asset_activity_undeclared",
    "activity_asset_agrarian_excluded",
    "activity_asset_residence_period_unknown",
    "activity_asset_disposal_finding",
    "register_acquisition_exceeds_ledger",
    "register_acquisition_partly_accounted",
    "register_acquisition_row_missing",
    "register_owned_capital_acquisition",
    "ledger_expense_may_be_durable",
    "household_rows_incomplete",
    "advisory_binding_value",
    "credit_source_disagreement",
    "credit_cross_check_absent",
    "credit_resolution_stale",
]


_BINDING_SOURCE_KEYED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
    }
)
