"""Real-behavior tests for Modelo 303 criterio-de-caja IVA projection."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import (
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaLedgerObservationRole,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ..iva_ledger import (
    IvaLedgerAggregation,
    aggregate_iva_ledger_observations_from_repositories,
)
from ..m303_arrivals import (
    resolve_m303_supplier_regime_arrival,
)
from .iva_authority_support import aggregate_iva_ledger_observations

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


def test_repository_backed_projection_matches_the_pure_projection_for_a_cross_quarter_devengo(
    tmp_path: Path,
) -> None:
    """The persisted read path must reproduce the in-memory projection exactly.

    A supplier-regime purchase booked in Q2 carries its art. 75 devengo in Q1.
    The in-memory projection reports that Q1 cuota devengada; the
    repository-backed projection selects its candidate rows through the
    plaintext date index, so it must select on the row's eligible-date span
    rather than its filing date or it returns an empty Q1 aggregation and
    silently under-declares.
    """

    cash_purchase = _transaction(
        "cross-quarter-devengo",
        direction=TransactionDirection.OUTGOING,
        booked_date=date(2026, 4, 15),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
        operation_date=date(2026, 3, 20),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 4, 15),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
            ),
        ),
    )
    catalogue = TransactionCatalogue.from_transactions((cash_purchase,))
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
