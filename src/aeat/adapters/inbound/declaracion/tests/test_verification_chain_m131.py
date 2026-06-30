from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M131,
    FIXTURES_DIR,
    BindingId,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryValidationError,
    _period_to_date,
    _registry_snapshot,
    calculate_registry_snapshot,
    parse_declaracion,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


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
    pdf_path = FIXTURES_DIR / "justificantes" / "131" / "2024-1T.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="131",
            año_override=2026,
            template_revision_override="2026",
            period_override="1T",
        )
    except DeclaracionParseError as exc:
        detail = exc.translated_message or str(exc) or type(exc).__name__
        context = exc.context if exc.context else {}
        pytest.fail(
            f"PARSER-GAP [M131/2024-1T.pdf/yr=2026]: parse_declaracion raised.\n  error: {detail} (context={context})",
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    inputs: dict[CasillaId, Decimal] = {
        cid: val
        for cid, val in extracted.items()
        if cid not in _COMPUTED_CASILLAS_M131 and isinstance(val, Decimal)
    }

    binding_values: dict[BindingId, Decimal] = {
        "modelo-131-2026-resultados-negativos-anteriores": Decimal("0"),
    }

    snapshot = _registry_snapshot("131", 2026, "1T")
    filing_period_date = _period_to_date(2026, "1T")

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": filing_period_date},
            binding_values=binding_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M131/yr=2026-1T]: calculate_registry_snapshot raised "
            f"RegistryValidationError.\n  error: {exc}\n"
            f"  inputs: {sorted(inputs)}\n  binding_values: {sorted(binding_values)}",
        )

    engine_values = dict(result.values)

    for closure_id in _M131_CLOSURE_CASILLAS:
        if closure_id not in extracted:
            continue
        extracted_val = extracted[closure_id]
        assert isinstance(extracted_val, Decimal)
        engine_val = engine_values.get(closure_id)
        assert engine_val is not None, (
            f"FORMULA-MISMATCH [M131/yr=2026-1T]: casilla {closure_id!r} absent from engine result."
        )
        assert engine_val == extracted_val, (
            f"FORMULA-MISMATCH [M131/yr=2026-1T]: engine casilla {closure_id!r} = {engine_val!r}, "
            f"AEAT-printed = {extracted_val!r}.\n  inputs: {inputs}"
        )
