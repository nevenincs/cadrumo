"""M210 / IRNR formula-runtime contract tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._formula_runtime_irnr import _irnr_resolve_tipo_gravamen_args
from ..convenio import load_convenio_authority
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason, resolve_keyed_bracket
from ..loader import load_registry_tree
from ..schema import RegistrySnapshot
from ..schema_formula import FormulaExpression
from ..snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M210_RATE_FORMULA_ID = "m210-tipo-gravamen-2025-resolve"
_M210_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"
_M210_TIPO_RENTA_CASILLA = "tipo_renta"
_M210_RENDIMIENTOS_INTEGROS_CASILLA = "rendimientos_integros"
_M210_GASTOS_DEDUCIBLES_CASILLA = "gastos_deducibles"
_M210_RETENCION_PRACTICADA_CASILLA = "retencion_practicada"
_M210_TIPO_GRAVAMEN_CASILLA = "tipo_gravamen"


def _current_m210_rate_expression() -> FormulaExpression:
    # Compile-only load (no full-registry validation) so the M210 rate-formula
    # shape assertion is independent of unrelated peer modelo churn.
    modelos, _catalogues = bundled_registry_tree()
    revision = next(modelo for modelo in modelos if modelo.id == "210").revisions["2025"]
    return next(formula.expression for formula in revision.formulas if formula.id == _M210_RATE_FORMULA_ID)


def _current_m210_snapshot() -> RegistrySnapshot:
    root = bundled_path("registry", "aeat")
    modelos, catalogues = load_registry_tree(root)
    catalogues = catalogues.model_copy(update={"convenio": load_convenio_authority(root / "treaties")})
    modelo = next(modelo for modelo in modelos if modelo.id == "210")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="EVENT-1")


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
    #
    # FormulaExpression.model_validate() now enforces op arity centrally
    # (require_formula_operator_arity, at construction), so a 6-arg expression
    # can no longer reach this resolver's own arity check via normal
    # validation. model_construct() bypasses that model-level validator to
    # exercise this function's defense-in-depth check directly.
    retired_expression = FormulaExpression.model_construct(
        op="irnr_resolve_tipo_gravamen",
        args=(
            FormulaExpression.model_validate({"casilla_id": "tipo_renta"}),
            FormulaExpression.model_validate({"casilla_id": "base_imponible"}),
            FormulaExpression.model_validate({"parameter": "m210-tipo-gravamen-2025"}),
            FormulaExpression.model_validate({"parameter": "m210-convenio-rates"}),
            FormulaExpression.model_validate({"parameter": "m210-pension-tarifa-2025"}),
            FormulaExpression.model_validate({"binding": _M210_COUNTRY_BINDING}),
        ),
    )

    with pytest.raises(RegistryValidationError, match=r"expects 5 args, got 6"):
        _irnr_resolve_tipo_gravamen_args(retired_expression)


def test_irnr_resolve_tipo_gravamen_reports_unresolved_rate_as_typed_outcome() -> None:
    snapshot = _current_m210_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M210_RENDIMIENTOS_INTEGROS_CASILLA: Decimal("12000"),
            _M210_GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _M210_RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        enum_binding_values={_M210_COUNTRY_BINDING: "ZW"},
        text_inputs={_M210_TIPO_RENTA_CASILLA: "general"},
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert _M210_TIPO_GRAVAMEN_CASILLA not in result.values
    assert all(value not in {Decimal("-1"), Decimal("-2")} for value in result.values.values())
    assert len(result.unresolved_outcomes) == 1
    outcome = result.unresolved_outcomes[0]
    assert outcome.casilla_id == _M210_TIPO_GRAVAMEN_CASILLA
    assert outcome.reason is RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING
    assert outcome.formula_id == _M210_RATE_FORMULA_ID
    assert outcome.operand_refs == (
        _M210_TIPO_RENTA_CASILLA,
        "m210-tipo-gravamen-2025",
        _M210_COUNTRY_BINDING,
    )
    assert outcome.operand_casilla_refs == (_M210_TIPO_RENTA_CASILLA,)
    assert outcome.legal_refs
    assert outcome.source_refs
    assert outcome.context["tipo_renta"] == "general"
    assert outcome.context["country"] == "ZW"


def test_irnr_resolve_tipo_gravamen_resolves_dividend_baseline_rate() -> None:
    """Art. 25.1.f.1º dividends resolve the unconditional 19% baseline, not a blocking refusal.

    Before the ``dividend`` tipo_renta category was added to the registry
    baseline table, a non-resident with Spanish-source dividend income (a
    routine M210 category) had no matching bracket row and hit the
    fail-closed ``m210-baseline-tipo-deferred`` unresolved outcome. This
    proves the engine now computes the rate directly with no treaty
    country declared (the baseline branch), producing a real
    ``tipo_gravamen`` value rather than an ``unresolved_outcomes`` entry.
    """
    snapshot = _current_m210_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M210_RENDIMIENTOS_INTEGROS_CASILLA: Decimal("1000"),
            _M210_GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _M210_RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        enum_binding_values={},
        text_inputs={_M210_TIPO_RENTA_CASILLA: "dividend"},
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert result.unresolved_outcomes == ()
    assert result.values[_M210_TIPO_GRAVAMEN_CASILLA] == Decimal("0.19")
    assert result.values["cuota_integra"] == Decimal("190.00")


def test_keyed_bracket_resolution_rejects_overlapping_official_m210_rate_windows() -> None:
    """A contradictory rate row must not silently replace Art. 25.1.f's 19% dividend rate."""
    snapshot = _current_m210_snapshot()
    parameter = next(
        parameter for parameter in snapshot.revision.parameters if parameter.id == "m210-tipo-gravamen-2025"
    )
    dividend = next(entry for entry in parameter.keyed_brackets if entry.key == "dividend")

    assert resolve_keyed_bracket(parameter, key="dividend", filing_year=2025) == Decimal("0.19")

    overlapping = parameter.model_copy(
        update={
            "keyed_brackets": (
                *parameter.keyed_brackets,
                dividend.model_copy(update={"value": Decimal("0.24"), "valid_from": date(2025, 6, 1)}),
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="expected exactly one keyed bracket") as exc_info:
        resolve_keyed_bracket(overlapping, key="dividend", filing_year=2025)

    assert exc_info.value.context == {
        "parameter_id": "m210-tipo-gravamen-2025",
        "key": "dividend",
        "filing_year": "2025",
        "match_count": "2",
    }
