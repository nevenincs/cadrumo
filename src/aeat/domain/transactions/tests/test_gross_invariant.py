"""Real-behavior tests for the ``gross == taxable_base + iva_amount`` invariant.

The :class:`aeat.domain.transactions.Transaction` model enforces, to the euro
cent, that a populated tax substrate reconstitutes the IVA-inclusive gross —
but only when **both** ``taxable_base`` and ``iva_amount`` are present. Rows
with an unset tax substrate (the common case) must validate unconditionally.

Authority: LLM ledger classification contract.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _raw(*, amount: Decimal, currency: str = "EUR") -> RawTransaction:
    return RawTransaction(
        transaction_id="row-invariant",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=amount,
        currency=currency,
        counterparty="Contraparte SL",
        description="Compra",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Compra"},
    )


def test_all_none_tax_substrate_validates() -> None:
    """A row with no tax substrate set must validate (the common case)."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
        },
    )
    assert tx.taxable_base is None
    assert tx.iva_amount is None


def test_consistent_triple_validates_against_magnitude_gross() -> None:
    """base + iva == gross magnitude to the cent is accepted (amount is non-negative)."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
        },
    )
    assert tx.taxable_base == Decimal("100.00")
    assert tx.iva_amount == Decimal("21.00")


def test_professional_income_net_of_irpf_withholding_validates() -> None:
    """Professional income can keep invoice base/IVA when the bank receipt is net.

    A Spanish professional invoice for 2000.00 + 420.00 IVA with 300.00 IRPF
    withheld lands as a 2120.00 bank receipt. The ledger must preserve the
    invoice substrate so IVA and Renta aggregations can read the declared base
    and cuota instead of losing those facts.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("2120.00")),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("2000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("420.00"),
            "irpf_category": "actividad_economica",
        },
    )

    assert tx.raw.amount == Decimal("2120.00")
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("2420.00")
    assert tx.taxable_base + tx.iva_amount > tx.raw.amount


def test_professional_service_expense_paid_net_of_irpf_withholding_validates() -> None:
    """A paid professional invoice can keep the supplier invoice base/IVA.

    Javier repro: 1000.00 base + 210.00 IVA with 150.00 IRPF withheld is paid
    as a 1060.00 bank movement. The cash amount must stay net while the row
    preserves the full invoice substrate for IVA and expense aggregation.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("1060.00")),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "asesoria_fiscal",
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "irpf_category": "actividad_economica",
        },
    )

    assert tx.raw.amount == Decimal("1060.00")
    assert tx.category_id == "asesoria_fiscal"
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("1210.00")
    assert tx.taxable_base + tx.iva_amount > tx.raw.amount


def test_activity_income_base_cash_is_not_inferred_as_iva_sized_withholding() -> None:
    """A base-only cash receipt plus IVA must not become a fake M130 retention.

    Persona repro: a professional enters a 2000.00 invoice base as the bank
    movement amount and also records 420.00 IVA. That 420.00 delta is IVA-sized
    and must not be accepted as IRPF withholding for casilla 06.
    """
    with pytest.raises(ValidationError, match="inferred IRPF withholding exceeds"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2000.00")),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_professional_service_base_cash_is_not_inferred_as_iva_sized_withholding() -> None:
    """Paid professional-service cash equal to base must not become retencion."""
    with pytest.raises(ValidationError, match="inferred IRPF withholding exceeds"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1000.00")),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "asesoria_fiscal",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_rent_expense_paid_net_of_withholding_validates() -> None:
    """Rent paid net of withholding keeps the supplier invoice base/IVA.

    Persona repro: local rent invoice 1000.00 + 210.00 IVA with 190.00
    withholding is paid as a 1020.00 bank movement. Modelo 303 still needs
    the full 210.00 IVA soportado substrate, so the ledger must not force the
    bank cash amount to equal base + IVA for this scoped rent withholding case.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("1020.00")),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "arrendamiento_local",
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "irpf_category": "arrendamiento_local",
        },
    )

    assert tx.raw.amount == Decimal("1020.00")
    assert tx.category_id == "arrendamiento_local"
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("1210.00")
    assert tx.taxable_base + tx.iva_amount > tx.raw.amount


def test_rent_expense_paid_net_requires_irpf_category() -> None:
    """Rent expense net-cash relaxation requires an explicit withholding axis."""
    with pytest.raises(ValidationError, match="set irpf_category"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "arrendamiento_local",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
            },
        )


def test_rent_expense_paid_net_requires_rental_irpf_category() -> None:
    """An unrelated non-work IRPF tag must not relax outgoing rent gross drift."""
    with pytest.raises(ValidationError, match="rental withholding category"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "arrendamiento_local",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_outgoing_irpf_category_does_not_relax_non_rent_expense_gross() -> None:
    """IRPF tags alone must not unlock arbitrary outgoing invoice-gross drift."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "material_oficina",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "arrendamiento_local",
            },
        )


def test_activity_irpf_category_does_not_relax_non_professional_expense_gross() -> None:
    """actividad_economica is scoped to professional-service expense categories."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "material_oficina",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_invoice_gross_above_cash_without_irpf_category_is_rejected() -> None:
    """The net-cash relaxation requires an explicit IRPF category."""
    with pytest.raises(ValidationError, match="set irpf_category"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2120.00")),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
            },
        )


def test_work_irpf_category_does_not_relax_professional_invoice_gross() -> None:
    """Salary/work tags must not unlock invoice-gross validation."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2120.00")),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
                "irpf_category": "trabajo",
            },
        )


def test_irpf_category_does_not_accept_understated_invoice_gross() -> None:
    """Withholding may explain cash below invoice gross, never invoice gross below cash."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2420.00")),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("300.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_drifted_triple_is_rejected() -> None:
    """A triple that does not reconstitute the gross raises ValidationError."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("121.00")),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("100.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("25.00"),
            },
        )


def test_base_present_but_iva_absent_validates() -> None:
    """The invariant fires only when both fields are present; base-only is fine."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
        },
    )
    assert tx.taxable_base == Decimal("100.00")
    assert tx.iva_amount is None


def test_invariant_uses_native_raw_amount_not_value_in_eur() -> None:
    """For a non-EUR row the gross reference is the native raw.amount.

    The tax substrate (taxable_base / iva_amount) is denominated in the
    row's native currency; the aggregation layer carries value_in_eur as a
    separate parallel EUR projection and does not apply fx_rate to the
    base or amount. So the invariant reconstitutes the native 100.00, not
    the 110.00 EUR conversion.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("100.00"), currency="USD"),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "fx_rate": Decimal("1.10"),
            "value_in_eur": Decimal("110.00"),
            "rate_source": "ecb_reference",
            "rate_date": "2025-02-10",
            "taxable_base": Decimal("82.64"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("17.36"),
        },
    )
    assert tx.value_in_eur == Decimal("110.00")
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("100.00")


def test_invariant_against_native_amount_rejects_eur_split() -> None:
    """A triple splitting the EUR value (not the native amount) is rejected."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("100.00"), currency="USD"),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "fx_rate": Decimal("1.10"),
                "value_in_eur": Decimal("110.00"),
                "rate_source": "ecb_reference",
                "rate_date": "2025-02-10",
                # Splits the 110.00 EUR value, not the 100.00 native gross.
                "taxable_base": Decimal("90.91"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("19.09"),
            },
        )
