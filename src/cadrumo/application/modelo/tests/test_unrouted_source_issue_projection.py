"""Both unrouted conditions survive to the persisted revision, not just the row one.

Resolver diagnostics live and die with the calculate response; a verify or
export gate runs later against the persisted ``CalculationRevision`` and reads
``source_issues``. The projector filtered on ``unrouted_observation`` alone, so
the QUANTITY condition evaporated — meaning a later gate saw a clean revision
for exactly the case the row-keyed screens cannot report, restoring the silence
the quantity screen exists to break one layer down.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationSourceIssue
from ...aggregation.source_mesh import CalculationSourceDiagnostic, CalculationSourceDiagnosticReason
from ..calculation_actions import _unrouted_source_issues
from ..printed_boxes import snapshot_printed_boxes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _project(
    operation: PinnedAuthorityOperation, diagnostics: tuple[CalculationSourceDiagnostic, ...]
) -> tuple[CalculationSourceIssue, ...]:
    """Project diagnostics against the Modelo 130 first-quarter revision, whose box 01 the form prints."""
    snapshot = operation.snapshot("130", filing_year=2026, period="1T")
    return _unrouted_source_issues(diagnostics, snapshot_printed_boxes(operation, snapshot))


def _diagnostic(reason: CalculationSourceDiagnosticReason, message: str) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind="ledger_iva_aggregation",
        resolver_id="ledger_iva_aggregation",
        message=message,
    )


def test_both_unrouted_reasons_reach_the_persisted_revision(operation: PinnedAuthorityOperation) -> None:
    """The row condition and the quantity condition are both durable."""
    issues = _project(
        operation,
        (
            _diagnostic("unrouted_observation", "a row no binding consumes"),
            _diagnostic("unrouted_declarable_quantity", "1 IVA row(s) carry 1000.00 EUR of base"),
        ),
    )

    assert {issue.reason for issue in issues} == {
        "unrouted_observation",
        "unrouted_declarable_quantity",
    }
    assert all(issue.binding_source is BindingSourceKind.LEDGER_IVA_AGGREGATION for issue in issues)


def test_each_issue_keeps_its_own_reason(operation: PinnedAuthorityOperation) -> None:
    """Guards the projector that hardcoded one reason for every row it emitted.

    Stamping a single literal would satisfy the test above as long as both
    diagnostics passed the filter, while mislabelling the quantity condition as
    a row condition in the persisted evidence.
    """
    issues = _project(
        operation,
        (_diagnostic("unrouted_declarable_quantity", "the quantity condition, alone"),),
    )

    assert len(issues) == 1
    assert issues[0].reason == "unrouted_declarable_quantity"
    assert issues[0].message == "the quantity condition, alone"


def test_calculate_time_only_diagnostics_stay_out_of_the_revision(operation: PinnedAuthorityOperation) -> None:
    """Anti-over-capture control.

    ``source_issues`` is a narrow durable envelope for values absent from the
    filing, not a dump of every resolver diagnostic. An advisory that describes
    a value the filing DOES carry must not be persisted as an unrouted
    condition.
    """
    issues = _project(
        operation,
        (
            _diagnostic("ungrounded_income_substrate", "consumed, but on cash"),
            _diagnostic("devengo_date_proxy_attribution", "issue date stood in"),
        ),
    )

    assert issues == ()


def test_a_diagnostic_with_no_binding_source_is_not_persisted(operation: PinnedAuthorityOperation) -> None:
    """An unrouted condition is read by its binding source, so one without any cannot be projected.

    The later gates select the unrouted and evidence reasons by binding
    source; persisting one with none would store an issue no gate reads.
    """
    orphan = CalculationSourceDiagnostic(
        reason="unrouted_declarable_quantity",
        source_kind="not_a_binding_source",
        resolver_id="whatever",
        message="carries no canonical binding source",
    )

    assert orphan.binding_source is None
    assert _project(operation, (orphan,)) == ()


@pytest.mark.parametrize(
    "reason",
    (
        "missing_taxable_base",
        "missing_iva_amount",
        "missing_iva_rate",
        "unsupported_currency",
        "missing_eur_tax_substrate",
        "unsupported_iva_rate",
        "missing_deduction_classification",
        "cuota_on_zero_rated_row",
        "non_zero_rate_on_zero_cuota_category",
        "non_arising_category_for_invoice_side",
        "missing_counterparty_identification_state",
        "missing_counterparty_establishment_on_export",
        "domestic_identification_on_intra_community_transaction",
        "eu_member_state_on_export_transaction",
    ),
)
def test_selected_scope_iva_evidence_failures_are_durable_and_sanitized(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    transaction_id = "a" * 64
    issues = _project(
        operation,
        (
            CalculationSourceDiagnostic(
                reason="iva_selected_scope_evidence_failure",
                source_kind="ledger_iva_aggregation",
                resolver_id="ledger_iva_aggregation",
                source_ref=f"transaction:{transaction_id}",
                message=f"selected-scope IVA evidence failure: {reason}",
            ),
        ),
    )

    assert len(issues) == 1
    assert issues[0].reason == "iva_selected_scope_evidence_failure"
    assert issues[0].source_ref == f"transaction:{transaction_id}"
    assert issues[0].message == "selected-scope IVA evidence failure"


def test_required_m390_annual_partition_evidence_failure_is_durable(operation: PinnedAuthorityOperation) -> None:
    """A missing, stale, or contradictory filed-303 source reaches later gates."""
    issues = _project(
        operation,
        (
            CalculationSourceDiagnostic(
                reason="iva_compensation_annual_source_evidence_failure",
                source_kind="iva_compensation_annual_partition",
                resolver_id="iva_compensation_annual_partition",
                message="required Modelo 303 annual partition evidence is unresolved",
            ),
        ),
    )

    assert len(issues) == 1
    assert issues[0].reason == "iva_compensation_annual_source_evidence_failure"
    assert issues[0].binding_source is BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    assert issues[0].message == "required Modelo 303 annual partition evidence is unresolved"


@pytest.mark.parametrize(
    "reason",
    ("outside_period", "reviewed_excluded", "unsupported_iva_category"),
)
def test_nonblocking_iva_diagnostics_do_not_become_durable_completeness_issues(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    issues = _project(
        operation,
        (
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="ledger_iva_aggregation",
                resolver_id="ledger_iva_aggregation",
                source_ref=f"transaction:{'a' * 64}",
                message=f"selected-scope IVA evidence failure: {reason}",
            ),
        ),
    )

    assert issues == ()


def test_generic_source_issue_cannot_spoof_a_durable_iva_completeness_failure(
    operation: PinnedAuthorityOperation,
) -> None:
    issues = _project(
        operation,
        (
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="ledger_iva_aggregation",
                resolver_id="ledger_iva_aggregation",
                source_ref=f"transaction:{'a' * 64}",
                message="selected-scope IVA evidence failure: missing_iva_rate",
            ),
        ),
    )

    assert issues == ()


def test_a_printed_box_whose_source_produced_nothing_persists_with_its_box(operation: PinnedAuthorityOperation) -> None:
    unresolved = CalculationSourceDiagnostic(
        reason="unresolved_binding",
        source_kind="ledger_renta_income_aggregation",
        casilla_id="01",
        message="binding for casilla '01' produced no value",
    )

    (issue,) = _project(operation, (unresolved,))

    assert issue.reason == "unresolved_binding"
    assert issue.casilla_id == "01"
    assert issue.binding_source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION


def test_a_working_figure_whose_source_produced_nothing_does_not_persist(operation: PinnedAuthorityOperation) -> None:
    """Teeth for the rule above: the same condition on a box the form does not print is not a filed figure."""
    revision = operation.snapshot("130", filing_year=2026, period="1T").revision
    unprinted = next(
        str(casilla.id) for casilla in revision.casillas if casilla.form_number is None and not casilla.number.isdigit()
    )
    unresolved = CalculationSourceDiagnostic(
        reason="unresolved_binding",
        source_kind="ledger_renta_income_aggregation",
        casilla_id=unprinted,
        message="binding for a working figure produced no value",
    )

    assert _project(operation, (unresolved,)) == ()


def test_a_blocking_reason_that_names_no_binding_source_persists(operation: PinnedAuthorityOperation) -> None:
    mismatch = CalculationSourceDiagnostic(
        reason="terminal_origin_mismatch",
        source_kind="terminal_origin_audit",
        message="a value arrived by an undeclared route",
    )

    (issue,) = _project(operation, (mismatch,))

    assert issue.reason == "terminal_origin_mismatch"
    assert issue.binding_source is None
