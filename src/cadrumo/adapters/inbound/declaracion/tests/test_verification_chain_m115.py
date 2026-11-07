from __future__ import annotations

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .parser_boundary_support import MODELO_115_SYNTHETIC_FIXTURE, specimen_period
from .verification_chain_support import (
    COMPUTED_CASILLAS_M115,
    assert_engine_closure_matches_extracted_decimal,
    calculate_engine_values_from_inputs,
    decimal_inputs_from_extracted_values,
    parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_SPECIMEN = specimen_period(MODELO_115_SYNTHETIC_FIXTURE)
_LABEL = f"M115/{MODELO_115_SYNTHETIC_FIXTURE.stem}"


_M115_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M115_ANTERIORES_CASILLA: CasillaId = validated_casilla_id("04")
_M115_RESULTADO_CASILLA: CasillaId = validated_casilla_id("05")
_M115_REQUIRED_CASILLAS: tuple[CasillaId, ...] = (
    _M115_TOTAL_PERCEPTORES_CASILLA,
    _M115_BASE_TOTAL_CASILLA,
    _M115_RETENCIONES_CASILLA,
    _M115_ANTERIORES_CASILLA,
    _M115_RESULTADO_CASILLA,
)
_M115_CLOSURE_CASILLAS: tuple[CasillaId, ...] = (_M115_RESULTADO_CASILLA,)


def test_verification_chain_m115_engine_recomputes_resultado() -> None:
    """Engine recomputes casilla 05 (resultado) from leaf inputs, casilla 03 among them.

    FIXTURE, NOT ORACLE: the specimen at
    src/cadrumo/tests/fixtures/justificantes/115/2024-1T.pdf is
    ``provenance = "synthetic_generated"``. Its FIELD LAYOUT is generated from
    the AEAT-published Diseno de Registro DR xls (aeat-dr-115-2019-v13) — that
    part is genuinely AEAT-grounded and is what the parse assertions rest on.
    Its AMOUNTS are hand-authored generator literals and carry no AEAT
    authority, so the closure below proves the formulas agree with the
    fixture's own numbers, not with AEAT.

    Chain:
      1. parse_declaracion -> extracted casillas 01 (perceptores), 02 (base),
         03 (retenciones), 04 (anteriores declaraciones), 05 (resultado a ingresar).
      2. Filter to non-computed casillas (01, 02, 03, 04) -> inputs.
      3. calculate_registry_snapshot with no binding_values (no previous_filing bindings).
      4. Assert engine.values["05"] == extracted["05"] (VERIFIED).

    Legal grounding: RD 439/2007 art.100, art.108; Ley 35/2006 art.99, art.101;
    Orden 2000-11-20 apartado primero.

    Verdict: the subtract formula for resultado closes against the fixture's
    own printed values. Not an
    AEAT-verified verdict — see FIXTURE, NOT ORACLE above.
    """
    extracted = parse_extracted_declaracion_values(
        modelo="115",
        fixture_stem=MODELO_115_SYNTHETIC_FIXTURE.stem,
        year=_SPECIMEN.filing_year,
        period=_SPECIMEN.code,
    )

    for required_id in _M115_REQUIRED_CASILLAS:
        assert required_id in extracted, (
            f"PARSER-GAP [{_LABEL}]: casilla {required_id!r} not extracted.\n  got: {sorted(extracted)}"
        )

    inputs = decimal_inputs_from_extracted_values(extracted, excluding=COMPUTED_CASILLAS_M115)
    engine_values = calculate_engine_values_from_inputs(
        modelo="115",
        year=_SPECIMEN.filing_year,
        period=_SPECIMEN.code,
        label=_LABEL,
        inputs=inputs,
    )

    for closure_id in _M115_CLOSURE_CASILLAS:
        assert_engine_closure_matches_extracted_decimal(
            label=_LABEL,
            engine_values=engine_values,
            extracted=extracted,
            casilla_id=closure_id,
            inputs=inputs,
        )
