"""M130 verification-chain tests over declaracion PDF fixtures."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M130,
    BindingId,
    CasillaId,
    Decimal,
    RegistryValidationError,
    _casilla_id,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
    _period_to_date,
    _registry_snapshot,
    calculate_registry_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = _casilla_id("03")
_M130_RESULTADO_CASILLA: CasillaId = _casilla_id("19")
_M130_FORMULA_CHAIN_CASILLAS: tuple[CasillaId, ...] = (
    _M130_RENDIMIENTO_NETO_CASILLA,
    _casilla_id("04"),
    _casilla_id("05"),
    _casilla_id("06"),
    _casilla_id("07"),
    _casilla_id("13"),
    _casilla_id("14"),
    _casilla_id("15"),
    _casilla_id("17"),
    _casilla_id("18"),
    _M130_RESULTADO_CASILLA,
)


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2021-2T", 2021, "2T"),
        ("2021-3T", 2021, "3T"),
        ("2021-4T", 2021, "4T"),
        ("2022-1T", 2022, "1T"),
        ("2022-2T", 2022, "2T"),
        ("2022-3T", 2022, "3T"),
        ("2022-4T", 2022, "4T"),
        ("2023-1T", 2023, "1T"),
        ("2023-2T", 2023, "2T"),
        ("2023-3T", 2023, "3T"),
        ("2023-4T", 2023, "4T"),
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
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

    snapshot = _registry_snapshot("130", year, period)
    filing_period_date = _period_to_date(year, period)

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": filing_period_date},
            binding_values=binding_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised "
            f"RegistryValidationError - a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}",
        )

    engine_values = dict(result.values)

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
        formula_chain_values = " ".join(
            f"{casilla_id}={engine_values.get(casilla_id)!r}" for casilla_id in _M130_FORMULA_CHAIN_CASILLAS
        )
        assert engine_19 == closure_extracted, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine recomputed casilla '19' as "
            f"{engine_19!r} but AEAT-printed form shows {closure_extracted!r}.\n"
            f"  diff: {engine_19 - closure_extracted!r}\n"
            f"  extracted inputs: {dict((k, v) for k, v in extracted.items() if k not in _COMPUTED_CASILLAS_M130)}\n"
            f"  engine values for formula chain: {formula_chain_values}"
        )
