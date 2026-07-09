"""Tests for the official Modelo 210 tipo-de-renta code axis and projection.

Grounds the code-to-:class:`~aeat.core.TipoRentaIrnr` projection declared in
:mod:`aeat.core._irnr` against the m210-irnr-phase-2-engine ADR (Slice A): the
code list is the bundled Orden EHA/3316/2010 HOJA INFORMATIVA 210, and only the
rate-concept-grounded codes are declared (the fetch-gated special-rate codes are
absent by design, not by omission).
"""

from __future__ import annotations

import pytest

from ...core import (
    M210_TIPO_RENTA_CODE_PROJECTION,
    OFFICIAL_M210_TIPO_RENTA_CODES,
    TipoRentaGroundingTier,
    TipoRentaIrnr,
    project_m210_tipo_renta_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# The rate-concept-grounded codes Slice A declares, keyed to the TRLIRNR
# Art. 25 letter (or Art. 13.1.h) the bundled corpus grounds the concept on.
# Derived from the bundled HOJA INFORMATIVA 210 income-type labels; NOT copied
# from engine output.
_EXPECTED_CONCEPT = {
    "01": TipoRentaIrnr.GENERAL,
    "02": TipoRentaIrnr.INMOBILIARIA,
    "03": TipoRentaIrnr.GENERAL,
    "04": TipoRentaIrnr.DIVIDEND,
    "05": TipoRentaIrnr.INTEREST,
    "06": TipoRentaIrnr.INTEREST,
    "07": TipoRentaIrnr.INTEREST,
    "14": TipoRentaIrnr.GENERAL,
    "15": TipoRentaIrnr.GENERAL,
    "16": TipoRentaIrnr.GENERAL,
    "17": TipoRentaIrnr.GENERAL,
    "18": TipoRentaIrnr.PENSION,
    "21": TipoRentaIrnr.GENERAL,
    "22": TipoRentaIrnr.GENERAL,
    "24": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "25": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "26": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "28": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "29": TipoRentaIrnr.DIVIDEND,
    "30": TipoRentaIrnr.DIVIDEND,
    "33": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "34": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "35": TipoRentaIrnr.GENERAL,
    "36": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "37": TipoRentaIrnr.INTEREST,
    "38": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
}

# The codes deliberately NOT declared: their rate is not bundle-verifiable
# (cánones may bear an un-bundled Art. 25 letter; asistencia técnica 13 is
# cánones-adjacent in the HOJA INFORMATIVA; reaseguros/navegación/imposición-
# complementaria/loterías carry special rates absent from the Phase-1 extract).
_FETCH_GATED_CODES = frozenset({"08", "09", "10", "11", "12", "13", "19", "20", "27", "31", "32"})


def test_projection_maps_every_declared_code_to_its_grounded_concept() -> None:
    assert dict(M210_TIPO_RENTA_CODE_PROJECTION) == _EXPECTED_CONCEPT


def test_declared_code_set_is_exactly_the_grounded_set() -> None:
    declared = {entry.code for entry in OFFICIAL_M210_TIPO_RENTA_CODES}
    assert declared == set(_EXPECTED_CONCEPT)
    # No fetch-gated code leaks into the declared set (no fabricated rate).
    assert declared.isdisjoint(_FETCH_GATED_CODES)


def test_projection_function_resolves_declared_codes() -> None:
    for code, concept in _EXPECTED_CONCEPT.items():
        assert project_m210_tipo_renta_code(code) is concept


@pytest.mark.parametrize("code", sorted(_FETCH_GATED_CODES))
def test_fetch_gated_code_raises_rather_than_fabricating_a_rate(code: str) -> None:
    # A code whose rate is not bundle-verifiable must refuse loudly, never
    # resolve to a fabricated concept/rate.
    with pytest.raises(KeyError):
        project_m210_tipo_renta_code(code)


def test_grounding_tier_matches_the_rate_letter() -> None:
    # RESIDUAL iff the concept is GENERAL (Art. 25.1.a residual clause);
    # RATE_VERIFIED for every code whose concept is a named Art. 25 letter
    # (pension/dividend/interest/ganancia) or the bundled inmobiliaria mechanism.
    for entry in OFFICIAL_M210_TIPO_RENTA_CODES:
        if entry.concept is TipoRentaIrnr.GENERAL:
            assert entry.grounding_tier is TipoRentaGroundingTier.RESIDUAL
            assert entry.rate_legal_ref == "trlirnr-rdleg-5-2004:art-25.1.a"
        else:
            assert entry.grounding_tier is TipoRentaGroundingTier.RATE_VERIFIED


def test_every_code_is_two_digit_and_unique() -> None:
    codes = [entry.code for entry in OFFICIAL_M210_TIPO_RENTA_CODES]
    assert len(codes) == len(set(codes))
    assert all(len(code) == 2 and code.isdigit() for code in codes)
