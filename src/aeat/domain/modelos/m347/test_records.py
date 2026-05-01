"""Tests for Modelo 347 strict detail records."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from . import MANIFEST_2024, MANIFEST_2025, MANIFEST_2026, ClaveOperacion, Modelo347RecordLine

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _record(**overrides: object) -> Modelo347RecordLine:
    values: dict[str, object] = {
        "declared_tax_id": "b12345678",
        "declared_name": "  Cliente   Uno SL ",
        "operation_key": ClaveOperacion.B,
        "annual_operation_amount": Decimal("12000.00"),
        "first_quarter_amount": Decimal("3000.00"),
        "second_quarter_amount": Decimal("3000.00"),
        "third_quarter_amount": Decimal("3000.00"),
        "fourth_quarter_amount": Decimal("3000.00"),
    }
    values.update(overrides)
    return Modelo347RecordLine.model_validate(values)


def test_record_is_strict_frozen_and_normalised() -> None:
    record = _record()
    assert record.declared_tax_id == "B12345678"
    assert record.declared_name == "Cliente Uno SL"
    with pytest.raises(ValidationError):
        Modelo347RecordLine.model_validate(
            {
                "declared_tax_id": "B12345678",
                "declared_name": "Cliente Uno SL",
                "operation_key": "Z",
                "annual_operation_amount": Decimal("12000.00"),
            }
        )


def test_blank_identity_rejected_after_normalisation() -> None:
    with pytest.raises(ValidationError, match="tax identifiers"):
        _record(declared_tax_id="   ")
    with pytest.raises(ValidationError, match="declared_name"):
        _record(declared_name="   ")


def test_quarter_sum_must_match_annual_amount() -> None:
    with pytest.raises(ValidationError, match="quarterly amounts"):
        _record(fourth_quarter_amount=Decimal("2999.98"))


def test_cash_origin_year_required_for_cash_amount() -> None:
    with pytest.raises(ValidationError, match="cash_origin_year"):
        _record(cash_received_amount=Decimal("6001.00"))
    assert _record(cash_received_amount=Decimal("6001.00"), cash_origin_year=2025).cash_origin_year == 2025


def test_boe_optional_fields_are_preserved() -> None:
    record = _record(
        declarant_tax_id="00000000t",
        ejercicio=2025,
        declared_tax_id=None,
        eu_vat_operator_id="DE123456789",
        cash_accounting_iva=True,
        reverse_charge_operation=True,
        non_customs_deposit_operation=True,
        cash_accounting_annual_amount=Decimal("12000.00"),
        first_quarter_real_estate_transmission_amount=Decimal("100.00"),
        second_quarter_real_estate_transmission_amount=Decimal("200.00"),
        third_quarter_real_estate_transmission_amount=Decimal("300.00"),
        fourth_quarter_real_estate_transmission_amount=Decimal("400.00"),
    )
    assert record.declarant_tax_id == "00000000T"
    assert record.eu_vat_operator_id == "DE123456789"
    assert record.cash_accounting_iva is True
    assert record.fourth_quarter_real_estate_transmission_amount == Decimal("400.00")


def test_bdns_required_for_public_subsidy_operation_key() -> None:
    with pytest.raises(ValidationError, match="bdns_call_number"):
        _record(operation_key=ClaveOperacion.E)
    assert _record(operation_key=ClaveOperacion.E, bdns_call_number="123456").bdns_call_number == "123456"


def test_per_year_manifests_are_explicit_and_same_schema() -> None:
    assert [m.ejercicio for m in (MANIFEST_2024, MANIFEST_2025, MANIFEST_2026)] == [2024, 2025, 2026]
    assert MANIFEST_2024.threshold_amount == Decimal("3005.06")
    assert MANIFEST_2024.record_fields == MANIFEST_2025.record_fields == MANIFEST_2026.record_fields
    assert MANIFEST_2024.operation_keys == tuple(ClaveOperacion)
