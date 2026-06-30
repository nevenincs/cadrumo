"""M111 verification-chain tests over declaracion PDF fixtures."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M111,
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryValidationError,
    _casilla_id,
    _casilla_ids,
    _period_to_date,
    _registry_snapshot,
    calculate_registry_snapshot,
    parse_declaracion,
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
    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="111",
            año_override=year,
            period_override=period,
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised DeclaracionParseError.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M111:
            continue
        if isinstance(value, Decimal):
            inputs[casilla_id] = value

    snapshot = _registry_snapshot("111", year, period)
    filing_period_date = _period_to_date(year, period)

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": filing_period_date},
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised "
            f"RegistryValidationError - a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}",
        )

    engine_values = dict(result.values)
    has_leaf_inputs = bool(inputs.keys() & _M111_RETENCIONES_TOTAL_LEAVES)

    if _M111_RETENCIONES_TOTAL_CASILLA in extracted and has_leaf_inputs:
        extracted_28 = extracted[_M111_RETENCIONES_TOTAL_CASILLA]
        assert isinstance(extracted_28, Decimal)
        engine_28 = engine_values.get(_M111_RETENCIONES_TOTAL_CASILLA)
        assert engine_28 is not None, f"FORMULA-MISMATCH [{pdf_stem}]: casilla '28' absent from engine result."
        assert engine_28 == extracted_28, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '28' = {engine_28!r}, "
            f"AEAT-printed = {extracted_28!r}.\n"
            f"  diff: {engine_28 - extracted_28!r}\n"
            f"  inputs: {inputs}"
        )

    if _M111_RESULTADO_CASILLA in extracted and has_leaf_inputs:
        extracted_30 = extracted[_M111_RESULTADO_CASILLA]
        assert isinstance(extracted_30, Decimal)
        engine_30 = engine_values.get(_M111_RESULTADO_CASILLA)
        assert engine_30 is not None, f"FORMULA-MISMATCH [{pdf_stem}]: casilla '30' absent from engine result."
        assert engine_30 == extracted_30, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '30' = {engine_30!r}, "
            f"AEAT-printed = {extracted_30!r}.\n"
            f"  diff: {engine_30 - extracted_30!r}\n"
            f"  inputs: {inputs}"
        )
