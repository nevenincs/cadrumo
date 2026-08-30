"""A row whose category admits no cuota may not also declare a tipo.

The mirror of the zero-rated-row refusal, one field over. That guard refuses a
0 % tipo carrying a cuota; this one refuses a category whose cuota is zero BY
LAW carrying a non-zero tipo. A tipo is what produces a cuota, so declaring one
on an operation that admits none is the same self-contradiction read from the
other end.

WHY THE KIND IS HALF THE QUESTION. ``domestic_reverse_charge`` is zero-cuota on
the ISSUED side only: the supplier charges nothing under LIVA art. 84.Uno.2 and
the recipient self-assesses. The received side of the identical category carries
a real cuota at a real tipo. A screen keyed on the category alone would refuse
every self-assessed acquisition in the ledger, which is why the received-side
control below is not decoration.

WHERE THE EXPECTATION COMES FROM. The zero-cuota fact is read from the Axis-A
component table through :func:`~domain.iva.category_cuota_is_zero_by_law`, which
is already the invoices path's authority for it. The table was enforced on that
path and independently re-derived on this one, and that asymmetry is how the two
came to disagree; consulting it here closes the asymmetry rather than adding a
third statement of the same legal fact. It also means this refusal covers every
zero-cuota category the table declares -- exempt, not-subject, exportación,
entrega intracomunitaria -- rather than the reverse-charge case that motivated
it, and picks up a new one the day the table declares it.

SIZE. Correctness-only on legitimate data: an issued reverse-charge row records
a zero cuota, so nothing about the amounts changes when it is refused. It is
money-bearing only on a row that contradicts itself, where a non-zero tipo today
carries its cuota into the devengada aggregation as though the supplier had
charged it.

Real-behaviour: real :class:`~domain.transactions.Transaction` rows through the
real ``aggregate_iva_ledger_observations`` classifier. No mocks, stubs, skips or
xfail. The population is constructed rows exercising what the code ACCEPTS, not
taxpayer data, which this repository does not hold.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.ledger_bindings import IvaLedgerObservation
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._iva_ledger import IvaLedgerAggregationIssueReason
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PERIOD = Period.from_year_and_code(2024, "4T")
_ON = date(2024, 11, 6)
_BASE = Decimal("1000.00")
#: Distinct from the base, so a check confusing the two would not land here.
_CUOTA = Decimal("210.00")


def _transaction(
    row_id: str,
    *,
    direction: TransactionDirection,
    category: IvaCategory,
    iva_rate: Decimal,
    iva_amount: Decimal,
    gross: Decimal,
) -> Transaction:
    """Build one ledger row.

    ``gross`` is passed rather than derived because the two category families
    reconstitute it differently: a self-assessed row's gross equals its base
    (the cuota was never paid to the supplier), while an ordinary row's gross is
    base plus cuota. The :class:`Transaction` model enforces both, so deriving
    one shape here would make half the fixtures unconstructible.
    """
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=row_id,
                booked_date=_ON,
                value_date=_ON,
                amount=gross,
                currency="EUR",
                counterparty="Contraparte",
                description=f"operacion {row_id}",
                provenance=RawProvenance(
                    source_path=Path("ledger.csv"),
                    source_sha256="e" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(2024, 12, 1, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "taxable_base": _BASE,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": category,
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT
            if direction is TransactionDirection.OUTGOING
            else None,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{row_id}",
                evidence_digest="e" * 64,
            )
            if direction is TransactionDirection.OUTGOING
            else None,
            "exemption_article": None,
            "art_104_tres_exclusion": None,
            "prorrata_reference": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "fx_rate": None,
            "value_in_eur": None,
            "classified_at": datetime(2024, 12, 2, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregate(transaction: Transaction) -> tuple[Sequence[IvaLedgerObservation], list[str]]:
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)
    return aggregation.observations, [issue.reason.value for issue in aggregation.issues]


def _issued_reverse_charge(row_id: str, *, iva_rate: Decimal, iva_amount: Decimal) -> Transaction:
    """A supply the taxpayer made under inversión del sujeto pasivo.

    Gross equals base: the taxpayer charged no cuota, so none moved.
    """
    return _transaction(
        row_id,
        direction=TransactionDirection.INCOMING,
        category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        gross=_BASE,
    )


def test_an_issued_reverse_charge_row_declaring_a_tipo_is_refused() -> None:
    """The live shape: an art. 84.Uno.2 supply cannot carry a 21 % tipo."""
    observations, reasons = _aggregate(
        _issued_reverse_charge("row-issued-rc-rated", iva_rate=Decimal("0.21"), iva_amount=_CUOTA),
    )
    assert list(observations) == [], "a self-contradicting reverse-charge supply produced an observation"
    assert reasons == [IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY.value]


def test_a_clean_issued_reverse_charge_row_still_produces_its_observation() -> None:
    """Positive control: the refusal differs from acceptance in the rate alone.

    A guard keyed on the CATEGORY rather than on the category-plus-tipo
    contradiction would delete every issued reverse-charge supply from the
    return, which is a silent under-declaration of its base.
    """
    observations, reasons = _aggregate(
        _issued_reverse_charge("row-issued-rc-clean", iva_rate=Decimal("0"), iva_amount=Decimal("0")),
    )
    assert reasons == []
    assert len(observations) == 1
    assert observations[0].base_amount == _BASE, "the legitimate reverse-charge supply lost its base imponible"
    assert observations[0].iva_amount == Decimal("0")


def test_a_received_reverse_charge_row_at_the_same_rate_is_untouched() -> None:
    """The control that makes the KIND load-bearing rather than incidental.

    Identical category and identical tipo, opposite side. Here the taxpayer is
    the sujeto pasivo and self-assesses a real cuota, so refusing this row would
    delete the devengada AND deducible entries of every acquisition under
    inversión del sujeto pasivo.
    """
    observations, reasons = _aggregate(
        _transaction(
            "row-received-rc",
            direction=TransactionDirection.OUTGOING,
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            iva_rate=Decimal("0.21"),
            iva_amount=_CUOTA,
            gross=_BASE,
        ),
    )
    assert reasons == []
    assert len(observations) == 1
    assert observations[0].iva_amount == _CUOTA


def test_an_exempt_row_declaring_a_tipo_is_refused_by_the_same_screen() -> None:
    """The refusal is table-driven, so it reaches beyond the reverse-charge case.

    An exención under LIVA art. 20 admits no cuota either, and a row declaring a
    21 % tipo on one is the same contradiction. This is what a hand-listed set of
    reverse-charge categories would have missed.
    """
    observations, reasons = _aggregate(
        _transaction(
            "row-exempt-rated",
            direction=TransactionDirection.INCOMING,
            category=IvaCategory.DOMESTIC_EXEMPT,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("0"),
            gross=_BASE,
        ),
    )
    assert list(observations) == []
    assert reasons == [IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY.value]


def test_an_ordinary_rated_sale_is_untouched() -> None:
    """Second positive control: the screen must not reach a cuota-bearing category.

    ``domestic_general`` requires a cuota by law, so a 21 % tipo on it is the
    ordinary case. A screen that fired on "row declares a tipo" would empty the
    return.
    """
    observations, reasons = _aggregate(
        _transaction(
            "row-general",
            direction=TransactionDirection.INCOMING,
            category=IvaCategory.DOMESTIC_GENERAL,
            iva_rate=Decimal("0.21"),
            iva_amount=_CUOTA,
            gross=_BASE + _CUOTA,
        ),
    )
    assert reasons == []
    assert len(observations) == 1
    assert observations[0].iva_amount == _CUOTA


def test_the_refusal_names_the_category_the_side_and_the_rate() -> None:
    """Three facts, because the operator has to know which one to repair.

    The category alone does not identify the contradiction -- the same category
    is legitimate on the other side -- so the side and the tipo have to travel
    with it.
    """
    transaction = _issued_reverse_charge("row-detail", iva_rate=Decimal("0.21"), iva_amount=_CUOTA)
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    detail = aggregate_iva_ledger_observations(catalogue, period=_PERIOD).issues[0].detail
    assert IvaCategory.DOMESTIC_REVERSE_CHARGE.value in detail
    assert "issued" in detail
    assert "0.21" in detail
