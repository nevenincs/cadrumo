from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M115,
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryValidationError,
    _casilla_id,
    _period_to_date,
    _registry_snapshot,
    calculate_registry_snapshot,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M115_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M115_ANTERIORES_CASILLA: CasillaId = _casilla_id("04")
_M115_RESULTADO_CASILLA: CasillaId = _casilla_id("05")
_M115_REQUIRED_CASILLAS: tuple[CasillaId, ...] = (
    _M115_TOTAL_PERCEPTORES_CASILLA,
    _M115_BASE_TOTAL_CASILLA,
    _M115_RETENCIONES_CASILLA,
    _M115_ANTERIORES_CASILLA,
    _M115_RESULTADO_CASILLA,
)
_M115_CLOSURE_CASILLAS: tuple[CasillaId, ...] = (
    _M115_RETENCIONES_CASILLA,
    _M115_RESULTADO_CASILLA,
)


def test_verification_chain_m115_engine_recomputes_retenciones_and_resultado() -> None:
    """Engine recomputes casilla 03 (retenciones) and 05 (resultado) from leaf inputs.

    GROUNDED authority: synthetic fixture generated from AEAT-published Diseno de
    Registro DR xls (aeat-dr-115-2019-v13) committed at
    src/aeat/tests/fixtures/justificantes/115/2024-1T.pdf.

    Chain:
      1. parse_declaracion -> extracted casillas 01 (perceptores), 02 (base),
         03 (retenciones), 04 (anteriores declaraciones), 05 (resultado a ingresar).
      2. Filter to non-computed casillas (01, 02, 04) -> inputs.
      3. calculate_registry_snapshot with no binding_values (no previous_filing bindings).
      4. Assert engine.values["03"] == extracted["03"] (VERIFIED).
         Assert engine.values["05"] == extracted["05"] (VERIFIED).

    Legal grounding: RD 439/2007 art.100, art.108; Ley 35/2006 art.99, art.101;
    Orden 2000-11-20 apartado primero.

    Verdict: VERIFIED - the percent formula for retenciones and the subtract formula
    for resultado both match the synthetic AEAT-grounded fixture.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "115" / "2024-1T.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="115",
            año_override=2024,
            period_override="1T",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M115/2024-1T]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    for required_id in _M115_REQUIRED_CASILLAS:
        assert required_id in extracted, (
            f"PARSER-GAP [M115/2024-1T]: casilla {required_id!r} not extracted.\n  got: {sorted(extracted)}"
        )

    inputs: dict[CasillaId, Decimal] = {
        cid: val
        for cid, val in extracted.items()
        if cid not in _COMPUTED_CASILLAS_M115 and isinstance(val, Decimal)
    }

    snapshot = _registry_snapshot("115", 2024, "1T")
    filing_period_date = _period_to_date(2024, "1T")

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": filing_period_date},
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M115/2024-1T]: calculate_registry_snapshot raised "
            f"RegistryValidationError.\n  error: {exc}\n  inputs: {sorted(inputs)}",
        )

    engine_values = dict(result.values)

    for closure_id in _M115_CLOSURE_CASILLAS:
        extracted_val = extracted[closure_id]
        assert isinstance(extracted_val, Decimal)
        engine_val = engine_values.get(closure_id)
        assert engine_val is not None, (
            f"FORMULA-MISMATCH [M115/2024-1T]: casilla {closure_id!r} absent from engine result."
        )
        assert engine_val == extracted_val, (
            f"FORMULA-MISMATCH [M115/2024-1T]: engine casilla {closure_id!r} = {engine_val!r}, "
            f"AEAT-printed = {extracted_val!r}.\n"
            f"  inputs: {inputs}"
        )
