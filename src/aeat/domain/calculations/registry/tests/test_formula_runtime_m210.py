"""M210 formula-runtime contract tests."""

from __future__ import annotations

import pytest

from .....core.resources import resources
from .._errors import RegistryValidationError
from .._formula_runtime import _m210_resolve_rate_args
from .._schema import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M210_RATE_FORMULA_ID = "m210-tipo-gravamen-2025-resolve"
_M210_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"


def _current_m210_rate_expression() -> FormulaExpression:
    revision = resources().modelos.authority.snapshot("210", filing_year=2025, period="EVENT-1").revision
    return next(formula.expression for formula in revision.formulas if formula.id == _M210_RATE_FORMULA_ID)


def test_m210_resolve_rate_args_accepts_current_six_arg_contract() -> None:
    args = _m210_resolve_rate_args(_current_m210_rate_expression())

    assert args.tipo_casilla_id == "tipo_renta"
    assert args.base_casilla_id == "base_imponible"
    assert args.baseline_parameter == "m210-tipo-gravamen-2025"
    assert args.convenio_parameter == "m210-convenio-rates"
    assert args.pension_tariff_parameter == "m210-pension-tarifa-2025"
    assert args.country_binding == _M210_COUNTRY_BINDING


def test_m210_resolve_rate_args_rejects_retired_four_arg_contract() -> None:
    retired_expression = FormulaExpression.model_validate(
        {
            "op": "m210_resolve_rate",
            "args": (
                {"casilla_id": "tipo_renta"},
                {"parameter": "m210-tipo-gravamen-2025"},
                {"parameter": "m210-convenio-rates"},
                {"binding": _M210_COUNTRY_BINDING},
            ),
        }
    )

    with pytest.raises(RegistryValidationError, match=r"expects 6 args, got 4"):
        _m210_resolve_rate_args(retired_expression)
