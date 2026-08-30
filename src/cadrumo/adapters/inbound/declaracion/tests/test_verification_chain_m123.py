from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M123_2019,
    _COMPUTED_CASILLAS_M123_2024,
    CasillaId,
    _assert_engine_closure_matches_extracted_decimal,
    _calculate_engine_values_from_inputs,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M123_2019_CLOSURE_CASILLAS: tuple[CasillaId, ...] = (
    validated_casilla_id("06"),
    validated_casilla_id("08"),
)
_M123_TOTAL_RENTAS_CASILLA: CasillaId = validated_casilla_id("03")
_M123_TOTAL_BASE_CASILLA: CasillaId = validated_casilla_id("06")
_M123_TOTAL_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("09")
_M123_2024_CLOSURE_CASILLAS: tuple[CasillaId, ...] = (
    _M123_TOTAL_RENTAS_CASILLA,
    _M123_TOTAL_BASE_CASILLA,
    _M123_TOTAL_RETENCIONES_CASILLA,
    validated_casilla_id("12"),
    validated_casilla_id("14"),
)


@pytest.mark.parametrize(
    "pdf_stem,year,period,computed_set,closure_ids",
    [
        ("2023-1T", 2023, "1T", _COMPUTED_CASILLAS_M123_2019, _M123_2019_CLOSURE_CASILLAS),
        ("2024-1T", 2024, "1T", _COMPUTED_CASILLAS_M123_2024, _M123_2024_CLOSURE_CASILLAS),
    ],
)
def test_verification_chain_m123_engine_recomputes_closure_casillas(
    pdf_stem: str,
    year: int,
    period: str,
    computed_set: frozenset[CasillaId],
    closure_ids: tuple[CasillaId, ...],
) -> None:
    """Engine recomputes M123 closure casillas from leaf inputs.

    FIXTURE, NOT ORACLE: the specimens under
    src/cadrumo/tests/fixtures/justificantes/123/ are
    ``provenance = "synthetic_generated"``. Their field layout follows the
    AEAT-published Diseno de Registro (genuinely AEAT-grounded, and what the
    parse assertions rest on); their AMOUNTS are hand-authored generator
    literals with no AEAT authority. The closures below prove the formula DAG
    agrees with the fixtures' own numbers, not with AEAT.

    2023-1T (2019-2023 revision):
      06 = 03 + 05  (total liquidacion)
      08 = 06 - 07  (resultado a ingresar)
      Fixture prints: 01=4, 02=8000, 03=1520, 04=0, 05=0, 06=1520, 07=0, 08=1520.

    2024-1T (2024-y-siguientes revision):
      03 = 01 + 02   (total rentas categoria 1)
      06 = 04 + 05   (total base)
      09 = 07 + 08   (total retenciones)
      12 = 10 + 11   (total cuota)
      14 = 12 - 13   (resultado a ingresar)
      Fixture prints: 01=5, 02=3, 03=8, 04=10000, 05=5000, 06=15000, 07=1900,
        08=950, 09=2850, 10=0, 11=0, 12=2850, 13=0, 14=2850.

    Legal grounding: Ley 35/2006 art.25, art.99; RD 439/2007 art.109, art.108,
    art.90, art.101; Orden EHA/3435/2007 Anexo II.

    Verdict: VERIFIED for all closure casillas in both revisions.
    """
    extracted = _parse_extracted_declaracion_values(modelo="123", fixture_stem=pdf_stem, year=year, period=period)
    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=computed_set)
    engine_values = _calculate_engine_values_from_inputs(
        modelo="123",
        year=year,
        period=period,
        label=f"M123/{pdf_stem}",
        inputs=inputs,
    )

    for closure_id in closure_ids:
        if closure_id not in extracted:
            continue
        _assert_engine_closure_matches_extracted_decimal(
            label=f"M123/{pdf_stem}",
            engine_values=engine_values,
            extracted=extracted,
            casilla_id=closure_id,
            inputs=inputs,
        )
