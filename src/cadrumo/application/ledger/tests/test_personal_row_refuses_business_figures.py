"""A ledger write never leaves business figures on a personal row, and no reader serves them.

A person who names a figure for a personal row is refused with the registered
sentence; a write that changes a row's classification to personal drops the
figures the row carried. A personal row that still holds figures from before is
projected without them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import resolve_error_message
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.vehicle_use import IvaVehicleUse
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionFiguresWithoutBusinessError
from ....domain.transactions.models import Transaction
from ...aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from ..allocate_operation import LedgerAllocateRequest, allocation_patch
from ..ledger_add_command import prepare_ledger_add_command
from ..ledger_add_contracts import LedgerAddRequest
from ..ledger_add_results import build_ledger_add_validation_messages
from ..manual_read import ledger_transaction_payload
from ..manual_update import command_from_patch
from ..models import ManualLedgerTransactionPatch
from .ledger_input_rule_support import PROFILE

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = str(PROFILE)
_BOOKED = date(filing_year_envelope().horizon, 4, 15)


def _add_request(**values: str) -> LedgerAddRequest:
    return LedgerAddRequest.model_validate(
        {
            "profile_id": PROFILE,
            "booked_date": _BOOKED.isoformat(),
            "amount": "121.00",
            "direction": "OUTGOING",
            "description": "Supermarket",
            "business_classification": "PERSONAL",
            **values,
        },
    )


def _row(classification: BusinessClassification, **fields: object) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction("personal-figures", booked_date=_BOOKED, amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": classification,
            "classified_at": datetime(_BOOKED.year, 4, 16, 9, 0, tzinfo=UTC),
            "classified_by": "manual",
            **fields,
        }
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("category_id", "material_oficina"),
        ("taxable_base", "100.00"),
        ("iva_amount", "21.00"),
        ("irpf_category", "actividad_economica"),
        ("usage_ratio_id", "synthetic-ratio"),
    ],
)
def test_adding_a_personal_row_with_a_business_figure_is_refused_with_the_served_sentence(
    field: str, value: str, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(TransactionFiguresWithoutBusinessError) as refusal:
        prepare_ledger_add_command(_add_request(**{field: value}), operation, actor="operator")

    assert refusal.value.context is not None
    assert refusal.value.context["fields"] == field
    messages = build_ledger_add_validation_messages(refusal.value)
    assert messages == (resolve_error_message(refusal.value),)
    assert field not in messages[0]
    assert "errors.refused" not in messages[0]


def _allocation(share: str, **values: str) -> LedgerAllocateRequest:
    return LedgerAllocateRequest(profile_id=PROFILE, transaction_id="a" * 12, business_pct=share, **values)


def test_allocating_nothing_to_the_business_with_a_category_is_refused(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(TransactionFiguresWithoutBusinessError):
        allocation_patch(_allocation("0", category_id="material_oficina"), operation=operation)


def test_allocating_a_share_keeps_the_category_and_allocating_nothing_writes_a_personal_row(
    operation: PinnedAuthorityOperation,
) -> None:
    mixed = allocation_patch(_allocation("0.5", category_id="material_oficina"), operation=operation)
    personal = allocation_patch(_allocation("0"), operation=operation)

    assert mixed.business_classification is BusinessClassification.MIXED
    assert mixed.category_id == "material_oficina"
    assert personal.business_classification is BusinessClassification.PERSONAL
    assert "category_id" not in personal.model_fields_set


def test_reclassifying_a_business_row_as_personal_drops_every_business_figure() -> None:
    business = _row(
        BusinessClassification.BUSINESS,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        iva_vehicle_use=IvaVehicleUse.SURVEILLANCE,
        irpf_category="actividad_economica",
    )

    command = command_from_patch(
        bucket_id=_BUCKET,
        current=business,
        patch=ManualLedgerTransactionPatch.model_validate({"business_classification": BusinessClassification.PERSONAL}),
        actor="operator",
        source_command="aeat app ledger classify",
    )

    assert command.business_classification is BusinessClassification.PERSONAL
    assert command.category_id is None
    assert command.taxable_base is None
    assert command.iva_rate is None
    assert command.iva_amount is None
    assert command.iva_vehicle_use is None
    assert command.irpf_category is None


def test_naming_a_category_for_a_personal_row_without_reclassifying_it_is_refused() -> None:
    personal = _row(BusinessClassification.PERSONAL)

    with pytest.raises(ValidationError) as caught:
        command_from_patch(
            bucket_id=_BUCKET,
            current=personal,
            patch=ManualLedgerTransactionPatch.model_validate({"category_id": "material_oficina"}),
            actor="operator",
            source_command="aeat app ledger update",
        )

    translated = caught.value.errors()[0].get("ctx", {}).get("error")
    assert isinstance(translated, BaseException)
    assert isinstance(translated.__cause__, TransactionFiguresWithoutBusinessError)


def test_a_personal_row_still_holding_figures_is_projected_without_them() -> None:
    held = _row(BusinessClassification.PERSONAL).model_copy(
        update={
            "category_id": "material_oficina",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "irpf_category": "actividad_economica",
        }
    )

    payload = ledger_transaction_payload(held)

    assert payload.business_classification == "PERSONAL"
    assert payload.category_id is None
    assert payload.taxable_base is None
    assert payload.iva_rate is None
    assert payload.iva_amount is None
    assert payload.irpf_category is None
    assert payload.transaction_id == held.transaction_id
    assert payload.amount == "121"


def test_a_business_row_is_projected_with_its_figures() -> None:
    business = _row(BusinessClassification.BUSINESS, category_id="material_oficina", taxable_base=Decimal("100.00"))

    payload = ledger_transaction_payload(business)

    assert payload.category_id == "material_oficina"
    assert payload.taxable_base == "100"
