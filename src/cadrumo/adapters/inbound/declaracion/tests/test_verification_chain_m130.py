"""M130 verification-chain tests over declaracion PDF fixtures."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_m130_support import _M130_CORPUS_IDS, _M130_CORPUS_PARAMS
from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M130,
    BindingId,
    CasillaId,
    Decimal,
    _calculate_engine_values_from_inputs,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19")
_M130_FORMULA_CHAIN_CASILLAS: tuple[CasillaId, ...] = (
    _M130_RENDIMIENTO_NETO_CASILLA,
    validated_casilla_id("04"),
    validated_casilla_id("05"),
    validated_casilla_id("06"),
    validated_casilla_id("07"),
    validated_casilla_id("13"),
    validated_casilla_id("14"),
    validated_casilla_id("15"),
    validated_casilla_id("17"),
    validated_casilla_id("18"),
    _M130_RESULTADO_CASILLA,
)


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    _M130_CORPUS_PARAMS,
    ids=_M130_CORPUS_IDS,
)
def test_verification_chain_m130_engine_recomputes_closure_casilla_19(pdf_stem: str, year: int, period: str) -> None:
    """Engine recomputes casilla 19 (resultado final) from extracted leaf inputs."""
    extracted = _parse_extracted_declaracion_values(modelo="130", fixture_stem=pdf_stem, year=year, period=period)

    closure_extracted: Decimal | None
    if _M130_RESULTADO_CASILLA not in extracted:
        closure_extracted = None
    else:
        raw_closure = extracted[_M130_RESULTADO_CASILLA]
        assert isinstance(raw_closure, Decimal), (
            f"{pdf_stem}: casilla {_M130_RESULTADO_CASILLA!r} expected Decimal, got {type(raw_closure).__name__}"
        )
        closure_extracted = raw_closure

    extracted_c03 = extracted.get(_M130_RENDIMIENTO_NETO_CASILLA)
    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M130)
    if isinstance(extracted_c03, Decimal):
        inputs[_M130_INGRESOS_CASILLA] = extracted_c03

    binding_values: dict[BindingId, Decimal] = {
        "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    }
    engine_values = _calculate_engine_values_from_inputs(
        modelo="130",
        year=year,
        period=period,
        label=pdf_stem,
        inputs=inputs,
        binding_values=binding_values,
    )

    input_01 = inputs.get(_M130_INGRESOS_CASILLA, Decimal("0"))
    input_02 = inputs.get(_M130_GASTOS_CASILLA, Decimal("0"))
    engine_03 = engine_values.get(_M130_RENDIMIENTO_NETO_CASILLA)
    assert engine_03 is not None, (
        f"FORMULA-MISMATCH [{pdf_stem}]: casilla '03' absent from engine result "
        f"- formula modelo-130-rendimiento-neto evaluation failed."
    )
    assert engine_03 == input_01 - input_02, (
        f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '03' = {engine_03!r}, "
        f"expected 01({input_01!r}) - 02({input_02!r}) = {input_01 - input_02!r}"
    )

    if closure_extracted is not None:
        engine_19 = engine_values.get(_M130_RESULTADO_CASILLA)
        assert engine_19 is not None, (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla '19' absent from engine result "
            f"- formula evaluation order issue or casilla missing from revision."
        )
        # ``engine_values`` is declared ``dict[CasillaId, object]`` (the shared
        # support module serves modelos whose computed values are not always
        # Decimal), so ``is not None`` narrows only to ``object``; casilla 19
        # is a numeric resultado, so assert its real type before subtracting.
        assert isinstance(engine_19, Decimal), (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla '19' engine value {engine_19!r} is not a Decimal"
        )
        diff = engine_19 - closure_extracted
        formula_chain_values = " ".join(
            f"{casilla_id}={engine_values.get(casilla_id)!r}" for casilla_id in _M130_FORMULA_CHAIN_CASILLAS
        )
        assert engine_19 == closure_extracted, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine recomputed casilla '19' as "
            f"{engine_19!r} but AEAT-printed form shows {closure_extracted!r}.\n"
            f"  diff: {diff!r}\n"
            f"  extracted inputs: {dict((k, v) for k, v in extracted.items() if k not in _COMPUTED_CASILLAS_M130)}\n"
            f"  engine values for formula chain: {formula_chain_values}"
        )
