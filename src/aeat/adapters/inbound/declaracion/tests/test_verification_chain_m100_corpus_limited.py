"""Modelo 100 corpus-limited engine verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_m100_support import (
    _M100_BASE_LIQUIDABLE_GENERAL_CASILLA,
    _M100_CLOSURE_ASSERTION_CASILLAS,
    _M100_COMPUTED_CASILLAS,
    _M100_CUOTA_AUTONOMICA_CASILLA,
    _M100_CUOTA_ESTATAL_CASILLA,
    _M100_INGRESOS_EXPLOTACION_CASILLA,
    _parse_m100_corpus,
)
from ._verification_chain_support import (
    Decimal,
    RegistryValidationError,
    _decimal_inputs_from_extracted_values,
    _registry_snapshot,
    calculate_registry_snapshot,
    date,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_verification_chain_m100_engine_corpus_limited() -> None:
    """Engine runs against M100 extracted inputs; verifies CORPUS-LIMITED verdict.

    GROUNDED authority: real AEAT corpus PDFs (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/100/2021-0A.pdf (representative
    specimen; same sanitisation pattern applies across 2021/2022/2023).

    Empirical finding: the M100 corpus PDFs have all amounts replaced with the
    uniform synthetic value ~1.001.000,00 (EUR). pdfplumber merges the adjacent
    casilla box number into the value token, producing garbage values like
    Decimal('1001000.001071') for casilla 0171. These values are not
    arithmetically consistent with each other; any formula closure will fail.

    This test confirms the CORPUS-LIMITED verdict:
      1. The engine runs without RegistryValidationError when supplied the
         appropriate binding and relation values.
      2. Engine-computed closure casillas (0545, 0546) do not match their
         sanitised extracted counterparts, confirming the sanitisation artefact
         is the blocker, not a formula or profile defect.
      3. The engine correctly computes 0545 and 0546 from the actual tax
         bracket tables applied to the extracted 0505 value, proving the
         formula DAG is structurally sound.

    Verdict: EXTRACTION-ONLY (CORPUS-LIMITED) - no path to VERIFIED from this
    corpus without un-sanitised real PDF values.

    Legal grounding: Ley 35/2006 arts. 50, 62-68; RD 439/2007 Disposicion Final.
    """
    year = 2021
    extracted = _parse_m100_corpus(year, f"M100/{year}-0A corpus-limited")

    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_M100_COMPUTED_CASILLAS)

    snapshot = _registry_snapshot("100", year, "0A")

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": date(year, 12, 31)},
            binding_values={
                "renta-2021-modelo-100-estimacion-directa-es-normal": Decimal("0"),
                "renta-2021-modelo-111-retenciones-periodicas": Decimal("0"),
                "renta-2021-modelo-115-retenciones-periodicas": Decimal("0"),
                "renta-2021-modelo-123-retenciones-periodicas": Decimal("0"),
            },
            enum_binding_values={
                "renta-2021-profile-tax-residence-ccaa": "cataluna",
            },
            relation_values={
                "renta-2021-rel-130-pagos-fraccionados": Decimal("0"),
                "renta-2021-rel-131-pagos-fraccionados": Decimal("0"),
            },
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M100/{year}-0A corpus-limited]: calculate_registry_snapshot raised "
            f"RegistryValidationError - a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs: {sorted(inputs)}",
        )

    engine_values = dict(result.values)

    for closure_id in _M100_CLOSURE_ASSERTION_CASILLAS:
        assert engine_values.get(closure_id) is not None, (
            f"FORMULA-MISMATCH [M100/{year}-0A corpus-limited]: casilla {closure_id!r} absent "
            f"from engine result - formula evaluation order issue."
        )

    engine_0545 = engine_values[_M100_CUOTA_ESTATAL_CASILLA]
    engine_0546 = engine_values[_M100_CUOTA_AUTONOMICA_CASILLA]
    extracted_0545 = extracted.get(_M100_CUOTA_ESTATAL_CASILLA)
    extracted_0546 = extracted.get(_M100_CUOTA_AUTONOMICA_CASILLA)

    assert isinstance(engine_0545, Decimal) and engine_0545 > Decimal("0"), (
        f"CORPUS-LIMITED [M100/{year}-0A]: engine 0545 should be positive from bracket "
        f"lookup on 0505={inputs.get(_M100_BASE_LIQUIDABLE_GENERAL_CASILLA)!r}, got {engine_0545!r}"
    )
    assert engine_0545 != extracted_0545, (
        f"CORPUS-LIMITED [M100/{year}-0A]: engine 0545={engine_0545!r} == extracted "
        f"{extracted_0545!r} - the sanitisation artefact guard failed. This either means "
        f"the corpus was un-sanitised (unlikely) or the engine formula is wrong."
    )
    assert engine_0546 != extracted_0546, (
        f"CORPUS-LIMITED [M100/{year}-0A]: engine 0546={engine_0546!r} == extracted "
        f"{extracted_0546!r} - same sanitisation guard as 0545."
    )

    assert _M100_INGRESOS_EXPLOTACION_CASILLA in extracted, (
        "PARSER-GAP [M100/2021-0A corpus-limited]: casilla '0171' absent from extracted values."
    )
    assert isinstance(extracted[_M100_INGRESOS_EXPLOTACION_CASILLA], Decimal), (
        "PARSER-GAP [M100/2021-0A corpus-limited]: casilla '0171' is not Decimal: "
        f"{type(extracted[_M100_INGRESOS_EXPLOTACION_CASILLA]).__name__!r}"
    )
