"""Hardening coverage for calc-sheets record validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .....core import CasillaId, Period, validated_casilla_id
from cadrumo.domain.calculations.registry.ids import LegalRefId
from ..errors import CalcSheetsRecordError
from .._records import (
    OperatorInput,
    OperatorInputs,
    SheetCellAddress,
    SheetCellConstraint,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetValueCell,
    TabName,
    column_letters_to_index,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IVA_DEVENGADO_BASE_CASILLA: CasillaId = validated_casilla_id(
    "iva.devengado.base",
    surface="_IVA_DEVENGADO_BASE_CASILLA",
)
_VALID_LEGAL_REF: LegalRefId = "ley-37-1992:art-99"


def _metadata() -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id="303",
        revision_id="2022",
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
        column_letters_to_index(sensitive_letters)

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


def test_operator_inputs_are_keyed_by_canonical_casilla_id() -> None:
    operator_input = OperatorInput(casilla_id=_IVA_DEVENGADO_BASE_CASILLA, value="100.00")
    inputs = OperatorInputs(values=(operator_input,))

    assert inputs.by_casilla_id() == {_IVA_DEVENGADO_BASE_CASILLA: operator_input}


def test_operator_input_rejects_generic_casilla_key() -> None:
    with pytest.raises(ValidationError):
        OperatorInput.model_validate(
            {
                "casilla": _IVA_DEVENGADO_BASE_CASILLA,
                "value": "100.00",
            },
        )


def test_sheet_plan_records_reject_generic_casilla_key() -> None:
    value_address = SheetCellAddress.at(TabName.ENTRADAS, row=2, column=4)
    formula_address = SheetCellAddress.at(TabName.CALCULOS, row=2, column=4)

    with pytest.raises(ValidationError):
        SheetValueCell.model_validate(
            {
                "address": value_address,
                "value": "100.00",
                "role": "operator_input",
                "casilla": _IVA_DEVENGADO_BASE_CASILLA,
            },
        )
    with pytest.raises(ValidationError):
        SheetFormulaCell.model_validate(
            {
                "address": formula_address,
                "formula": "'Entradas'!D2*0.21",
                "rounding_rule": "money",
                "casilla": _IVA_DEVENGADO_BASE_CASILLA,
            },
        )
    with pytest.raises(ValidationError):
        SheetCellConstraint.model_validate(
            {
                "address": value_address,
                "sign": "non_negative",
                "legal_refs": (_VALID_LEGAL_REF,),
                "casilla": _IVA_DEVENGADO_BASE_CASILLA,
            },
        )
    with pytest.raises(ValidationError):
        SheetNumberFormat.model_validate(
            {
                "address": formula_address,
                "data_type": "money",
                "pattern": "#,##0.00",
                "casilla": _IVA_DEVENGADO_BASE_CASILLA,
            },
        )


def test_sheet_cell_constraint_rejects_blank_legal_ref() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        SheetCellConstraint(
            address=SheetCellAddress.at(TabName.ENTRADAS, row=2, column=4),
            sign="non_negative",
            legal_refs=(" ",),
            casilla_id=_IVA_DEVENGADO_BASE_CASILLA,
        )


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
                    casilla_id=_IVA_DEVENGADO_BASE_CASILLA,
                ),
            ),
            formula_cells=(
                SheetFormulaCell(
                    address=address,
                    formula="A1+B1",
                    casilla_id=_IVA_DEVENGADO_BASE_CASILLA,
                    rounding_rule="money",
                ),
            ),
        )

    error = _record_error_from(raised.value)
    assert str(error) == "sheet export plan writes more than one payload to the same cell address"
    assert error.context == {"duplicate_count": 1}
    assert error.translated_message == "application.storage.calc_sheets.records.errors.duplicate_write_address"
