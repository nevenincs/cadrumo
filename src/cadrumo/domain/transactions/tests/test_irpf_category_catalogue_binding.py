"""The gross-invariant relaxation is bound to the closed ledger IRPF catalogue.

``has_non_work_irpf_category`` used to accept any non-empty token other than
``trabajo``, so a row tagged with an invented withholding axis kept an invoice
substrate above its cash movement while no aggregator produced any withholding
for the tag. The predicates now resolve through the closed catalogue and honour
each descriptor's declared directions, so an unrecognised token -- or a
paid-only rent treatment claimed on a received row -- no longer unlocks the
relaxation and the row is refused by the gross invariant.

``irpf_category`` also legitimately carries Renta income-type tags, a separate
classification axis with no withholding treatment. Those must keep validating:
the contract here is "no withholding relaxation", not "no such token".

Real model construction, no mocks.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..enums import TransactionDirection
from ..irpf_categories import (
    IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
    IRPF_CATEGORY_TRABAJO,
    has_activity_irpf_category,
    has_non_work_irpf_category,
    has_rent_irpf_category,
    ledger_irpf_category,
    ledger_irpf_category_ids,
)
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
_RENT_CATEGORY = "arrendamiento_local"
# A Renta income-type tag: a different classification axis carried in the same
# field, with no withholding treatment and therefore no relaxation.
_RENTA_INCOME_TAG = "actividades_economicas_directa_simplificada"


def _raw(*, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id="row-irpf-catalogue",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=amount,
        currency="EUR",
        counterparty="Contraparte SL",
        description="Factura",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Factura"},
    )


def _transaction(
    *,
    amount: Decimal,
    direction: TransactionDirection,
    irpf_category: str | None,
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(amount=amount),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "irpf_category": irpf_category,
            "taxable_base": taxable_base,
            "iva_amount": iva_amount,
        },
    )


def test_unknown_token_does_not_unlock_the_withholding_relaxation() -> None:
    """An invented axis must not keep a substrate above the cash movement.

    The probe row: 2120.00 received against a declared 2000.00 + 420.00
    invoice. Only a catalogued net-paid treatment may reconcile that gap.
    """
    with pytest.raises(ValidationError) as excinfo:
        _transaction(
            amount=Decimal("2120.00"),
            direction=TransactionDirection.INCOMING,
            irpf_category="bogus_withholding",
            taxable_base=Decimal("2000.00"),
            iva_amount=Decimal("420.00"),
        )

    assert "must equal the gross to the cent" in str(excinfo.value)


def test_outgoing_only_rent_treatment_does_not_relax_an_incoming_row() -> None:
    """Rent withholding is paid, never received; the descriptor says so."""
    with pytest.raises(ValidationError) as excinfo:
        _transaction(
            amount=Decimal("2120.00"),
            direction=TransactionDirection.INCOMING,
            irpf_category=_RENT_CATEGORY,
            taxable_base=Decimal("2000.00"),
            iva_amount=Decimal("420.00"),
        )

    assert "must equal the gross to the cent" in str(excinfo.value)


def test_renta_income_tag_does_not_unlock_the_relaxation() -> None:
    """A Renta income-type tag classifies the branch; it withholds nothing."""
    with pytest.raises(ValidationError):
        _transaction(
            amount=Decimal("2120.00"),
            direction=TransactionDirection.INCOMING,
            irpf_category=_RENTA_INCOME_TAG,
            taxable_base=Decimal("2000.00"),
            iva_amount=Decimal("420.00"),
        )


def test_renta_income_tag_still_validates_on_a_consistent_row() -> None:
    """The relaxation is withheld from the tag, but the tag itself stays valid."""
    transaction = _transaction(
        amount=Decimal("121.00"),
        direction=TransactionDirection.OUTGOING,
        irpf_category=_RENTA_INCOME_TAG,
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )

    assert transaction.irpf_category == _RENTA_INCOME_TAG


def test_activity_withholding_above_the_supported_rate_stays_refused() -> None:
    """The rate cap still bounds the relaxation the catalogued axis unlocks.

    An incoming row whose declared substrate exceeds the cash movement by more
    than the supported activity withholding rate is a base-without-IVA cash
    figure, not a net-of-withholding receipt.
    """
    with pytest.raises(ValidationError) as excinfo:
        _transaction(
            amount=Decimal("1000.00"),
            direction=TransactionDirection.INCOMING,
            irpf_category=IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
            taxable_base=Decimal("2000.00"),
            iva_amount=Decimal("420.00"),
        )

    assert "exceeds supported activity rate" in str(excinfo.value)


def test_catalogued_axis_on_its_declared_direction_is_accepted() -> None:
    """Valid parity: the activity axis relaxes an incoming net-of-withholding receipt."""
    transaction = _transaction(
        amount=Decimal("2120.00"),
        direction=TransactionDirection.INCOMING,
        irpf_category=IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
        taxable_base=Decimal("2000.00"),
        iva_amount=Decimal("420.00"),
    )

    assert transaction.irpf_category == IRPF_CATEGORY_ACTIVIDAD_ECONOMICA
    assert transaction.taxable_base == Decimal("2000.00")
    assert transaction.iva_amount == Decimal("420.00")


def test_predicates_resolve_through_the_closed_catalogue_with_direction() -> None:
    """The withholding predicates are catalogue lookups, not string comparisons."""
    incoming = TransactionDirection.INCOMING
    outgoing = TransactionDirection.OUTGOING

    assert has_non_work_irpf_category(IRPF_CATEGORY_ACTIVIDAD_ECONOMICA, direction=incoming) is True
    assert has_non_work_irpf_category(_RENT_CATEGORY, direction=outgoing) is True
    assert has_non_work_irpf_category(_RENT_CATEGORY, direction=incoming) is False
    assert has_non_work_irpf_category(IRPF_CATEGORY_TRABAJO, direction=incoming) is False
    assert has_non_work_irpf_category("bogus_withholding", direction=incoming) is False
    assert has_non_work_irpf_category(_RENTA_INCOME_TAG, direction=incoming) is False
    assert has_non_work_irpf_category(None, direction=incoming) is False

    assert has_activity_irpf_category(IRPF_CATEGORY_ACTIVIDAD_ECONOMICA, direction=outgoing) is True
    assert has_activity_irpf_category(_RENT_CATEGORY, direction=outgoing) is False
    assert has_rent_irpf_category(_RENT_CATEGORY, direction=outgoing) is True
    assert has_rent_irpf_category(_RENT_CATEGORY, direction=incoming) is False
    assert has_rent_irpf_category(IRPF_CATEGORY_ACTIVIDAD_ECONOMICA, direction=outgoing) is False


def test_catalogue_membership_is_closed_and_direction_aware() -> None:
    """Resolution answers both "is this catalogued" and "for this direction"."""
    accepted = ledger_irpf_category_ids()

    assert set(accepted) == {
        IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
        IRPF_CATEGORY_TRABAJO,
        _RENT_CATEGORY,
        "arrendamiento_vivienda_afecto",
    }

    assert ledger_irpf_category("bogus_withholding") is None
    assert ledger_irpf_category(_RENTA_INCOME_TAG) is None
    assert ledger_irpf_category(None) is None

    trabajo = ledger_irpf_category(IRPF_CATEGORY_TRABAJO)
    assert trabajo is not None
    assert trabajo.directions == (TransactionDirection.INCOMING,)
    assert ledger_irpf_category(IRPF_CATEGORY_TRABAJO, direction=TransactionDirection.OUTGOING) is None
