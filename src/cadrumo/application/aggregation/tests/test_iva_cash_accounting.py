"""Real-behavior tests for Modelo 303 criterio-de-caja IVA projection."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ledger_bindings import resolve_ledger_iva_aggregation_binding_values
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory, IvaLedgerObservationRole
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    IvaLedgerAggregation,
    aggregate_iva_ledger_observations_from_repositories,
    resolve_m303_supplier_regime_arrival,
)
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Q1_2026 = Period.from_year_and_code(2026, "1T")
_Q2_2026 = Period.from_year_and_code(2026, "2T")
_Q3_2026 = Period.from_year_and_code(2026, "3T")
_Q4_2027 = Period.from_year_and_code(2027, "4T")
_PARITY_BUCKET_ID = "5c5c5c5c-5c5c-4c5c-8c5c-5c5c5c5c5c5c"


def _revision_303():
    return bundled_authority().snapshot("303", filing_year=2026, period="2T").revision


def _raw(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente criterio caja",
        description=f"cash-accounting {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    booked_date: date,
    taxable_base: Decimal,
    iva_amount: Decimal,
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE,
    operation_date: date | None = None,
    cash_accounting_payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...] = (),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, booked_date=booked_date, amount=taxable_base + iva_amount),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT
            if direction is TransactionDirection.OUTGOING
            else None,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{provider_id}",
                evidence_digest="a" * 64,
            )
            if direction is TransactionDirection.OUTGOING
            else None,
            "cash_accounting_treatment": cash_accounting_treatment,
            "operation_date": operation_date,
            "cash_accounting_payment_evidence": cash_accounting_payment_evidence,
            "classified_at": datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _binding_values(*transactions: Transaction, period: Period) -> dict[str, Decimal]:
    aggregation = _aggregation(*transactions, period=period)
    assert aggregation.issues == ()
    return resolve_ledger_iva_aggregation_binding_values(_revision_303(), aggregation.observations)


def _aggregation(*transactions: Transaction, period: Period) -> IvaLedgerAggregation:
    return aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(transactions),
        period=period,
    )


class _CommonTransactionFields(TypedDict):
    """The fields the rate-box pair holds constant, so only the axis varies."""

    direction: TransactionDirection
    taxable_base: Decimal
    iva_amount: Decimal


def test_cash_accounting_supply_reports_art75_information_before_collection_and_settles_when_collected() -> None:
    cash_sale = _transaction(
        "cash-sale",
        direction=TransactionDirection.INCOMING,
        booked_date=date(2026, 4, 15),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
        operation_date=date(2026, 3, 20),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 4, 15),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
            ),
        ),
    )
    ordinary_sale = _transaction(
        "ordinary-sale",
        direction=TransactionDirection.INCOMING,
        booked_date=date(2026, 3, 25),
        taxable_base=Decimal("500.00"),
        iva_amount=Decimal("105.00"),
    )

    q1_values = _binding_values(cash_sale, ordinary_sale, period=_Q1_2026)
    assert q1_values["modelo-303-criterio-caja-entregas-art75-base"] == Decimal("1000.00")
    assert q1_values["modelo-303-criterio-caja-entregas-art75-cuota"] == Decimal("210.00")
    assert q1_values["modelo-303-iva-repercutido-general-base"] == Decimal("500.00")
    assert q1_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("105.00")

    q2_values = _binding_values(cash_sale, period=_Q2_2026)
    assert q2_values["modelo-303-criterio-caja-entregas-art75-base"] == Decimal("0")
    assert q2_values["modelo-303-criterio-caja-entregas-art75-cuota"] == Decimal("0")
    assert q2_values["modelo-303-iva-repercutido-general-base"] == Decimal("1000.00")
    assert q2_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("210.00")


def test_cash_accounting_purchase_reports_acquisition_information_without_admitting_ordinary_domestic_rows() -> None:
    cash_purchase = _transaction(
        "supplier-cash-purchase",
        direction=TransactionDirection.OUTGOING,
        booked_date=date(2026, 4, 10),
        taxable_base=Decimal("300.00"),
        iva_amount=Decimal("63.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
        operation_date=date(2026, 3, 12),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 4, 10),
                taxable_base=Decimal("300.00"),
                iva_amount=Decimal("63.00"),
            ),
        ),
    )
    ordinary_purchase = _transaction(
        "ordinary-purchase",
        direction=TransactionDirection.OUTGOING,
        booked_date=date(2026, 3, 22),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
    )

    q1_values = _binding_values(cash_purchase, ordinary_purchase, period=_Q1_2026)
    assert q1_values["modelo-303-criterio-caja-adquisiciones-base"] == Decimal("300.00")
    assert q1_values["modelo-303-criterio-caja-adquisiciones-cuota"] == Decimal("63.00")
    assert q1_values["modelo-303-iva-soportado-interiores-base"] == Decimal("200.00")
    assert q1_values["modelo-303-iva-soportado-interiores-cuota"] == Decimal("42.00")

    q2_values = _binding_values(cash_purchase, period=_Q2_2026)
    assert q2_values["modelo-303-criterio-caja-adquisiciones-base"] == Decimal("0")
    assert q2_values["modelo-303-criterio-caja-adquisiciones-cuota"] == Decimal("0")
    assert q2_values["modelo-303-iva-soportado-interiores-base"] == Decimal("300.00")
    assert q2_values["modelo-303-iva-soportado-interiores-cuota"] == Decimal("63.00")


def test_supplier_regime_arrival_spans_operation_and_partial_settlements_without_duplicate_evidence() -> None:
    """The SI fact is period evidence, whereas cash boxes and money use separate roles.

    One received cash-accounting operation deliberately has two same-quarter
    partial settlements and a later settlement.  The operation information
    projection and every monetary projection retain the supplier affiliation;
    the immutable arrival deduplicates the one ledger identity only after that
    affiliation has established the fact for each relevant filing period.
    """
    cash_purchase = _transaction(
        "supplier-regime-partial",
        direction=TransactionDirection.OUTGOING,
        booked_date=date(2026, 4, 10),
        taxable_base=Decimal("300.00"),
        iva_amount=Decimal("63.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
        operation_date=date(2026, 3, 12),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 3, 14),
                taxable_base=Decimal("50.00"),
                iva_amount=Decimal("10.50"),
            ),
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 3, 28),
                taxable_base=Decimal("100.00"),
                iva_amount=Decimal("21.00"),
            ),
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 4, 10),
                taxable_base=Decimal("150.00"),
                iva_amount=Decimal("31.50"),
            ),
        ),
    )

    q1 = _aggregation(cash_purchase, period=_Q1_2026)
    assert q1.issues == ()
    assert {observation.observation_role for observation in q1.observations} == {
        IvaLedgerObservationRole.OPERATION_INFORMATIONAL,
        IvaLedgerObservationRole.SETTLEMENT,
    }
    assert all(
        observation.cash_accounting_treatment is IvaCashAccountingTreatment.SUPPLIER_REGIME
        for observation in q1.observations
    )
    assert sum(
        (
            observation.base_amount
            for observation in q1.observations
            if observation.observation_role is IvaLedgerObservationRole.SETTLEMENT
        ),
        Decimal("0"),
    ) == Decimal("150.00")
    assert sum(
        (
            observation.base_amount
            for observation in q1.observations
            if observation.observation_role is IvaLedgerObservationRole.OPERATION_INFORMATIONAL
        ),
        Decimal("0"),
    ) == Decimal("300.00")
    assert (
        tuple(type(observation).model_validate_json(observation.model_dump_json()) for observation in q1.observations)
        == q1.observations
    )

    q1_arrival = resolve_m303_supplier_regime_arrival(period=_Q1_2026, iva_aggregation=q1)
    assert q1_arrival.recipient_of_cash_accounting_operations is True
    assert q1_arrival.source_ledger_ids == (cash_purchase.transaction_id,)

    q2 = _aggregation(cash_purchase, period=_Q2_2026)
    assert q2.issues == ()
    assert len(q2.observations) == 1
    assert q2.observations[0].observation_role is IvaLedgerObservationRole.SETTLEMENT
    assert q2.observations[0].cash_accounting_treatment is IvaCashAccountingTreatment.SUPPLIER_REGIME
    assert q2.observations[0].base_amount == Decimal("150.00")
    assert resolve_m303_supplier_regime_arrival(period=_Q2_2026, iva_aggregation=q2).source_ledger_ids == (
        cash_purchase.transaction_id,
    )


def test_supplier_regime_arrival_covers_the_statutory_fallback_and_leaves_empty_periods_blank() -> None:
    """A partial payment leaves a lawful fallback settlement; unrelated periods create no SI artifact."""
    partially_unpaid_purchase = _transaction(
        "supplier-regime-fallback",
        direction=TransactionDirection.OUTGOING,
        booked_date=date(2026, 3, 12),
        taxable_base=Decimal("300.00"),
        iva_amount=Decimal("63.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
        operation_date=date(2026, 3, 12),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 3, 20),
                taxable_base=Decimal("100.00"),
                iva_amount=Decimal("21.00"),
            ),
        ),
    )

    q1 = _aggregation(partially_unpaid_purchase, period=_Q1_2026)
    assert q1.issues == ()
    assert resolve_m303_supplier_regime_arrival(period=_Q1_2026, iva_aggregation=q1).source_ledger_ids == (
        partially_unpaid_purchase.transaction_id,
    )

    empty_q3 = _aggregation(partially_unpaid_purchase, period=_Q3_2026)
    assert empty_q3.observations == ()
    assert tuple(issue.reason.value for issue in empty_q3.issues) == ("outside_period",)
    empty_arrival = resolve_m303_supplier_regime_arrival(period=_Q3_2026, iva_aggregation=empty_q3)
    assert empty_arrival.recipient_of_cash_accounting_operations is False
    assert empty_arrival.source_ledger_ids == ()

    fallback = _aggregation(partially_unpaid_purchase, period=_Q4_2027)
    assert fallback.issues == ()
    assert len(fallback.observations) == 1
    assert fallback.observations[0].transaction_date == date(2027, 12, 31)
    assert fallback.observations[0].observation_role is IvaLedgerObservationRole.SETTLEMENT
    assert fallback.observations[0].base_amount == Decimal("200.00")
    assert resolve_m303_supplier_regime_arrival(period=_Q4_2027, iva_aggregation=fallback).source_ledger_ids == (
        partially_unpaid_purchase.transaction_id,
    )


def test_supplier_regime_arrival_excludes_taxpayer_regime_and_keeps_only_supplier_evidence_in_a_mixed_period() -> None:
    """Taxpayer-regime cash timing is never evidence that the taxpayer received a supplier-regime operation."""
    taxpayer_cash_sale = _transaction(
        "taxpayer-regime-sale",
        direction=TransactionDirection.INCOMING,
        booked_date=date(2026, 3, 20),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
        operation_date=date(2026, 3, 12),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 3, 20),
                taxable_base=Decimal("200.00"),
                iva_amount=Decimal("42.00"),
            ),
        ),
    )
    supplier_cash_purchase = _transaction(
        "supplier-regime-mixed",
        direction=TransactionDirection.OUTGOING,
        booked_date=date(2026, 3, 24),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
        operation_date=date(2026, 3, 14),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 3, 24),
                taxable_base=Decimal("100.00"),
                iva_amount=Decimal("21.00"),
            ),
        ),
    )

    taxpayer_only = _aggregation(taxpayer_cash_sale, period=_Q1_2026)
    assert (
        resolve_m303_supplier_regime_arrival(
            period=_Q1_2026,
            iva_aggregation=taxpayer_only,
        ).recipient_of_cash_accounting_operations
        is False
    )

    mixed = _aggregation(taxpayer_cash_sale, supplier_cash_purchase, period=_Q1_2026)
    mixed_arrival = resolve_m303_supplier_regime_arrival(period=_Q1_2026, iva_aggregation=mixed)
    assert mixed_arrival.recipient_of_cash_accounting_operations is True
    assert mixed_arrival.source_ledger_ids == (supplier_cash_purchase.transaction_id,)


def test_repository_backed_projection_matches_the_pure_projection_for_a_cross_quarter_devengo(
    tmp_path: Path,
) -> None:
    """The persisted read path must reproduce the in-memory projection exactly.

    A criterio-de-caja sale booked in Q2 carries its art. 75 devengo in Q1.
    The in-memory projection reports that Q1 cuota devengada; the
    repository-backed projection selects its candidate rows through the
    plaintext date index, so it must select on the row's eligible-date span
    rather than its filing date or it returns an empty Q1 aggregation and
    silently under-declares.
    """

    cash_sale = _transaction(
        "cross-quarter-devengo",
        direction=TransactionDirection.INCOMING,
        booked_date=date(2026, 4, 15),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
        operation_date=date(2026, 3, 20),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 4, 15),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
            ),
        ),
    )
    catalogue = TransactionCatalogue.from_transactions((cash_sale,))
    pure = aggregate_iva_ledger_observations(catalogue, period=_Q1_2026)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PARITY_BUCKET_ID) as profile:
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(catalogue)
        repository_backed = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=profile.bucket_id,
            period=_Q1_2026,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=profile.bucket_id),
        )

    assert pure.observations != ()
    assert tuple(repository_backed.observations) == tuple(pure.observations)
    assert repository_backed.issues == pure.issues


def _not_subject_transaction(
    provider_id: str,
    *,
    category: IvaCategory,
    cash_accounting_treatment: IvaCashAccountingTreatment,
) -> Transaction:
    """A cuota-less row under the cash-accounting regime, category varied by the caller."""
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, booked_date=date(2026, 2, 10), amount=Decimal("1000.00")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": category,
            "cash_accounting_treatment": cash_accounting_treatment,
            "operation_date": date(2026, 2, 10),
            # The model refuses payment evidence without an active regime, so a
            # NONE-treatment row carries none -- that pairing is the control for
            # the gate keying on the regime rather than on the category alone.
            "cash_accounting_payment_evidence": ()
            if cash_accounting_treatment is IvaCashAccountingTreatment.NONE
            else (
                IvaCashAccountingPaymentEvidence(
                    payment_date=date(2026, 2, 20),
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("0"),
                    recargo_amount=Decimal("0"),
                ),
            ),
            "classified_at": datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _gate_reasons(transaction: Transaction) -> tuple[str, ...]:
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q1_2026,
    )
    return tuple(issue.reason.value for issue in aggregation.issues)


@pytest.mark.parametrize(
    "category",
    [IvaCategory.OPERACION_NO_SUJETA, IvaCategory.DOMESTIC_NOT_SUBJECT],
)
def test_both_not_subject_categories_are_outside_the_cash_accounting_regime(
    category: IvaCategory,
) -> None:
    """Ley 37/1992 art. 163 duodecies.Uno scopes the regime to operations realizadas en el TAI.

    An operation that is not subject in the TAI is outside by SCOPE and matches
    no letter of apartado Dos, so both not-subject members belong in the
    exclusion set on that ground. `DOMESTIC_NOT_SUBJECT` was previously absent
    while its twin was present, with nothing in the set distinguishing the two
    mechanisms it carries -- which is how the omission survived.
    """
    transaction = _not_subject_transaction(
        f"not-subject-{category.value}",
        category=category,
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
    )

    assert _gate_reasons(transaction) == ("cash_accounting_excluded_category",)


def test_an_exempt_domestic_supply_still_enters_the_cash_accounting_regime() -> None:
    """Anti-vacuity: the gate refuses the excluded set, not every cuota-less row.

    A domestic exempt supply is realizada en el TAI and is not an apartado-Dos
    carve-out, so it stays inside the regime. Without this the parametrized
    refusal above would pass equally if the gate rejected everything.
    """
    transaction = _not_subject_transaction(
        "exempt-inside-regime",
        category=IvaCategory.DOMESTIC_EXEMPT,
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
    )

    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q1_2026,
    )

    assert aggregation.issues == ()
    assert aggregation.observations != ()


def test_a_not_subject_row_outside_the_regime_is_not_refused_by_this_gate() -> None:
    """The gate keys on the regime being active, not on the category alone.

    A not-subject row with no cash-accounting treatment must not trip the
    exclusion -- otherwise the fix would refuse ordinary not-subject rows that
    never claimed the regime at all.
    """
    transaction = _not_subject_transaction(
        "not-subject-ordinary",
        category=IvaCategory.DOMESTIC_NOT_SUBJECT,
        cash_accounting_treatment=IvaCashAccountingTreatment.NONE,
    )

    assert "cash_accounting_excluded_category" not in _gate_reasons(transaction)


_M390_EJERCICIO = 2025


def _m390_repercutido_values(transaction: Transaction) -> dict[str, Decimal]:
    """Resolve the real M390 repercutido bindings for one transaction."""
    # Modelo 390 is annual and AEAT publishes an ejercicio's design late in that
    # same year, so ejercicio 2026 has no instrument yet. The caller's claim is
    # an equality between two economically identical sales within ONE ejercicio,
    # so it is year-agnostic and reads the latest published one.
    annual = Period.from_year_and_code(_M390_EJERCICIO, "0A")
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=annual,
    )
    assert aggregation.issues == ()
    # The revision is RESOLVED from the same period the observations were
    # aggregated for, never pinned: an id literal names one moment in the
    # registry and rots on the next span split, and pinning a different year's
    # id would compute this period under another year's norms.
    revision = (
        bundled_authority()
        .snapshot(
            Modelo.M390.value,
            filing_year=annual.filing_year,
            period=annual.registry_token,
        )
        .revision
    )
    resolved = resolve_ledger_iva_aggregation_binding_values(
        revision,
        aggregation.observations,
    )
    return {key: value for key, value in resolved.items() if value and "repercutido" in key}


def test_cash_accounting_row_reaches_the_same_rate_boxes_as_an_ordinary_row() -> None:
    """A criterio-de-caja sale must fill the official rate boxes, not only its tier total.

    ``applied_rate is None`` is a claim that the rate is genuinely unknown, and
    it makes an observation match no rate-specific binding. A cash-accounting
    row knows its rate as well as any other -- ``rate_kind`` is resolved FROM
    it -- so omitting it filed an M390 whose tier totals were populated while
    every rate box beneath them was blank, a return that contradicts itself.

    Asserted as an equality between the two producers on economically identical
    sales, so it cannot be satisfied by both going blank, and pinned to the
    declared rate's own boxes.
    """
    # Declared, not inferred: an untyped mapping widens each value to the union
    # of all three, so the splat below reads as offering a Decimal where a
    # direction is expected and checks none of them.
    common: _CommonTransactionFields = {
        "direction": TransactionDirection.INCOMING,
        "taxable_base": Decimal("1000.00"),
        "iva_amount": Decimal("210.00"),
    }
    ordinary = _transaction("ordinary-rate-box", booked_date=date(2025, 4, 20), **common)
    cash = _transaction(
        "cash-rate-box",
        booked_date=date(2025, 4, 15),
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
        operation_date=date(2025, 4, 10),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2025, 4, 15),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
            ),
        ),
        **common,
    )

    ordinary_values = _m390_repercutido_values(ordinary)
    cash_values = _m390_repercutido_values(cash)

    assert cash_values == ordinary_values
    # Pins the shared result to the declared 21 % boxes, so the equality above
    # cannot be satisfied by both filings losing the rate breakdown.
    assert ordinary_values["modelo-390-iva-repercutido-tipo-21-base"] == Decimal("1000.00")
    assert ordinary_values["modelo-390-iva-repercutido-tipo-21-cuota"] == Decimal("210.00")
