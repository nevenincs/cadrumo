"""M111 verification-chain tests over declaracion PDF fixtures."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M111,
    CasillaId,
    _assert_engine_closure_matches_extracted_decimal,
    _calculate_engine_values_from_inputs,
    _casilla_id,
    _casilla_ids,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("28")
_M111_RESULTADO_CASILLA: CasillaId = _casilla_id("30")
_M111_RETENCIONES_TOTAL_LEAVES: frozenset[CasillaId] = _casilla_ids(
    "03",
    "06",
    "09",
    "12",
    "15",
    "18",
    "21",
    "24",
    "27",
)


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_verification_chain_m111_engine_recomputes_closure_casillas_28_and_30(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """Engine recomputes casilla 28 (total retenciones) and 30 (resultado) from leaf inputs.

    GROUNDED authority: AEAT corpus PDFs from the sanitised real-form fixture
    set committed at src/aeat/tests/fixtures/justificantes/111/.
    """
    extracted = _parse_extracted_declaracion_values(modelo="111", fixture_stem=pdf_stem, year=year, period=period)
    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M111)
    engine_values = _calculate_engine_values_from_inputs(
        modelo="111",
        year=year,
        period=period,
        label=pdf_stem,
        inputs=inputs,
    )
    has_leaf_inputs = bool(inputs.keys() & _M111_RETENCIONES_TOTAL_LEAVES)

    if _M111_RETENCIONES_TOTAL_CASILLA in extracted and has_leaf_inputs:
        _assert_engine_closure_matches_extracted_decimal(
            label=pdf_stem,
            engine_values=engine_values,
            extracted=extracted,
            casilla_id=_M111_RETENCIONES_TOTAL_CASILLA,
            inputs=inputs,
        )

    if _M111_RESULTADO_CASILLA in extracted and has_leaf_inputs:
        _assert_engine_closure_matches_extracted_decimal(
            label=pdf_stem,
            engine_values=engine_values,
            extracted=extracted,
            casilla_id=_M111_RESULTADO_CASILLA,
            inputs=inputs,
        )
