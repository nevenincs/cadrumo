"""Real-behavior tests for Modelo 303 criterio-de-caja IVA projection."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import resolve_ledger_iva_aggregation_binding_values
from ....domain.iva import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import aggregate_iva_ledger_observations, aggregate_iva_ledger_observations_from_repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Q1_2026 = Period.from_year_and_code(2026, "1T")
_Q2_2026 = Period.from_year_and_code(2026, "2T")
_PARITY_BUCKET_ID = "5c5c5c5c-5c5c-4c5c-8c5c-5c5c5c5c5c5c"


def _revision_303():
    return resources().modelos.get("303").revisions["2023-y-siguientes"]


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
            "cash_accounting_treatment": cash_accounting_treatment,
            "operation_date": operation_date,
            "cash_accounting_payment_evidence": cash_accounting_payment_evidence,
            "classified_at": datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _binding_values(*transactions: Transaction, period: Period) -> dict[str, Decimal]:
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(transactions),
        period=period,
    )
    assert aggregation.issues == ()
    return resolve_ledger_iva_aggregation_binding_values(_revision_303(), aggregation.observations)


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


def _m390_repercutido_values(transaction: Transaction) -> dict[str, Decimal]:
    """Resolve the real M390 repercutido bindings for one transaction."""
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=Period.from_year_and_code(2026, "0A"),
    )
    assert aggregation.issues == ()
    resolved = resolve_ledger_iva_aggregation_binding_values(
        resources().modelos.get("390").revisions["2010-y-siguientes"],
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
    ordinary = _transaction("ordinary-rate-box", booked_date=date(2026, 4, 20), **common)
    cash = _transaction(
        "cash-rate-box",
        booked_date=date(2026, 4, 15),
        cash_accounting_treatment=IvaCashAccountingTreatment.TAXPAYER_REGIME,
        operation_date=date(2026, 4, 10),
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(2026, 4, 15),
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
