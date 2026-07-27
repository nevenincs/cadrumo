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
    _calculate_engine_values_from_inputs,
    _decimal_inputs_from_extracted_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_verification_chain_m100_engine_corpus_limited() -> None:
    """Engine runs against M100 extracted inputs; verifies CORPUS-LIMITED verdict.

    WHAT THIS PROVES, AND WHAT IT NO LONGER CLAIMS.

    This test was authored against a sanitised REAL render, and its verdict was
    a claim about that render: every amount had been overwritten with one
    constant, so no printed arithmetic held and no formula closure could be
    checked. The claim was "this corpus cannot ground the calculation", and the
    evidence was the corpus.

    All three M100 renders have since been withdrawn -- they carried personal
    data the redaction pipeline never wrote -- and replaced by generated
    specimens. The verdict is UNCHANGED and its reason has moved. The printed
    amounts are now probes chosen by the fixture generator, deliberately not
    derived from any formula, so they still cannot ground a calculation; what
    has gone is the ability to say anything at all about a real filing.

    What survives here is structural, and is worth keeping:
      1. The engine runs without RegistryValidationError on inputs that came out
         of the real parser, over a real registry snapshot. That is the parse ->
         engine seam, and nothing else exercises it for M100.
      2. Every closure casilla the formula DAG declares (0545, 0546, 0585, 0586)
         reaches the engine result rather than dropping out of evaluation order.
      3. The engine computes a positive 0545 from the actual tax bracket tables
         applied to the extracted 0505, so the bracket lookup is wired.
      4. The engine's 0545/0546 differ from the PRINTED 0545/0546. On the
         withdrawn renders that difference proved the redaction constant was the
         blocker. Here it proves the printed probes are not engine output --
         which is the property that stops any later reader from mistaking this
         fixture for a calculation oracle.

    Verdict: EXTRACTION-ONLY. There is no path to VERIFIED from this fixture,
    and an AEAT-authoritative M100 figure would have to come from the bundled
    oracle corpora instead.

    Legal grounding: Ley 35/2006 arts. 50, 62-68; RD 439/2007 Disposicion Final.
    """
    year = 2022
    extracted = _parse_m100_corpus(year, f"M100/{year}-0A corpus-limited")

    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_M100_COMPUTED_CASILLAS)
    binding_values = {
        "renta-2022-modelo-100-estimacion-directa-es-normal": Decimal("0"),
        "renta-2022-modelo-111-retenciones-periodicas": Decimal("0"),
        "renta-2022-modelo-123-retenciones-periodicas": Decimal("0"),
        # Childless corpus fixture: Art. 58/61 LIRPF mínimo por descendientes
        # aggregate is zero.
        "renta-2022-profile-minimo-descendientes-estatal": Decimal("0"),
        # Parte autonómica: Cataluña profile mirrors the estatal zero.
        "renta-2022-profile-minimo-descendientes-autonomico": Decimal("0"),
    }
    enum_binding_values = {
        "renta-2022-profile-tax-residence-ccaa": "cataluna",
    }
    relation_values = {
        "renta-2022-rel-130-pagos-fraccionados": Decimal("0"),
        "renta-2022-rel-131-pagos-fraccionados": Decimal("0"),
    }
    engine_values = _calculate_engine_values_from_inputs(
        modelo="100",
        year=year,
        period="0A",
        label=f"M100/{year}-0A corpus-limited",
        inputs=inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
    )

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
        "PARSER-GAP [M100/2022-0A corpus-limited]: casilla '0171' absent from extracted values."
    )
    assert isinstance(extracted[_M100_INGRESOS_EXPLOTACION_CASILLA], Decimal), (
        "PARSER-GAP [M100/2022-0A corpus-limited]: casilla '0171' is not Decimal: "
        f"{type(extracted[_M100_INGRESOS_EXPLOTACION_CASILLA]).__name__!r}"
    )
