"""Application wire models refuse a code whose width the registry does not declare."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ....domain.calculations.registry.form_codes import resolve_form_codes_leased
from ...ledger.transaction_projection import LedgerM210IncomeProjection
from ...modelo.edit_apply_row_contracts import Modelo210AgrupacionRentaRowWireV1
from ...modelo.invoice_withholding_capture_public import PublicAnnualRecipientDetail
from ..irnr_income_ledger import IrnrIncomeLedgerAggregation, IrnrIncomeObservation
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TIPO_RENTA = "m210.tipo_renta_digits"


def _refused(model: type[BaseModel], field: str, value: object) -> bool:
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        return any(error["loc"][0] == field for error in exc.errors())
    return False


@pytest.mark.parametrize(
    ("model", "field", "key"),
    [
        (LedgerM210IncomeProjection, "official_tipo_renta_code", _TIPO_RENTA),
        (Modelo210AgrupacionRentaRowWireV1, "tipo_renta_code", _TIPO_RENTA),
        (IrnrIncomeObservation, "official_tipo_renta_code", _TIPO_RENTA),
        (IrnrIncomeLedgerAggregation, "selected_official_tipo_renta_code", _TIPO_RENTA),
        (CalculationSourceContext, "m210_official_tipo_renta_code", _TIPO_RENTA),
        (PublicAnnualRecipientDetail, "subclave", "withholding.subclave_max"),
        (PublicAnnualRecipientDetail, "codigo_emisor", "withholding.codigo_emisor_max"),
    ],
)
def test_a_code_past_the_declared_width_is_refused(model: type[BaseModel], field: str, key: str) -> None:
    limit = int(resolve_form_codes_leased("form-row-codes").code(key))
    assert not _refused(model, field, "1" * limit)
    assert _refused(model, field, "1" * (limit + 1))
