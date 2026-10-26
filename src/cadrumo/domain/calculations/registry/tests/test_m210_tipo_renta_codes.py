"""Tests for the registry-owned Modelo 210 tipo-de-renta code projection.

The dated fact catalogue owns the official code list and its projection onto
the opaque :class:`~cadrumo.core.TipoRentaIrnr` token. These tests live beside
that policy boundary and consume its public catalogue surface.
"""

from __future__ import annotations

import pytest

from ..irnr_tipo_renta import (
    m210_tipo_renta_code_projection,
    resolve_tipo_renta_irnr_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


# The rate-concept-grounded codes declared here, keyed to the TRLIRNR
# Art. 25 letter (or Art. 13.1.h) the bundled corpus grounds the concept on.
# Derived from the bundled HOJA INFORMATIVA 210 income-type labels; NOT copied
# from engine output.
_EXPECTED_CONCEPT = {
    "01": "general",
    "02": "inmobiliaria",
    "03": "general",
    "04": "dividend",
    "05": "interest",
    "06": "interest",
    "07": "interest",
    "08": "canones",
    "09": "canones",
    "10": "canones",
    "11": "canones",
    "12": "canones",
    "14": "general",
    "15": "general",
    "16": "general",
    "17": "general",
    "18": "pension",
    "21": "general",
    "22": "general",
    "24": "ganancia_patrimonial",
    "25": "ganancia_patrimonial",
    "26": "ganancia_patrimonial",
    "28": "ganancia_patrimonial",
    "29": "dividend",
    "30": "dividend",
    "32": "canones",
    "33": "ganancia_patrimonial",
    "34": "ganancia_patrimonial",
    "35": "general",
    "36": "ganancia_patrimonial",
    "37": "interest",
    "38": "ganancia_patrimonial",
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
    projection = m210_tipo_renta_code_projection()
    assert {code: concept.value for code, concept in projection.items()} == _EXPECTED_CONCEPT


def test_declared_code_set_is_exactly_the_grounded_set() -> None:
    catalogue = resolve_tipo_renta_irnr_catalogue()
    grounded = tuple(entry for entry in catalogue.code_definitions if entry.concept is not None)
    declared = {entry.code for entry in grounded}
    assert declared == set(_EXPECTED_CONCEPT)
    # No fetch-gated code leaks into the declared set (no fabricated rate).
    assert declared.isdisjoint(_FETCH_GATED_CODES)


def test_grounding_tier_matches_the_rate_letter() -> None:
    # RESIDUAL iff the concept rests on the Art. 25.1.a residual clause — an
    # ordinary rendimiento with no special regime. Two concepts qualify:
    # GENERAL and CANONES. Both MUST cite Art. 25.1.a. Every other concept is
    # grounded on a named Art. 25 letter or the bundled Art. 13.1.h mechanism.
    residual_concepts = {"general", "canones"}
    catalogue = resolve_tipo_renta_irnr_catalogue()
    grounded = tuple(entry for entry in catalogue.code_definitions if entry.concept is not None)
    for entry in grounded:
        if entry.concept is not None and entry.concept.value in residual_concepts:
            assert entry.grounding_tier == "residual"
            assert entry.rate_legal_ref == "trlirnr-rdleg-5-2004:art-25.1.a"
        else:
            assert entry.grounding_tier == "rate_verified"


def test_every_code_is_two_digit_and_unique() -> None:
    catalogue = resolve_tipo_renta_irnr_catalogue()
    codes = [entry.code for entry in catalogue.code_definitions if entry.concept is not None]
    assert len(codes) == len(set(codes))
    assert all(len(code) == 2 and code.isdigit() for code in codes)
