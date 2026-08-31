"""Tests for the official Modelo 210 tipo-de-renta code axis and projection.

Grounds the code-to-:class:`~cadrumo.core.TipoRentaIrnr` projection declared in
:mod:`cadrumo.core.irnr` against the M210 IRNR implementation decision: the
code list is the bundled Orden EHA/3316/2010 HOJA INFORMATIVA 210, and only the
rate-concept-grounded codes are declared (the fetch-gated special-rate codes are
absent by design, not by omission).
"""

from __future__ import annotations

import pytest

from ..irnr import (
    M210_TIPO_RENTA_CODE_PROJECTION,
    OFFICIAL_M210_TIPO_RENTA_CODES,
    TipoRentaGroundingTier,
    TipoRentaIrnr,
    project_m210_tipo_renta_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# The rate-concept-grounded codes declared here, keyed to the TRLIRNR
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
    "08": TipoRentaIrnr.CANONES,
    "09": TipoRentaIrnr.CANONES,
    "10": TipoRentaIrnr.CANONES,
    "11": TipoRentaIrnr.CANONES,
    "12": TipoRentaIrnr.CANONES,
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
    "32": TipoRentaIrnr.CANONES,
    "33": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "34": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "35": TipoRentaIrnr.GENERAL,
    "36": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
    "37": TipoRentaIrnr.INTEREST,
    "38": TipoRentaIrnr.GANANCIA_PATRIMONIAL,
}

# The codes deliberately NOT declared: their rate is not bundle-verifiable.
# The cánones codes 08/09/10/11/12/32 were promoted into the declared set —
# cánones is the general rendimiento rate under the Art. 25.1.a residual clause
# (the consolidated Art. 25.1 carries no cánones-specific letter). What remains
# fetch-gated: asistencia técnica 13 (cánones-adjacent in the HOJA INFORMATIVA,
# a possible non-bundled special letter, NOT cánones proper), reaseguros 19
# (Art. 25.1.e), navegación 20 (Art. 25.1.d), imposición complementaria 27
# (Art. 19.2), and premios de loterías 31 (D.A. 5ª) — special rates absent from
# the initial extract.
_FETCH_GATED_CODES = frozenset({"13", "19", "20", "27", "31"})


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
    # RESIDUAL iff the concept rests on the Art. 25.1.a residual clause — an
    # ordinary rendimiento with no special regime. Two concepts qualify: GENERAL,
    # and CANONES (the consolidated Art. 25.1 carries no cánones-specific letter,
    # so royalties are taxed at the general rendimiento rate). Both MUST cite the
    # Art. 25.1.a residual clause. Every other concept is grounded on a named
    # Art. 25 letter (pension 25.1.b; dividend/interest/ganancia 25.1.f) or the
    # bundled Art. 13.1.h imputed real-estate mechanism (inmobiliaria — carried at
    # the 25.1.a general rate but rate-verified), so it is RATE_VERIFIED.
    residual_concepts = {TipoRentaIrnr.GENERAL, TipoRentaIrnr.CANONES}
    for entry in OFFICIAL_M210_TIPO_RENTA_CODES:
        if entry.concept in residual_concepts:
            assert entry.grounding_tier is TipoRentaGroundingTier.RESIDUAL
            assert entry.rate_legal_ref == "trlirnr-rdleg-5-2004:art-25.1.a"
        else:
            assert entry.grounding_tier is TipoRentaGroundingTier.RATE_VERIFIED


def test_every_code_is_two_digit_and_unique() -> None:
    codes = [entry.code for entry in OFFICIAL_M210_TIPO_RENTA_CODES]
    assert len(codes) == len(set(codes))
    assert all(len(code) == 2 and code.isdigit() for code in codes)
