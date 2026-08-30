"""Retención derivation on actividad-económica income rows.

The precondition these gates cover used to require a recorded ``iva_amount``,
which excluded precisely the invoices whose withholding matters most: an
IVA-exempt professional service (LIVA art. 20) has no cuota to record, so its
retención was never recovered and the row contributed nothing to the
retenciones casilla while its income was also mis-measured -- one missing field,
two wrong figures.

Three properties are pinned here, each of which a later edit could plausibly
break in a way that silently changes a declared figure:

* a cuota that is zero BY LAW is as good as a recorded zero, while an absent
  cuota with no declared category stays unknown -- nullness alone cannot tell
  those apart, which is the conflation the whole contract exists to remove;
* the registry maximum supported rate bounds the inference, including on the
  newly admitted rows, which the Transaction gross invariant never sees;
* the base is never reconstructed from the cash by assuming a rate.

Withholding figures here are invoice arithmetic (declared gross minus declared
cash), not the output of a registry formula under test. The 15 % bound is read
from the registry parameter rather than restated.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ....domain.iva import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.retencion_parameters import maximum_supported_activity_retencion_rate
from .._renta_income_ledger import RentaIncomeObservation, aggregate_renta_income_ledger
from .._renta_income_ledger import _income_withheld_amount as income_withheld_amount

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _raw(provider_id: str, *, amount: Decimal, value_date: date) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=value_date,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente SA",
        description=f"income row {provider_id}",
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


def _income_row(
    provider_id: str,
    *,
    cash: str,
    taxable_base: str | None = None,
    iva_amount: str | None = None,
    iva_rate: str | None = None,
    iva_category: IvaCategory | None = None,
    irpf_category: str | None = "actividad_economica",
    value_date: date = date(2024, 3, 15),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, amount=Decimal(cash), value_date=value_date),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": None if taxable_base is None else Decimal(taxable_base),
            "iva_amount": None if iva_amount is None else Decimal(iva_amount),
            "iva_rate": None if iva_rate is None else Decimal(iva_rate),
            "iva_category": iva_category,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def test_exempt_professional_invoice_recovers_its_retencion() -> None:
    """A cuota-less operation still withholds; the base is what it withholds from.

    2000 base, no cuota by law (LIVA art. 20), 1700 banked. The 300 difference
    is the retención practicada, which the old both-fields precondition dropped.
    """
    row = _income_row(
        "exempt-professional",
        cash="1700.00",
        taxable_base="2000.00",
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
    )

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("300.00")
    assert inference.derivation is LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA


def test_declared_cuota_row_still_derives_and_says_so() -> None:
    """The pre-existing route is unchanged and now names itself.

    2000 base + 420 IVA = 2420 invoice gross, 2120 banked, 300 withheld.
    """
    row = _income_row(
        "rated-professional",
        cash="2120.00",
        taxable_base="2000.00",
        iva_amount="420.00",
        iva_rate="0.21",
        iva_category=IvaCategory.DOMESTIC_GENERAL,
    )

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("300.00")
    assert inference.derivation is LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA


def test_absent_cuota_without_a_declared_category_stays_unknown() -> None:
    """An untagged row is not an exempt row, however identical the amounts look.

    Same base and cash as the exempt case above. The only difference is that no
    IVA category is declared, so the cuota is genuinely unknown rather than
    known to be zero -- and a withholding must not be derived from a gross the
    row never established.
    """
    row = _income_row("untagged", cash="1700.00", taxable_base="2000.00")

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.NO_SUBSTRATE


def test_row_without_a_base_derives_nothing_rather_than_inverting_a_rate() -> None:
    """Cash alone never yields a retención.

    Reconstructing the base as ``cash / (1 - r)`` would require selecting ``r``,
    which is a per-row legal fact this application cannot determine. The row
    therefore reports no substrate instead of a plausible figure.
    """
    row = _income_row("cash-only", cash="1700.00", iva_category=IvaCategory.DOMESTIC_EXEMPT)

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.NO_SUBSTRATE


def test_inference_above_the_supported_rate_is_refused_not_capped() -> None:
    """An implied withholding beyond the bound is dropped, and says it was.

    2000 base with 1000 banked implies 50 % withheld, far above the RIRPF
    art. 95.1 general rate. The likelier reading is that the cash is the base
    without IVA, so the figure is refused. Capping it at the bound would invent
    a withholding at exactly the legal maximum, which is worse than none.

    This row is the one the Transaction gross invariant cannot see: it carries
    no ``iva_amount``, so that invariant returns before its own bound check.
    """
    row = _income_row(
        "over-bound",
        cash="1000.00",
        taxable_base="2000.00",
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
    )

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE


def test_the_refusal_boundary_is_the_registry_rate_not_a_local_literal() -> None:
    """A withholding exactly at the registry maximum is accepted, a cent more is not."""
    rate = maximum_supported_activity_retencion_rate()
    base = Decimal("2000.00")
    at_bound = base * rate

    accepted = income_withheld_amount(
        _income_row(
            "at-bound",
            cash=str(base - at_bound),
            taxable_base=str(base),
            iva_category=IvaCategory.DOMESTIC_EXEMPT,
        ),
    )
    refused = income_withheld_amount(
        _income_row(
            "over-bound-by-a-cent",
            cash=str(base - at_bound - Decimal("0.01")),
            taxable_base=str(base),
            iva_category=IvaCategory.DOMESTIC_EXEMPT,
        ),
    )

    assert accepted.amount == at_bound
    assert accepted.derivation is LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA
    assert refused.amount == Decimal("0")
    assert refused.derivation is LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE


def test_cash_covering_the_invoice_withheld_nothing() -> None:
    """Substrate sufficed and nothing was held back; that is not missing data."""
    row = _income_row(
        "paid-in-full",
        cash="2000.00",
        taxable_base="2000.00",
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
    )

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.NONE_WITHHELD


def test_non_actividad_row_reports_not_applicable() -> None:
    """A row outside actividades económicas has no retención to derive."""
    row = _income_row("no-category", cash="1700.00", taxable_base="2000.00", irpf_category=None)

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.NOT_APPLICABLE


def test_the_exempt_recovery_reaches_the_aggregated_observation() -> None:
    """The derivation is carried on the observation, not only inside the helper."""
    catalogue = TransactionCatalogue.from_transactions(
        (
            _income_row(
                "exempt-aggregated",
                cash="1700.00",
                taxable_base="2000.00",
                iva_category=IvaCategory.DOMESTIC_EXEMPT,
            ),
        ),
    )

    aggregation = aggregate_renta_income_ledger(
        catalogue,
        bucket_id="test",
        period=Period.from_year_and_code(2024, "1T"),
    )

    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.withheld_amount == Decimal("300.00")
    assert observation.withheld_derivation is LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA


def test_a_derived_marker_without_a_figure_is_refused() -> None:
    """A zero beside an inference marker would make the marker unreadable."""
    with pytest.raises(ValueError, match="claims a derived figure"):
        RentaIncomeObservation.model_validate(
            {
                "transaction_id": "720e1f85a69c11123bde21f70e4d24351509111d2fead5ee3c22ec243ee65931",
                "target_casilla_id": "01",
                "gross_amount": Decimal("1700.00"),
                "taxable_base_amount": Decimal("2000.00"),
                "withheld_amount": Decimal("0"),
                "withheld_derivation": LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA,
                "filing_date": date(2024, 3, 15),
                "grounding": LedgerIncomeGrounding.SUBSTRATE_DECLARED,
            },
        )


def test_a_refusal_carrying_the_figure_it_refused_is_rejected() -> None:
    """The refusal marker must never travel with the amount it declined to emit."""
    with pytest.raises(ValueError, match="must not carry the figure it refused"):
        RentaIncomeObservation.model_validate(
            {
                "transaction_id": "e7069cd081825298f943214257e7e4fe030860d44c74a04ca5ad380a498ff18d",
                "target_casilla_id": "01",
                "gross_amount": Decimal("1700.00"),
                "taxable_base_amount": Decimal("2000.00"),
                "withheld_amount": Decimal("300.00"),
                "withheld_derivation": LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE,
                "filing_date": date(2024, 3, 15),
                "grounding": LedgerIncomeGrounding.SUBSTRATE_DECLARED,
            },
        )


def test_the_builder_never_emits_an_unmarked_withholding() -> None:
    """Every figure the production path produces states how it was derived.

    The model default is permissive so an observation built without reference
    to this axis stays constructible; that concession is only safe because the
    builder itself never takes it. Each of these rows carries a withholding
    for a different reason, and none of them comes back unmarked.
    """
    rows = (
        _income_row(
            "builder-exempt",
            cash="1700.00",
            taxable_base="2000.00",
            iva_category=IvaCategory.DOMESTIC_EXEMPT,
        ),
        _income_row(
            "builder-rated",
            cash="2120.00",
            taxable_base="2000.00",
            iva_amount="420.00",
            iva_rate="0.21",
            iva_category=IvaCategory.DOMESTIC_GENERAL,
        ),
    )
    catalogue = TransactionCatalogue.from_transactions(rows)

    aggregation = aggregate_renta_income_ledger(
        catalogue,
        bucket_id="test",
        period=Period.from_year_and_code(2024, "1T"),
    )

    assert len(aggregation.observations) == len(rows)
    for observation in aggregation.observations:
        assert observation.withheld_amount > Decimal("0")
        assert observation.withheld_derivation is not LedgerWithholdingDerivation.NOT_APPLICABLE
