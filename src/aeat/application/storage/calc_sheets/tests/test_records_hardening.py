"""Hardening coverage for calc-sheets record validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .....core import Period
from .._errors import CalcSheetsRecordError
from .._records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetProtectedRange,
    SheetValueCell,
    TabName,
    _column_letters_to_index,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _metadata() -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id="303",
        revision_id="2009-y-siguientes",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        engine_version="test",
        registry_sha="abcd1234",
        exported_at=datetime(2026, 6, 4, 12, 0, tzinfo=UTC),
    )


def _guide() -> SheetGuideContent:
    return SheetGuideContent(title="Modelo 303", paragraphs=("Use Entradas.",))


def _record_error_from(validation_error: ValidationError) -> CalcSheetsRecordError:
    ctx_error = validation_error.errors(include_input=False)[0].get("ctx", {}).get("error")
    assert isinstance(ctx_error, CalcSheetsRecordError)
    return ctx_error


def test_invalid_column_letters_raise_typed_record_error_without_raw_value() -> None:
    sensitive_letters = "PRIVATE_TOKEN"

    with pytest.raises(CalcSheetsRecordError) as raised:
        _column_letters_to_index(sensitive_letters)

    error = raised.value
    assert str(error) == "invalid Sheets column letters"
    assert sensitive_letters not in str(error)
    assert sensitive_letters not in str(error.context)
    assert error.context == {"letters_length": len(sensitive_letters)}
    assert error.translated_message == "application.storage.calc_sheets.records.errors.invalid_column_letters"


def test_a1_mismatch_validator_uses_typed_record_error_without_raw_a1() -> None:
    sensitive_a1 = "PRIVATE99"

    with pytest.raises(ValidationError) as raised:
        SheetCellAddress(tab=TabName.ENTRADAS, row=1, column=1, a1=sensitive_a1)

    error = _record_error_from(raised.value)
    assert str(error) == "sheet cell A1 address does not match row and column"
    assert sensitive_a1 not in str(error)
    assert sensitive_a1 not in str(error.context)
    assert error.context == {"row": 1, "column": 1}
    assert error.translated_message == "application.storage.calc_sheets.records.errors.address_mismatch"


def test_malformed_protected_range_validator_uses_typed_record_error() -> None:
    with pytest.raises(ValidationError) as raised:
        SheetProtectedRange(
            tab=TabName.CALCULOS,
            start_row=5,
            end_row=4,
            start_column=1,
            end_column=1,
            description="protected",
        )

    error = _record_error_from(raised.value)
    assert str(error) == "range end row must be on or after start row"
    assert error.context == {"range_kind": "protected"}
    assert error.translated_message == "application.storage.calc_sheets.records.errors.range_malformed"


def test_export_plan_rejects_duplicate_writable_cell_addresses() -> None:
    address = SheetCellAddress.at(TabName.ENTRADAS, row=2, column=3)

    with pytest.raises(ValidationError) as raised:
        SheetExportPlan(
            metadata=_metadata(),
            guide=_guide(),
            value_cells=(
                SheetValueCell(
                    address=address,
                    value="operator value",
                    role="operator_input",
                    casilla="iva.devengado.base",
                ),
            ),
            formula_cells=(
                SheetFormulaCell(
                    address=address,
                    formula="A1+B1",
                    casilla="iva.devengado.base",
                    rounding_rule="money",
                ),
            ),
        )

    error = _record_error_from(raised.value)
    assert str(error) == "sheet export plan writes more than one payload to the same cell address"
    assert error.context == {"duplicate_count": 1}
    assert error.translated_message == "application.storage.calc_sheets.records.errors.duplicate_write_address"
