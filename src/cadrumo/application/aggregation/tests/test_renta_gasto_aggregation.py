"""Pure aggregation-rule tests for M130 deductible-expense (gasto) behavior.

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
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.tests.published_authority import published_revision

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
)
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..renta_gasto_ledger import (
    RentaGastoLedgerAggregation,
    RentaGastoLedgerAggregationIssueReason,
    RentaGastoObservation,
    aggregate_renta_gasto_ledger,
)
from ..renta_ledger import (
    RentaLedgerAggregationIssueReason,
    aggregate_renta_ledger_expenses,
)
from .renta_income_aggregation_support import _period
from .usage_ratio_support import (
    HOME_OFFICE_SUMINISTRO_RATIO,
    dwelling_classify_share,
    dwelling_profile,
    dwelling_usage_ratios,
)

SECURE_OBJECTS_BUCKET_ID = "78804f92-b6f7-4daf-9ddf-a8ce3829dbb1"

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


_Q1_2024 = _period(2025, "1T")
_Q2_2024 = _period(2025, "2T")


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
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
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
    category_id: str = "asesoria_fiscal",
    usage_ratio_id: str | None = None,
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
            "category_id": category_id,
            "usage_ratio_id": usage_ratio_id,
            "taxable_base": taxable_base,
            "iva_rate": None,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


# ---------------------------------------------------------------------------
# Pure-aggregator tests (no repository)
# ---------------------------------------------------------------------------


def test_q1_window_sums_jan_mar_expense_bases() -> None:
    """Q1 cumulative window [Jan 1 to Mar 31] sums the deductible bases into casilla 02."""
    jan_base, feb_base, mar_base = Decimal("100.00"), Decimal("200.00"), Decimal("50.00")
    jan = _gasto_transaction("jan", value_date=date(2025, 1, 15), taxable_base=jan_base)
    feb = _gasto_transaction("feb", value_date=date(2025, 2, 20), taxable_base=feb_base)
    mar = _gasto_transaction("mar", value_date=date(2025, 3, 31), taxable_base=mar_base)
    apr = _gasto_transaction("apr", value_date=date(2025, 4, 1), taxable_base=Decimal("999.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, feb, mar, apr))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

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
    jan = _gasto_transaction("jan", value_date=date(2025, 1, 10), taxable_base=jan_base)
    may = _gasto_transaction("may", value_date=date(2025, 5, 5), taxable_base=may_base)
    jul = _gasto_transaction("jul", value_date=date(2025, 7, 1), taxable_base=Decimal("400.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, may, jul))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q2_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

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
        value_date=date(2025, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert result.observations[0].deductible_amount == Decimal("100.00")
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("100.00")


def test_untagged_expense_is_surfaced_not_gross_folded() -> None:
    """An untagged expense (no taxable_base) is surfaced, not gross-folded (F2 fix).

    The gross transfer carries IVA soportado (recovered through Modelo 303), which
    is not a Renta gasto. Gross-folding would OVER-declare gastos (and under-state
    the pago fraccionado). The row is surfaced as MISSING_TAXABLE_BASE so the
    operator tags it; it does not contribute an observation.
    """
    tx = _gasto_transaction("untagged", value_date=date(2025, 2, 1), amount=Decimal("80.00"), taxable_base=None)
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaGastoLedgerAggregationIssueReason.MISSING_TAXABLE_BASE
    assert _M130_GASTOS_CASILLA not in result.casilla_aggregation.casilla_values


def test_mixed_classification_applies_business_pct() -> None:
    """A MIXED expense contributes only its business fraction of the base."""
    tx = _gasto_transaction(
        "mixed",
        value_date=date(2025, 3, 1),
        taxable_base=Decimal("200.00"),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.50"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert result.observations[0].deductible_amount == Decimal("100.00")


def test_personal_outgoing_is_skipped_silently() -> None:
    """A personal expense is not a deducible gasto and produces no observation or issue."""
    tx = _gasto_transaction(
        "personal",
        value_date=date(2025, 2, 1),
        taxable_base=Decimal("75.00"),
        business_classification=BusinessClassification.PERSONAL,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

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
        value_date=date(2025, 2, 1),
        amount=Decimal("217.80"),
        taxable_base=actividad_base,
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    untagged = _gasto_transaction(
        "actividad-untagged",
        value_date=date(2025, 2, 1),
        amount=Decimal("217.80"),
        taxable_base=actividad_base,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((tagged, untagged))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert {observation.transaction_id for observation in result.observations} == {tagged.transaction_id}
    assert result.observations[0].deductible_amount == actividad_base
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == actividad_base
    assert result.issues == ()


def test_reviewed_excluded_irpf_actividad_gasto_stays_excluded() -> None:
    """A final reviewed exclusion cannot re-enter through the actividad category."""
    tx = _gasto_transaction(
        "reviewed-excluded",
        value_date=date(2025, 2, 1),
        taxable_base=Decimal("125.00"),
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.REVIEWED_EXCLUDED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert result.observations == ()
    assert result.issues == ()
    assert _M130_GASTOS_CASILLA not in result.casilla_aggregation.casilla_values


def test_incoming_transaction_is_not_a_gasto() -> None:
    """An INCOMING receipt is the income pipeline's concern, never a gasto."""
    tx = _gasto_transaction(
        "income",
        value_date=date(2025, 2, 1),
        taxable_base=Decimal("500.00"),
        direction=TransactionDirection.INCOMING,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert result.observations == ()
    assert result.issues == ()


def test_inactive_transaction_skipped_silently() -> None:
    """An archived/tombstoned expense never reaches the aggregation."""
    tx = _gasto_transaction(
        "inactive",
        value_date=date(2025, 2, 1),
        taxable_base=Decimal("100.00"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert result.observations == ()
    assert result.issues == ()


def test_all_observations_target_casilla_02() -> None:
    """Every gasto observation targets casilla 02 — structural pin for the binding contract."""
    transactions = [
        _gasto_transaction(f"tx-{i}", value_date=date(2025, 1, i + 1), taxable_base=Decimal("10.00")) for i in range(5)
    ]
    catalogue = TransactionCatalogue.from_transactions(transactions)

    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert all(o.target_casilla_id == _M130_GASTOS_CASILLA for o in result.observations)
    assert result.casilla_aggregation.modelo == "130"


def test_gasto_observation_rejects_legacy_target_casilla_key() -> None:
    transactions = [
        _gasto_transaction("tx-legacy-key", value_date=date(2025, 1, 1), taxable_base=Decimal("10.00")),
    ]
    result = aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions(transactions),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )
    payload = result.observations[0].model_dump()
    payload["target_casilla"] = payload.pop("target_casilla_id")

    with pytest.raises(ValidationError) as exc_info:
        RentaGastoObservation.model_validate(payload)

    detail = str(exc_info.value)
    assert "target_casilla_id" in detail
    assert "target_casilla" in detail


def test_domain_resolver_folds_gasto_observations_into_the_m130_casilla_02_binding() -> None:
    """The real M130 revision binds casilla 02 to the gasto source and sums the bases.

    Uses the live registry revision (not a synthetic one) so the binding id,
    selector, and casilla wiring under test are exactly what ships. Expected value
    is the sum of the deductible bases, derived from the inputs — never copied
    from engine output.
    """
    revision = published_revision("130", "2019-y-siguientes")

    casilla_02 = next(c for c in revision.casillas if c.id == _M130_GASTOS_CASILLA)
    assert casilla_02.input_kind is InputKind.BOUND
    binding = next(b for b in revision.bindings if b.id == casilla_02.binding)
    assert str(binding.source) == "ledger_renta_gastos_pago_fraccionado_aggregation"

    feb_base, apr_base = Decimal("147.93"), Decimal("100.00")
    feb = _gasto_transaction("feb", value_date=date(2025, 2, 1), taxable_base=feb_base)
    apr = _gasto_transaction("apr", value_date=date(2025, 4, 2), taxable_base=apr_base)
    catalogue = TransactionCatalogue.from_transactions((feb, apr))
    aggregation = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q2_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

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
        value_date=date(2025, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=actividad_base,
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    quarterly = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )
    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_period(2025, "0A"),
        profile_year=2025,
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
        value_date=date(2025, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        irpf_category="actividad_economica",
        business_classification=BusinessClassification.BUSINESS,
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    quarterly = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )
    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_period(2025, "0A"),
        profile_year=2025,
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
        value_date=date(2025, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_period(2025, "0A"),
        profile_year=2025,
    )

    assert [issue.reason for issue in annual.issues] == [
        RentaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE,
    ]


# ---------------------------------------------------------------------------
# The category rule apportions a usage-ratio row once, as it does annually.
# ---------------------------------------------------------------------------

_HOME_OFFICE_LUZ = "suministros_home_office_luz"
_DWELLING_BASE = Decimal("100.00")
#: Worked by hand from the dwelling profile: 20 / 100 = 0.20, and 0.30 * 0.20 = 0.06 of a 100.00 base.
_DWELLING_DEDUCTION = Decimal("6.00")


def _quarterly(
    *rows: Transaction,
    usage_ratios: dict[SpendingCategory, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> RentaGastoLedgerAggregation:
    return aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions(rows),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        usage_ratios=usage_ratios,
        profile_record=dwelling_profile(),
        operation=operation,
    )


def _dwelling_row(
    provider_id: str,
    classification: BusinessClassification,
    *,
    operation: PinnedAuthorityOperation,
    irpf_category: str | None = None,
) -> Transaction:
    """Return a 100.00 home-office luz bill classified as the classify path stamps it."""
    category = SpendingCategory.from_registry(_HOME_OFFICE_LUZ)
    mixed = classification is BusinessClassification.MIXED
    return _gasto_transaction(
        provider_id,
        value_date=date(2025, 2, 1),
        amount=Decimal("121.00"),
        taxable_base=_DWELLING_BASE,
        category_id=category.value,
        business_classification=classification,
        business_pct=dwelling_classify_share(dwelling_profile(), category, operation=operation) if mixed else None,
        usage_ratio_id=category.value if mixed else None,
        irpf_category=irpf_category,
    )


@pytest.mark.parametrize(
    "classification",
    [BusinessClassification.BUSINESS, BusinessClassification.MIXED],
    ids=["business", "mixed"],
)
def test_home_office_gasto_deducts_the_statutory_share_once(
    classification: BusinessClassification,
    operation: PinnedAuthorityOperation,
) -> None:
    """LIRPF art. 30.2.5.b reaches casilla 02 as it reaches the annual return: once.

    A BUSINESS row used to deduct its whole base here, because the quarterly path
    never consulted the usage ratio; a MIXED row deducted its stored share. Both now
    come out of the category rule: 100.00 * 0.06 = 6.00, whatever the row's share
    (the 0.20 degree of use, which feeds IVA only).
    """
    profile = dwelling_profile()
    ratios = dwelling_usage_ratios(profile, bucket_id=SECURE_OBJECTS_BUCKET_ID, operation=operation)
    assert ratios[SpendingCategory.from_registry(_HOME_OFFICE_LUZ)] == HOME_OFFICE_SUMINISTRO_RATIO
    row = _dwelling_row("home-office", classification, operation=operation)

    result = _quarterly(row, usage_ratios=ratios, operation=operation)

    assert result.issues == ()
    deducted = result.observations[0].deductible_amount
    assert deducted == _DWELLING_DEDUCTION, f"{classification.value} gasto deducted {deducted}, expected 6.00"
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == _DWELLING_DEDUCTION


def test_activity_marker_does_not_lift_a_mixed_home_office_row_past_its_category_rule(
    operation: PinnedAuthorityOperation,
) -> None:
    """A MIXED row carrying the actividad marker still deducts 6.00, not its whole base.

    The marker used to return full attribution before the classification was read,
    so the row deducted 100.00 whatever its share and whatever its category rule.
    """
    profile = dwelling_profile()
    ratios = dwelling_usage_ratios(profile, bucket_id=SECURE_OBJECTS_BUCKET_ID, operation=operation)
    row = _dwelling_row(
        "marked-mixed",
        BusinessClassification.MIXED,
        operation=operation,
        irpf_category="actividad_economica",
    )

    result = _quarterly(row, usage_ratios=ratios, operation=operation)

    assert result.issues == ()
    assert result.observations[0].deductible_amount == _DWELLING_DEDUCTION


def test_activity_marker_admits_an_unclassified_home_office_row_but_the_category_rule_apportions_it(
    operation: PinnedAuthorityOperation,
) -> None:
    """The marker supplies eligibility only; the usage ratio still decides the amount."""
    profile = dwelling_profile()
    ratios = dwelling_usage_ratios(profile, bucket_id=SECURE_OBJECTS_BUCKET_ID, operation=operation)
    row = _dwelling_row(
        "marked-unclassified",
        BusinessClassification.NOT_YET_PROCESSED,
        operation=operation,
        irpf_category="actividad_economica",
    )

    result = _quarterly(row, usage_ratios=ratios, operation=operation)

    assert result.issues == ()
    assert result.observations[0].deductible_amount == _DWELLING_DEDUCTION


def test_activity_marker_does_not_lift_a_mixed_row_in_a_plain_category_past_its_share(
    operation: PinnedAuthorityOperation,
) -> None:
    """Outside the usage-ratio categories the MIXED share is the apportionment: 0.50 of 200.00.

    The marker used to return full attribution ahead of the classification, so this
    row deducted its whole 200.00.
    """
    row = _gasto_transaction(
        "marked-mixed-plain",
        value_date=date(2025, 2, 1),
        taxable_base=Decimal("200.00"),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.50"),
        irpf_category="actividad_economica",
    )

    result = _quarterly(row, operation=operation)

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("100.00")


def test_home_office_gasto_without_a_ratio_is_surfaced_not_deducted_in_full(
    operation: PinnedAuthorityOperation,
) -> None:
    """With no afectacion ratio the rule refuses the row; it is never summed at full value."""
    row = _dwelling_row("no-ratio", BusinessClassification.BUSINESS, operation=operation)

    result = _quarterly(row, usage_ratios={}, operation=operation)

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        RentaGastoLedgerAggregationIssueReason.INELIGIBLE_DEDUCTIBILITY
    ]
    assert "missing usage ratio" in result.issues[0].detail
    assert _M130_GASTOS_CASILLA not in result.casilla_aggregation.casilla_values


@pytest.mark.parametrize(
    "classification",
    [BusinessClassification.BUSINESS, BusinessClassification.MIXED],
    ids=["business", "mixed"],
)
def test_operator_usage_ratio_on_a_dwelling_lease_gasto_applies_once(
    classification: BusinessClassification,
    operation: PinnedAuthorityOperation,
) -> None:
    """A stored 25 per cent dwelling-lease ratio deducts 25.00 of a 100.00 base, not 100.00 or 6.25."""
    category = SpendingCategory.from_registry("arrendamiento_vivienda_afecto")
    mixed = classification is BusinessClassification.MIXED
    row = _gasto_transaction(
        "lease",
        value_date=date(2025, 2, 1),
        taxable_base=_DWELLING_BASE,
        category_id=category.value,
        business_classification=classification,
        business_pct=Decimal("0.25") if mixed else None,
        usage_ratio_id=category.value if mixed else None,
    )

    result = _quarterly(row, usage_ratios={category: Decimal("0.25")}, operation=operation)

    assert result.issues == ()
    deducted = result.observations[0].deductible_amount
    assert deducted == Decimal("25.00"), f"{classification.value} lease gasto deducted {deducted}, expected 25.00"


def test_quarterly_and_annual_deduct_the_same_home_office_rows(operation: PinnedAuthorityOperation) -> None:
    """The two filings cannot diverge on a usage-ratio row: both total 12.00 for two 100.00 bills."""
    profile = dwelling_profile()
    ratios = dwelling_usage_ratios(profile, bucket_id=SECURE_OBJECTS_BUCKET_ID, operation=operation)
    rows = (
        _dwelling_row("parity-business", BusinessClassification.BUSINESS, operation=operation),
        _dwelling_row("parity-mixed", BusinessClassification.MIXED, operation=operation),
    )
    catalogue = TransactionCatalogue.from_transactions(rows)

    quarterly = _quarterly(*rows, usage_ratios=ratios, operation=operation)
    annual = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_period(2025, "0A"),
        profile_year=2025,
        usage_ratios=ratios,
        profile_record=profile,
        operation=operation,
    )

    assert annual.issues == quarterly.issues == ()
    assert sum(o.deductible_amount for o in quarterly.observations) == Decimal("12.00")
    assert sum(annual.casilla_values.values()) == Decimal("12.00")
