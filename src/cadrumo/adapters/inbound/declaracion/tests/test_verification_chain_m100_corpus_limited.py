"""Modelo 100 corpus-limited engine verification-chain tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from .....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ._verification_chain_m100_support import (
    _M100_ANNUAL_PERIOD,
    _M100_BASE_LIQUIDABLE_GENERAL_CASILLA,
    _M100_CLOSURE_ASSERTION_CASILLAS,
    _M100_CUOTA_AUTONOMICA_CASILLA,
    _M100_CUOTA_ESTATAL_CASILLA,
    _M100_INGRESOS_EXPLOTACION_CASILLA,
    _m100_bound_extracted_values,
    _m100_corpus_years,
    _m100_manual_casillas,
    _neutral_m100_bindings,
    _parse_m100_corpus,
)
from ._verification_chain_support import _calculate_engine_values_from_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_CCAA = "cataluna"
_HAS_ECONOMIC_ACTIVITY = "renta-profile-has-economic-activity"


def _admitted_corpus_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    return tuple(year for year in _m100_corpus_years() if support is None or support.admits_filing_year(year))


@pytest.mark.parametrize("year", _admitted_corpus_years())
def test_verification_chain_m100_engine_corpus_limited(year: int) -> None:
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
      3. The extracted activity income reaches a positive base liquidable
         general (0505) through the edition's own chain, and the escala yields
         a non-negative 0545 from it.
      4. The engine's 0545/0546 differ from the PRINTED 0545/0546. On the
         withdrawn renders that difference proved the redaction constant was the
         blocker. Here it proves the printed probes are not engine output --
         which is the property that stops any later reader from mistaking this
         fixture for a calculation oracle.

    Each specimen year the support envelope admits runs against its own
    edition: the casillas that edition leaves manual are fed as leaf inputs, the
    extracted values of its bound casillas travel through their bindings, and
    every other binding it declares receives a neutral value.

    Verdict: EXTRACTION-ONLY. There is no path to VERIFIED from this fixture,
    and an AEAT-authoritative M100 figure would have to come from the bundled
    oracle corpora instead.

    Legal grounding: Ley 35/2006 arts. 50, 62-68; RD 439/2007 Disposicion Final.
    """
    label = f"M100/{year}-{_M100_ANNUAL_PERIOD} corpus-limited"
    extracted = _parse_m100_corpus(year, label)
    revision = published_snapshot("100", filing_year=year, period=_M100_ANNUAL_PERIOD).revision

    bindings = _neutral_m100_bindings(revision, ccaa=_CCAA)
    bindings.decimals.update(_m100_bound_extracted_values(revision, extracted))
    # The specimen declares activity income, so its filer carries on an economic activity.
    if _HAS_ECONOMIC_ACTIVITY in bindings.booleans:
        bindings.booleans[_HAS_ECONOMIC_ACTIVITY] = True
    manual = _m100_manual_casillas(revision)
    inputs = {
        casilla_id: value
        for casilla_id, value in extracted.items()
        if casilla_id in manual and isinstance(value, Decimal)
    }
    inputs.update(resolve_available_bound_inputs_by_casilla_id(revision, bindings.decimals))
    relation_values = {
        "renta-modelo-130-pagos-fraccionados": Decimal("0"),
        "renta-modelo-131-pagos-fraccionados": Decimal("0"),
    }
    engine_values = _calculate_engine_values_from_inputs(
        modelo="100",
        year=year,
        period=_M100_ANNUAL_PERIOD,
        label=label,
        inputs=inputs,
        binding_values=bindings.decimals,
        enum_binding_values=bindings.enums,
        relation_values=relation_values,
        date_binding_values=bindings.dates,
        boolean_binding_values=bindings.booleans,
    )

    for closure_id in _M100_CLOSURE_ASSERTION_CASILLAS:
        assert engine_values.get(closure_id) is not None, (
            f"FORMULA-MISMATCH [{label}]: casilla {closure_id!r} absent "
            f"from engine result - formula evaluation order issue."
        )

    engine_0545 = engine_values[_M100_CUOTA_ESTATAL_CASILLA]
    engine_0546 = engine_values[_M100_CUOTA_AUTONOMICA_CASILLA]
    extracted_0545 = extracted.get(_M100_CUOTA_ESTATAL_CASILLA)
    extracted_0546 = extracted.get(_M100_CUOTA_AUTONOMICA_CASILLA)

    engine_0505 = engine_values.get(_M100_BASE_LIQUIDABLE_GENERAL_CASILLA)
    assert isinstance(engine_0505, Decimal) and engine_0505 > Decimal("0"), (
        f"CORPUS-LIMITED [{label}]: the extracted activity income "
        f"0171={extracted.get(_M100_INGRESOS_EXPLOTACION_CASILLA)!r} should reach the base "
        f"liquidable general, got 0505={engine_0505!r}"
    )
    assert isinstance(engine_0545, Decimal) and engine_0545 >= Decimal("0"), (
        f"CORPUS-LIMITED [{label}]: engine 0545 should be a non-negative escala result, got {engine_0545!r}"
    )
    assert engine_0545 != extracted_0545, (
        f"CORPUS-LIMITED [{label}]: engine 0545={engine_0545!r} == extracted "
        f"{extracted_0545!r} - the printed probe matches engine output, so the fixture "
        f"could be mistaken for a calculation oracle."
    )
    assert engine_0546 != extracted_0546, (
        f"CORPUS-LIMITED [{label}]: engine 0546={engine_0546!r} == extracted "
        f"{extracted_0546!r} - same probe guard as 0545."
    )

    assert _M100_INGRESOS_EXPLOTACION_CASILLA in extracted, (
        f"PARSER-GAP [{label}]: casilla '0171' absent from extracted values."
    )
    assert isinstance(extracted[_M100_INGRESOS_EXPLOTACION_CASILLA], Decimal), (
        f"PARSER-GAP [{label}]: casilla '0171' is not Decimal: "
        f"{type(extracted[_M100_INGRESOS_EXPLOTACION_CASILLA]).__name__!r}"
    )
