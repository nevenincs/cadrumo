"""Regression tests for repository-backed M130 deductible-expense (gasto) aggregation.

Tests exercise the full path:
  - real TransactionCatalogueRepository backed by isolated_runtime_profile
  - aggregate_renta_gasto_ledger(_from_repositories) for quarterly cumulative windows
  - resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values against the real M130
    registry revision

The cumulative window rule (RD 439/2007 art. 110.2) mirrors the income pipeline:
Q1 covers Jan-Mar, Q2 covers Jan-Jun, so a Jan expense appears in both Q1 and Q2
totals while a May expense appears only in Q2. Casilla 02 ("Gastos") accumulates
the IVA-exclusive deductible base of OUTGOING business expenses.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ._secure_objects_fixtures import secure_objects

__all__ = ["secure_objects"]
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, ProrrataProvisionalProvenance, ProrrataRegisterRegime, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    InputKind,
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
)
from ....domain.invoices import InvoiceCatalogue
from ....domain.prorrata_register import ProrrataRegisterEntry
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._renta_gasto_ledger import (
    RentaGastoLedgerAggregationIssueReason,
    RentaGastoObservation,
    aggregate_renta_gasto_ledger,
    aggregate_renta_gasto_ledger_from_repositories,
)
from .._renta_ledger import (
    RentaLedgerAggregationIssueReason,
    aggregate_renta_ledger_expenses,
    aggregate_renta_ledger_expenses_from_repositories,
)
from ._renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_Q1_2024 = _period(2024, "1T")
_Q2_2024 = _period(2024, "2T")


_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    value_date: date | None,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Proveedor SA",
        description=f"gasto row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _gasto_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = None,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": "asesoria_fiscal",
            "taxable_base": taxable_base,
            "iva_rate": None,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


# ---------------------------------------------------------------------------
# Pure-aggregator tests (no repository)
# ---------------------------------------------------------------------------


def test_q1_window_sums_jan_mar_expense_bases() -> None:
    """Q1 cumulative window [Jan 1 to Mar 31] sums the deductible bases into casilla 02."""
    jan_base, feb_base, mar_base = Decimal("100.00"), Decimal("200.00"), Decimal("50.00")
    jan = _gasto_transaction("jan", value_date=date(2024, 1, 15), taxable_base=jan_base)
    feb = _gasto_transaction("feb", value_date=date(2024, 2, 20), taxable_base=feb_base)
    mar = _gasto_transaction("mar", value_date=date(2024, 3, 31), taxable_base=mar_base)
    apr = _gasto_transaction("apr", value_date=date(2024, 4, 1), taxable_base=Decimal("999.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, feb, mar, apr))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    observation_ids = {o.transaction_id for o in result.observations}
    assert observation_ids == {jan.transaction_id, feb.transaction_id, mar.transaction_id}
    # April is outside the Q1 window — surfaced as a dropped declarable gasto.
    issue_ids = {i.transaction_id for i in result.issues}
    assert apr.transaction_id in issue_ids
    assert result.issues[0].reason == RentaGastoLedgerAggregationIssueReason.OUTSIDE_PERIOD
    # Expected casilla 02 derived from the in-window input bases (apr excluded).
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == sum(
        (jan_base, feb_base, mar_base),
        Decimal("0"),
    )


def test_q2_window_accumulates_jan_through_jun() -> None:
    """Q2 cumulative window [Jan 1 to Jun 30] includes Q1 rows too (YTD rule)."""
    jan_base, may_base = Decimal("100.00"), Decimal("250.00")
    jan = _gasto_transaction("jan", value_date=date(2024, 1, 10), taxable_base=jan_base)
    may = _gasto_transaction("may", value_date=date(2024, 5, 5), taxable_base=may_base)
    jul = _gasto_transaction("jul", value_date=date(2024, 7, 1), taxable_base=Decimal("400.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, may, jul))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q2_2024)

    observation_ids = {o.transaction_id for o in result.observations}
    assert observation_ids == {jan.transaction_id, may.transaction_id}
    # jul is outside the Q2 cumulative window; expected = the two in-window bases.
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == sum(
        (jan_base, may_base),
        Decimal("0"),
    )


def test_taxable_base_preferred_over_gross_for_deductible_amount() -> None:
    """The IVA-exclusive base imponible is the deductible gasto, not the gross transfer.

    IVA soportado is recovered through Modelo 303 and is not a Renta gasto, so a
    tagged transaction contributes its base (100), never its IVA-inclusive gross
    (121).
    """
    tx = _gasto_transaction(
        "tagged",
        value_date=date(2024, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations[0].deductible_amount == Decimal("100.00")
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("100.00")


def test_untagged_expense_is_surfaced_not_gross_folded() -> None:
    """An untagged expense (no taxable_base) is surfaced, not gross-folded (F2 fix).

    The gross transfer carries IVA soportado (recovered through Modelo 303), which
    is not a Renta gasto. Gross-folding would OVER-declare gastos (and under-state
    the pago fraccionado). The row is surfaced as MISSING_TAXABLE_BASE so the
    operator tags it; it does not contribute an observation.
    """
    tx = _gasto_transaction("untagged", value_date=date(2024, 2, 1), amount=Decimal("80.00"), taxable_base=None)
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaGastoLedgerAggregationIssueReason.MISSING_TAXABLE_BASE
    assert _M130_GASTOS_CASILLA not in result.casilla_aggregation.casilla_values


def test_mixed_classification_applies_business_pct() -> None:
    """A MIXED expense contributes only its business fraction of the base."""
    tx = _gasto_transaction(
        "mixed",
        value_date=date(2024, 3, 1),
        taxable_base=Decimal("200.00"),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.50"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations[0].deductible_amount == Decimal("100.00")


def test_personal_outgoing_is_skipped_silently() -> None:
    """A personal expense is not a deducible gasto and produces no observation or issue."""
    tx = _gasto_transaction(
        "personal",
        value_date=date(2024, 2, 1),
        taxable_base=Decimal("75.00"),
        business_classification=BusinessClassification.PERSONAL,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()
    assert _M130_GASTOS_CASILLA not in result.casilla_aggregation.casilla_values


def test_irpf_actividad_economica_gasto_flows_despite_unclassified_business() -> None:
    """Explicit actividad-economica category is the M130 gasto eligibility gate.

    Casilla 02 covers fiscalmente deducible gastos imputables to direct-estimation
    actividades economicas over the same year-to-date window as casilla 01. A row
    explicitly tagged with ``irpf_category=actividad_economica`` must therefore
    flow even before the broad business-classification sweep marks it BUSINESS.
    """
    actividad_base = Decimal("180.00")
    tagged = _gasto_transaction(
        "actividad-tagged",
        value_date=date(2024, 2, 1),
        amount=Decimal("217.80"),
        taxable_base=actividad_base,
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    untagged = _gasto_transaction(
        "actividad-untagged",
        value_date=date(2024, 2, 1),
        amount=Decimal("217.80"),
        taxable_base=actividad_base,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((tagged, untagged))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert {observation.transaction_id for observation in result.observations} == {tagged.transaction_id}
    assert result.observations[0].deductible_amount == actividad_base
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == actividad_base
    assert result.issues == ()


def test_reviewed_excluded_irpf_actividad_gasto_stays_excluded() -> None:
    """A final reviewed exclusion cannot re-enter through the actividad category."""
    tx = _gasto_transaction(
        "reviewed-excluded",
        value_date=date(2024, 2, 1),
        taxable_base=Decimal("125.00"),
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.REVIEWED_EXCLUDED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()
    assert _M130_GASTOS_CASILLA not in result.casilla_aggregation.casilla_values


def test_incoming_transaction_is_not_a_gasto() -> None:
    """An INCOMING receipt is the income pipeline's concern, never a gasto."""
    tx = _gasto_transaction(
        "income",
        value_date=date(2024, 2, 1),
        taxable_base=Decimal("500.00"),
        direction=TransactionDirection.INCOMING,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()


def test_inactive_transaction_skipped_silently() -> None:
    """An archived/tombstoned expense never reaches the aggregation."""
    tx = _gasto_transaction(
        "inactive",
        value_date=date(2024, 2, 1),
        taxable_base=Decimal("100.00"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()


def test_all_observations_target_casilla_02() -> None:
    """Every gasto observation targets casilla 02 — structural pin for the binding contract."""
    transactions = [
        _gasto_transaction(f"tx-{i}", value_date=date(2024, 1, i + 1), taxable_base=Decimal("10.00")) for i in range(5)
    ]
    catalogue = TransactionCatalogue.from_transactions(transactions)

    result = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert all(o.target_casilla_id == _M130_GASTOS_CASILLA for o in result.observations)
    assert result.casilla_aggregation.modelo == "130"


def test_gasto_observation_rejects_legacy_target_casilla_key() -> None:
    transactions = [
        _gasto_transaction("tx-legacy-key", value_date=date(2024, 1, 1), taxable_base=Decimal("10.00")),
    ]
    result = aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions(transactions),
        bucket_id="test",
        period=_Q1_2024,
    )
    payload = result.observations[0].model_dump()
    payload["target_casilla"] = payload.pop("target_casilla_id")

    with pytest.raises(ValidationError) as exc_info:
        RentaGastoObservation.model_validate(payload)

    detail = str(exc_info.value)
    assert "target_casilla_id" in detail
    assert "target_casilla" in detail


# ---------------------------------------------------------------------------
# Repository-backed path + domain resolver against the real M130 revision
# ---------------------------------------------------------------------------


def test_repository_backed_aggregation_emits_casilla_02_sum(
    secure_objects: SecureObjectRepository,
) -> None:
    """Full path: persist -> load from repo -> aggregate -> correct casilla 02 value."""
    q1_a_base, q1_b_base, q2_base = Decimal("120.00"), Decimal("80.00"), Decimal("300.00")
    q1_a = _gasto_transaction("q1-a", value_date=date(2024, 2, 1), taxable_base=q1_a_base)
    q1_b = _gasto_transaction("q1-b", value_date=date(2024, 3, 15), taxable_base=q1_b_base)
    q2_only = _gasto_transaction("q2-only", value_date=date(2024, 5, 10), taxable_base=q2_base)

    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((q1_a, q1_b, q2_only)))

    result_q1 = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )
    # Q1 window excludes the May row; expected = the two Q1 input bases.
    assert result_q1.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == sum(
        (q1_a_base, q1_b_base),
        Decimal("0"),
    )
    assert {o.transaction_id for o in result_q1.observations} == {q1_a.transaction_id, q1_b.transaction_id}
    # Regression: the excluded May row must surface as a visible
    # compact summary, not silently vanish.
    assert result_q1.issues == ()
    assert result_q1.out_of_window_summary is not None
    assert result_q1.out_of_window_summary.count == 1
    assert result_q1.out_of_window_summary.min_filing_date == date(2024, 5, 10)
    assert result_q1.out_of_window_summary.max_filing_date == date(2024, 5, 10)

    result_q2 = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q2_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )
    # Q2 cumulative window includes all three input bases.
    expected_q2 = sum((q1_a_base, q1_b_base, q2_base), Decimal("0"))
    assert result_q2.out_of_window_summary is None
    assert result_q2.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == expected_q2


def test_repository_backed_aggregation_summarizes_previously_silent_out_of_window_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary.

    A wrong-direction incoming row is ignored before the in-window gasto
    classifier runs because this aggregation owns outgoing rows. When that row
    falls outside the requested cumulative window, the repository-backed
    partition reports its count and date span instead of dropping it before
    aggregation.
    """
    in_window = _gasto_transaction("row-in-window", value_date=date(2024, 2, 1), taxable_base=Decimal("50.00"))
    wrong_direction_out_of_window = _gasto_transaction(
        "row-wrong-direction-out-of-window",
        value_date=date(2024, 5, 10),
        taxable_base=Decimal("90.00"),
        direction=TransactionDirection.INCOMING,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((in_window, wrong_direction_out_of_window)))

    result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )

    assert {o.transaction_id for o in result.observations} == {in_window.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2024, 5, 10)
    assert result.out_of_window_summary.max_filing_date == date(2024, 5, 10)


def test_repository_backed_aggregation_partition_matches_full_scan(
    secure_objects: SecureObjectRepository,
) -> None:
    """The partitioned result matches the full-scan result for declared values.

    The same multi-period catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and casilla totals/provenance must match; only the
    out-of-window issue taxonomy can differ.
    """
    q1_row = _gasto_transaction("row-q1", value_date=date(2024, 2, 1), taxable_base=Decimal("50.00"))
    q3_row = _gasto_transaction("row-q3", value_date=date(2024, 8, 1), taxable_base=Decimal("70.00"))
    wrong_direction_q3_row = _gasto_transaction(
        "row-q3-wrong-direction",
        value_date=date(2024, 9, 1),
        taxable_base=Decimal("30.00"),
        direction=TransactionDirection.INCOMING,
    )
    catalogue = TransactionCatalogue.from_transactions((q1_row, q3_row, wrong_direction_q3_row))
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(catalogue)

    partitioned = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )
    full_scan = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert set(partitioned.observations) == set(full_scan.observations)
    assert partitioned.casilla_aggregation.casilla_values == full_scan.casilla_aggregation.casilla_values
    assert set(partitioned.casilla_aggregation.provenance) == set(full_scan.casilla_aggregation.provenance)
    assert {o.transaction_id for o in partitioned.observations} == {q1_row.transaction_id}

    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 2
    assert partitioned.out_of_window_summary.min_filing_date == date(2024, 8, 1)
    assert partitioned.out_of_window_summary.max_filing_date == date(2024, 9, 1)

    full_scan_issue_ids = {i.transaction_id for i in full_scan.issues}
    assert full_scan_issue_ids == {q3_row.transaction_id}
    assert wrong_direction_q3_row.transaction_id not in full_scan_issue_ids


def test_domain_resolver_folds_gasto_observations_into_the_m130_casilla_02_binding() -> None:
    """The real M130 revision binds casilla 02 to the gasto source and sums the bases.

    Uses the live registry revision (not a synthetic one) so the binding id,
    selector, and casilla wiring under test are exactly what ships. Expected value
    is the sum of the deductible bases, derived from the inputs — never copied
    from engine output.
    """
    modelo_def = resources().modelos.get("130")
    revision = modelo_def.revisions["2019-y-siguientes"]

    casilla_02 = next(c for c in revision.casillas if c.id == _M130_GASTOS_CASILLA)
    assert casilla_02.input_kind is InputKind.BOUND
    binding = next(b for b in revision.bindings if b.id == casilla_02.binding)
    assert str(binding.source) == "ledger_renta_gastos_pago_fraccionado_aggregation"

    feb_base, apr_base = Decimal("147.93"), Decimal("100.00")
    feb = _gasto_transaction("feb", value_date=date(2024, 2, 1), taxable_base=feb_base)
    apr = _gasto_transaction("apr", value_date=date(2024, 4, 2), taxable_base=apr_base)
    catalogue = TransactionCatalogue.from_transactions((feb, apr))
    aggregation = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q2_2024)

    resolved = resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
        revision, aggregation.observations
    )

    # Both rows fall in the 2T cumulative window; expected = the input bases summed.
    assert resolved[binding.id] == sum((feb_base, apr_base), Decimal("0"))


def test_actividad_marked_row_accepted_by_m130_is_visibly_held_by_m100() -> None:
    """The same row cannot be accepted quarterly and dropped annually without a reason.

    The two Renta expense projections decided business eligibility with separate
    implementations: M130 honoured an explicit ``actividad_economica`` IRPF
    category as full business attribution, while the annual M100 first-slice
    projection consulted the business classification alone. An activity-marked
    row not yet swept by the classification review therefore fed a pago
    fraccionado while the annual declaration built from the same ledger reported
    it only as a generic unclassified state -- indistinguishable from a row
    carrying no classification signal at all.

    Both now consume one predicate, and the annual gate is a declared argument
    of it. The annual refusal names the actual state, so the operator can see
    that the quarterly pipeline already accepted the row and what clears it.
    """
    actividad_base = Decimal("100.00")
    transaction = _gasto_transaction(
        "actividad-pending-review",
        value_date=date(2024, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=actividad_base,
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    quarterly = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)
    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id="test",
        period=_period(2024, "0A"),
        profile_year=2024,
    )

    # The quarterly pago fraccionado accepts the row.
    assert {observation.transaction_id for observation in quarterly.observations} == {transaction.transaction_id}

    # The annual declaration holds it, and says so specifically.
    assert not annual.observations
    assert [issue.reason for issue in annual.issues] == [
        RentaLedgerAggregationIssueReason.ACTIVITY_MARKED_PENDING_ANNUAL_REVIEW,
    ]
    assert annual.issues[0].transaction_id == transaction.transaction_id


def test_reviewed_business_row_is_accepted_by_both_projections() -> None:
    """The positive control: once reviewed, the same row feeds quarterly and annual alike.

    Without this, the held-row assertion above would also hold for an annual
    projection that refused every activity-marked row unconditionally.
    """
    transaction = _gasto_transaction(
        "actividad-reviewed",
        value_date=date(2024, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.BUSINESS,
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    quarterly = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q1_2024)
    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id="test",
        period=_period(2024, "0A"),
        profile_year=2024,
    )

    assert {observation.transaction_id for observation in quarterly.observations} == {transaction.transaction_id}
    assert {observation.transaction_id for observation in annual.observations} == {transaction.transaction_id}


def test_unmarked_unclassified_row_still_reports_the_generic_state() -> None:
    """A row with no activity marker keeps the generic unclassified reason.

    The new reason is narrower, not a rename: it must not absorb rows that
    carry no classification signal at all.
    """
    transaction = _gasto_transaction(
        "no-marker",
        value_date=date(2024, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id="test",
        period=_period(2024, "0A"),
        profile_year=2024,
    )

    assert [issue.reason for issue in annual.issues] == [
        RentaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE,
    ]


# ---------------------------------------------------------------------------
# IVA-deduction ratio derived from the profile's ``iva.regime`` fact and the
# bucket's ProrrataRegister, driven through the real repository path -- the
# SAME resolver the M100 annual first slice uses
# (application.aggregation._renta_ledger._resolve_iva_deduction_ratio), for the
# SAME ejercicio, so the two filings cannot diverge on it.
# ---------------------------------------------------------------------------


def _profile_with_iva_regime(*iva_facts: UserProfileFact) -> UserProfileRecord:
    """Build a user-profile record from explicitly supplied IVA facts."""
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="44444444-4444-4444-8444-444444444444",
        facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"), *iva_facts),
    )


def test_repository_wrapper_exento_iva_regime_joins_the_full_iva_to_the_quarterly_gasto(
    secure_objects: SecureObjectRepository,
) -> None:
    """A wholly ``EXENTO`` taxpayer's non-deductible input IVA joins the M130 gasto, end to end.

    Same medico radiologo figures the M100 side proves against the AEAT Manual
    practico de Renta 2024 (Parte 1, Capitulo 7): base 8.000,00 EUR, IVA
    soportado 1.600,00 EUR. LIVA art. 20.Uno.3.º gives the activity NO right to
    deduct any of its input IVA (art. 94.Uno a contrario), and that legal fact is
    unchanged between the annual declaration and the quarterly pago fraccionado
    (LIRPF arts. 28-30 base-imponible deductibility governs both identically).
    Drives the real repository path -- a transaction carrying its own
    taxable_base/iva_amount and a profile declaring ``iva.regime = EXENTO`` --
    never a hand-built ratio.
    """
    row = _gasto_transaction(
        "row-exento",
        value_date=date(2024, 2, 1),
        amount=Decimal("9600.00"),
        taxable_base=Decimal("8000.00"),
        iva_amount=Decimal("1600.00"),
    )
    TransactionCatalogueRepository(bucket_id="test", objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )

    def _run(profile_record: UserProfileRecord | None) -> Decimal:
        result = aggregate_renta_gasto_ledger_from_repositories(
            bucket_id="test",
            period=_Q1_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
            profile_record=profile_record,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
        )
        assert result.issues == ()
        return result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA]

    exento_total = _run(
        _profile_with_iva_regime(
            UserProfileFact(path="iva.regime", value="EXENTO"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    assert exento_total == Decimal("9600.00")

    # Without the EXENTO fact the historic base-only behaviour stands: only the
    # net-of-IVA base is deductible, proving the ratio is the actual selector.
    general_total = _run(_profile_with_iva_regime())
    assert general_total == Decimal("8000.00")


def test_repository_wrapper_general_prorrata_register_joins_the_non_deductible_share_quarterly(
    secure_objects: SecureObjectRepository,
) -> None:
    """A GENERAL-prorrata register entry joins the non-recoverable IVA share into M130, end to end.

    Same 70% figures the M100 side proves against LIVA art. 104.Uno: base
    1.000,00 EUR, IVA soportado 210,00 EUR, of which 30% (63,00 EUR) has no
    right to deduct. Seeds a real
    :class:`~domain.prorrata_register.ProrrataRegister` entry for the SAME
    ejercicio the quarterly period falls in, exercising the identical
    ``resolve_provisional`` resolution the M303 and M100 sides already apply --
    the PROVISIONAL percentage, not the definitive one, since the year is not
    yet over when a Q1 pago fraccionado is computed.
    """
    row = _gasto_transaction(
        "row-prorrata",
        value_date=date(2024, 2, 1),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id="test", objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id="test", objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        ),
    )

    result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )

    assert result.issues == ()
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("1063.00")


def test_repository_wrapper_ninguna_prorrata_regime_is_byte_identical_to_absent_entry_quarterly(
    secure_objects: SecureObjectRepository,
) -> None:
    """A ``NINGUNA`` regime entry (full deduction rights) changes nothing for M130 either.

    ``NINGUNA`` means the taxpayer performs only con-derecho operations, so no
    percentage apportions the cuotas (LIVA art. 94 stands unmodified) -- the
    quarterly fold-in must fall through to the historic base-only behaviour
    exactly as if no register entry existed at all.
    """
    row = _gasto_transaction(
        "row-ninguna",
        value_date=date(2024, 2, 1),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id="test", objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id="test", objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(ejercicio=2024, regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None),
    )

    result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )

    assert result.issues == ()
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("1000.00")


def test_m130_and_m100_resolve_the_same_iva_deduction_ratio_for_the_same_ejercicio(
    secure_objects: SecureObjectRepository,
) -> None:
    """The quarterly and annual filings cannot diverge on the deduction ratio.

    ``aggregate_renta_gasto_ledger_from_repositories`` (M130) and
    ``aggregate_renta_ledger_expenses_from_repositories`` (M100) both read the
    SAME transaction from the SAME bucket and resolve the SAME 70% GENERAL
    register entry through the SAME ``_resolve_iva_deduction_ratio`` function
    for the SAME ejercicio -- verified end to end through both real repository
    paths rather than assumed from the shared-resolver claim alone.
    """
    row = _gasto_transaction(
        "row-shared",
        value_date=date(2024, 2, 1),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id="test", objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id="test", objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        ),
    )

    m130_result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )
    assert m130_result.issues == ()
    assert m130_result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("1063.00")

    m100_result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id="test",
        period=_period(2024, "0A"),
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects),
        profile_year=2024,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id="test", objects=secure_objects),
    )
    assert m100_result.issues == ()
    assert m100_result.observations[0].deductible_amount == Decimal("1063.00")
