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
from ..groi_check import _POSITIVE_MARKERS as _GROI_POSITIVE_MARKERS
from ..nif_iva_check import _POSITIVE_MARKERS as _NIF_IVA_POSITIVE_MARKERS

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
    assert extract_marker_verdict(body_text, positive_markers=_GROI_POSITIVE_MARKERS) == "invalid", body_text
    assert extract_marker_verdict(body_text, positive_markers=_NIF_IVA_POSITIVE_MARKERS) == "invalid", body_text


@pytest.mark.parametrize("body_text", SPANISH_NEGATIVE_RESPONSES)
def test_no_negative_response_is_ever_reported_valid(body_text: str) -> None:
    """The safety property: an AEAT rejection must never read as a pass."""
    assert extract_marker_verdict(body_text, positive_markers=_GROI_POSITIVE_MARKERS) != "valid", body_text
    assert extract_marker_verdict(body_text, positive_markers=_NIF_IVA_POSITIVE_MARKERS) != "valid", body_text


def test_surface_specific_affirmations_stay_surface_specific() -> None:
    """Positive vocabulary is per surface; the negative table is shared.

    A VIES affirmation does not assert Spanish ROI registration, so GROI
    must not read it as ``valid``; the converse holds for GROI's own
    registration phrase.
    """
    assert extract_marker_verdict("NIF-IVA válido", positive_markers=_NIF_IVA_POSITIVE_MARKERS) == "valid"
    assert extract_marker_verdict("NIF-IVA válido", positive_markers=_GROI_POSITIVE_MARKERS) == "unknown"

    assert (
        extract_marker_verdict("CONSTA UN OPERADOR INTRACOMUNITARIO", positive_markers=_GROI_POSITIVE_MARKERS)
        == "valid"
    )
    assert (
        extract_marker_verdict("CONSTA UN OPERADOR INTRACOMUNITARIO", positive_markers=_NIF_IVA_POSITIVE_MARKERS)
        == "unknown"
    )


def test_empty_and_unanswerable_text_is_unknown() -> None:
    assert extract_marker_verdict("", positive_markers=_GROI_POSITIVE_MARKERS) == "unknown"
    assert extract_marker_verdict("", positive_markers=_NIF_IVA_POSITIVE_MARKERS) == "unknown"
    assert (
        extract_marker_verdict(
            "Servicio temporalmente no disponible por mantenimiento",
            positive_markers=_GROI_POSITIVE_MARKERS,
        )
        == "unknown"
    )


def test_negative_precedence_beats_a_positive_marker_in_the_same_body() -> None:
    """Negative-first precedence, not marker richness, is the safety property."""
    body = "Operador intracomunitario identificado: no consta en el registro"

    assert extract_marker_verdict(body, positive_markers=("operador intracomunitario identificado",)) == "invalid"


def test_every_shared_negative_marker_is_honoured_by_both_checkers() -> None:
    """No checker may quietly drop a marker from the shared table."""
    for marker in SPANISH_NEGATIVE_VERDICT_MARKERS:
        assert extract_marker_verdict(marker, positive_markers=_GROI_POSITIVE_MARKERS) == "invalid", marker
        assert extract_marker_verdict(marker, positive_markers=_NIF_IVA_POSITIVE_MARKERS) == "invalid", marker
