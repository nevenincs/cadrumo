"""The detail-row field map of a calculation snapshot carries only names the typed row models declare."""

from __future__ import annotations

from decimal import Decimal
from typing import get_args

import pytest
from pydantic import BaseModel

from ....domain.modelos.row_models import Modelo184MemberRow, Modelo349OperadorRow, ModeloDetailRow
from ..calculation_projection import ModeloCalculationDetailSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _member_row() -> Modelo184MemberRow:
    return Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000"), clave="D")


def _operator_row() -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="EU trader",
        clave_operacion="E",
        importe=Decimal("25.00"),
    )


@pytest.mark.parametrize("row", [_member_row(), _operator_row()], ids=["modelo-184-member", "modelo-349-operator"])
def test_projected_field_names_are_exactly_the_names_the_row_model_declares(row: ModeloDetailRow) -> None:
    snapshot = ModeloCalculationDetailSnapshot.from_row(3, row)

    declared = set(type(row).model_fields) - {"row_type"}
    assert snapshot.index == 3
    assert snapshot.row_type == row.row_type
    assert [field.key for field in snapshot.fields] == [name for name in type(row).model_fields if name in declared]
    assert {field.key for field in snapshot.fields} == declared


def test_projected_values_are_the_rows_own_values_with_absent_facts_left_absent() -> None:
    snapshot = ModeloCalculationDetailSnapshot.from_row(1, _member_row())

    values = {field.key: field.value for field in snapshot.fields}
    assert values["nif"] == "11111111A"
    assert values["clave"] == "D"
    assert values["subclave"] is None


def test_every_detail_row_model_forbids_extra_names_and_declares_no_computed_field() -> None:
    models = get_args(ModeloDetailRow)

    assert models
    for model in models:
        assert issubclass(model, BaseModel)
        assert model.model_config.get("extra") == "forbid", model.__name__
        assert not model.model_computed_fields, model.__name__
