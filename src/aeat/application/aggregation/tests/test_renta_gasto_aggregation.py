"""Regression tests for repository-backed M130 deductible-expense (gasto) aggregation.

Tests exercise the full path:
  - real TransactionCatalogueRepository backed by isolated_runtime_profile
  - aggregate_renta_gasto_ledger(_from_repositories) for quarterly cumulative windows
  - resolve_ledger_renta_gasto_aggregation_binding_values against the real M130
    registry revision

The cumulative window rule (RD 439/2007 art. 110.2) mirrors the income pipeline:
Q1 covers Jan-Mar, Q2 covers Jan-Jun, so a Jan expense appears in both Q1 and Q2
totals while a May expense appears only in Q2. Casilla 02 ("Gastos") accumulates
the IVA-exclusive deductible base of OUTGOING business expenses.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    InputKind,
    resolve_ledger_renta_gasto_aggregation_binding_values,
    validated_casilla_id,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._renta_gasto_ledger import (
    RentaGastoLedgerAggregationIssueReason,
    RentaGastoObservation,
    aggregate_renta_gasto_ledger,
    aggregate_renta_gasto_ledger_from_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_Q1_2024 = _period(2024, "1T")
_Q2_2024 = _period(2024, "2T")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"renta gasto aggregation fixture key {value!r} is not a CasillaId") from exc


_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="test") as profile:
        yield profile.repository


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    value_date: date | None,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
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
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": "asesoria_fiscal",
            "taxable_base": taxable_base,
            "iva_rate": None,
            "iva_amount": None,
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
    )
    # Q1 window excludes the May row; expected = the two Q1 input bases.
    assert result_q1.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == sum(
        (q1_a_base, q1_b_base),
        Decimal("0"),
    )
    assert {o.transaction_id for o in result_q1.observations} == {q1_a.transaction_id, q1_b.transaction_id}

    result_q2 = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id="test",
        period=_Q2_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
    )
    # Q2 cumulative window includes all three input bases.
    expected_q2 = sum((q1_a_base, q1_b_base, q2_base), Decimal("0"))
    assert result_q2.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == expected_q2


def test_domain_resolver_folds_gasto_observations_into_the_m130_casilla_02_binding() -> None:
    """The real M130 revision binds casilla 02 to the gasto source and sums the bases.

    Uses the live registry revision (not a synthetic one) so the binding id,
    selector, and casilla wiring under test are exactly what ships. Expected value
    is the sum of the deductible bases, derived from the inputs — never copied
    from engine output.
    """
    modelo_def = next(item for item in resources().modelos.all() if item.id == "130")
    revision = modelo_def.revisions["2019-y-siguientes"]

    casilla_02 = next(c for c in revision.casillas if c.id == _M130_GASTOS_CASILLA)
    assert casilla_02.input_kind is InputKind.BOUND
    binding = next(b for b in revision.bindings if b.id == casilla_02.binding)
    assert str(binding.source) == "ledger_renta_gasto_aggregation"

    feb_base, apr_base = Decimal("147.93"), Decimal("100.00")
    feb = _gasto_transaction("feb", value_date=date(2024, 2, 1), taxable_base=feb_base)
    apr = _gasto_transaction("apr", value_date=date(2024, 4, 2), taxable_base=apr_base)
    catalogue = TransactionCatalogue.from_transactions((feb, apr))
    aggregation = aggregate_renta_gasto_ledger(catalogue, bucket_id="test", period=_Q2_2024)

    resolved = resolve_ledger_renta_gasto_aggregation_binding_values(revision, aggregation.observations)

    # Both rows fall in the 2T cumulative window; expected = the input bases summed.
    assert resolved[binding.id] == sum((feb_base, apr_base), Decimal("0"))
