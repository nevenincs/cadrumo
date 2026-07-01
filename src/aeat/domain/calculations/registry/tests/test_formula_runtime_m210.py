"""M210 / IRNR formula-runtime contract tests."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._formula_runtime import _irnr_resolve_tipo_gravamen_args
from .._loader import load_registry_tree
from .._schema import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M210_RATE_FORMULA_ID = "m210-tipo-gravamen-2025-resolve"
_M210_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"


def _current_m210_rate_expression() -> FormulaExpression:
    # Compile-only load (no full-registry validation) so the M210 rate-formula
    # shape assertion is independent of unrelated peer modelo churn.
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    revision = next(modelo for modelo in modelos if modelo.id == "210").revisions["2025"]
    return next(formula.expression for formula in revision.formulas if formula.id == _M210_RATE_FORMULA_ID)


def test_irnr_resolve_tipo_gravamen_args_accepts_current_five_arg_contract() -> None:
    args = _irnr_resolve_tipo_gravamen_args(_current_m210_rate_expression())

    assert args.tipo_casilla_id == "tipo_renta"
    assert args.base_casilla_id == "base_imponible"
    assert args.baseline_parameter == "m210-tipo-gravamen-2025"
    assert args.pension_tariff_parameter == "m210-pension-tarifa-2025"
    assert args.country_binding == _M210_COUNTRY_BINDING


def test_irnr_resolve_tipo_gravamen_args_rejects_retired_convenio_parameter_contract() -> None:
    # The retired six-arg contract carried an M210-local convenio-rates parameter
    # leaf at args[3]; the generalised op reads treaty overrides from the
    # ConvenioAuthority snapshot projection instead, so the arg count is now 5.
    retired_expression = FormulaExpression.model_validate(
        {
            "op": "irnr_resolve_tipo_gravamen",
            "args": (
                {"casilla_id": "tipo_renta"},
                {"casilla_id": "base_imponible"},
                {"parameter": "m210-tipo-gravamen-2025"},
                {"parameter": "m210-convenio-rates"},
                {"parameter": "m210-pension-tarifa-2025"},
                {"binding": _M210_COUNTRY_BINDING},
            ),
        }
    )

    with pytest.raises(RegistryValidationError, match=r"expects 5 args, got 6"):
        _irnr_resolve_tipo_gravamen_args(retired_expression)
