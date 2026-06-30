from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M131,
    BindingId,
    CasillaId,
    Decimal,
    _assert_engine_closure_matches_extracted_decimal,
    _calculate_engine_values_from_inputs,
    _casilla_id,
    _decimal_inputs_from_extracted_values,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M131_CLOSURE_CASILLAS: tuple[CasillaId, ...] = (
    _casilla_id("07"),
    _casilla_id("10"),
    _casilla_id("13"),
    _casilla_id("15"),
)


def test_verification_chain_m131_engine_recomputes_closure_casillas() -> None:
    """Engine recomputes M131 closure casillas from leaf inputs.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/131/2024-1T.pdf.
    The fixture encodes filing year 2026 (detected from PDF header).
    Registry revision '2026' is used.

    Chain:
      1. parse_declaracion with año_override=2026, period_override='1T'.
      2. Filter to non-computed casillas (01, 02, 03, 05, 08, 09, 12, 14) -> inputs.
      3. Supply binding_values for casilla 11 (previous-filing bound):
         modelo-131-2026-resultados-negativos-anteriores = 0.
      4. calculate_registry_snapshot.
      5. Assert engine computes:
         07 = 02 + 04 + 06
         10 = 07 - 08 - 09
         13 = 10 - 11 - 12
         15 = 13 - 14

    Fixture values: 01=5000, 02=100, 03=0, 05=0, 07=100 (computed), 08=0, 09=0,
      10=100 (computed), 11=0, 12=0, 13=100 (computed), 14=0, 15=100 (computed).

    Legal grounding: RD 439/2007 art.110, art.95; Orden EHA/672/2007 art.1;
    Orden HFP/1359/2023 art.4.

    Verdict: VERIFIED - all four formula closure casillas match fixture values.
    """
    extracted = _parse_extracted_declaracion_values(
        modelo="131",
        fixture_stem="2024-1T",
        year=2026,
        period="1T",
        template_revision="2026",
    )
    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M131)

    binding_values: dict[BindingId, Decimal] = {
        "modelo-131-2026-resultados-negativos-anteriores": Decimal("0"),
    }
    engine_values = _calculate_engine_values_from_inputs(
        modelo="131",
        year=2026,
        period="1T",
        label="M131/yr=2026-1T",
        inputs=inputs,
        binding_values=binding_values,
    )

    for closure_id in _M131_CLOSURE_CASILLAS:
        if closure_id not in extracted:
            continue
        _assert_engine_closure_matches_extracted_decimal(
            label="M131/yr=2026-1T",
            engine_values=engine_values,
            extracted=extracted,
            casilla_id=closure_id,
            inputs=inputs,
        )
