"""Both sede identity checkers reject the same Spanish negatives.

GROI (Spanish ROI registration) and NIF-IVA (VIES) answer different
questions, so their affirmation vocabulary legitimately differs. Their
*rejection* vocabulary does not: AEAT renders both refusals off the same
Spanish template family, and AEAT phrases a rejection by negating the very
word it uses to affirm (``no es un NIF válido``). A checker whose negative
table misses a phrase therefore does not merely fall back to ``unknown`` --
if a generic ``valido`` substring survives in its positive table, it reports
an explicit refusal as ``valid``.

These fixtures pin that shared refusal contract in both directions.
"""

from __future__ import annotations

import pytest

from .._adapter_utils import SPANISH_NEGATIVE_VERDICT_MARKERS, extract_marker_verdict
from ..groi_check import extract_verdict_from_response_text as groi_verdict
from ..nif_iva_check import extract_verdict_from_response_text as nif_iva_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: AEAT rejection phrasings both surfaces must classify identically.
SPANISH_NEGATIVE_RESPONSES = (
    "No es un NIF válido",
    "El campo NIF no es un NIF válido",
    "No válido",
    "No consta",
    "El operador no está identificado",
    "No se encuentra identificado",
    "Operador no identificado",
)


@pytest.mark.parametrize("body_text", SPANISH_NEGATIVE_RESPONSES)
def test_both_checkers_classify_spanish_negatives_as_invalid(body_text: str) -> None:
    """A refusal is a refusal on either surface -- never valid, never unknown."""
    assert groi_verdict(body_text) == "invalid", body_text
    assert nif_iva_verdict(body_text) == "invalid", body_text


@pytest.mark.parametrize("body_text", SPANISH_NEGATIVE_RESPONSES)
def test_no_negative_response_is_ever_reported_valid(body_text: str) -> None:
    """The safety property: an AEAT rejection must never read as a pass."""
    assert groi_verdict(body_text) != "valid", body_text
    assert nif_iva_verdict(body_text) != "valid", body_text


def test_surface_specific_affirmations_stay_surface_specific() -> None:
    """Positive vocabulary is per surface; the negative table is shared.

    A VIES affirmation does not assert Spanish ROI registration, so GROI
    must not read it as ``valid``; the converse holds for GROI's own
    registration phrase.
    """
    assert nif_iva_verdict("NIF-IVA válido") == "valid"
    assert groi_verdict("NIF-IVA válido") == "unknown"

    assert groi_verdict("CONSTA UN OPERADOR INTRACOMUNITARIO") == "valid"
    assert nif_iva_verdict("CONSTA UN OPERADOR INTRACOMUNITARIO") == "unknown"


def test_empty_and_unanswerable_text_is_unknown() -> None:
    assert groi_verdict("") == "unknown"
    assert nif_iva_verdict("") == "unknown"
    assert groi_verdict("Servicio temporalmente no disponible por mantenimiento") == "unknown"


def test_negative_precedence_beats_a_positive_marker_in_the_same_body() -> None:
    """Negative-first precedence, not marker richness, is the safety property."""
    body = "Operador intracomunitario identificado: no consta en el registro"

    assert extract_marker_verdict(body, positive_markers=("operador intracomunitario identificado",)) == "invalid"


def test_every_shared_negative_marker_is_honoured_by_both_checkers() -> None:
    """No checker may quietly drop a marker from the shared table."""
    for marker in SPANISH_NEGATIVE_VERDICT_MARKERS:
        assert groi_verdict(marker) == "invalid", marker
        assert nif_iva_verdict(marker) == "invalid", marker
