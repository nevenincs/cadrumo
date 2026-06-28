"""Focused unit tests for declaracion._detect.detect_template_revision_from_pages.

The detector inspects already-extracted PDF page text and returns a
`TemplateRevision`, keying off:

- Modelo code via ``Modelo: NNN`` header.
- Ejercicio via ``Ejercicio: YYYY`` header (searched across pages 1-2).
- Revision tag: ``{año}.orden-{N}`` (when ``Orden HAC/N/YYYY`` footer
  present) or the ``{ejercicio}.01`` fallback sentinel.

Currently no direct unit-test coverage. A regression in the regex
grammar (e.g., requiring Modelo + Ejercicio on the same line, or
dropping the cross-page-2 search for Modelo 100 pre-2022
justificantes) would silently misclassify or fail to detect
template revisions across operator-imported PDFs.

Tests pin the detection rules; assertions are structural /
detection-contract assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from .._detect import detect_template_revision_from_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_detect_returns_none_for_empty_pages_tuple() -> None:
    assert detect_template_revision_from_pages(()) is None


def test_detect_returns_template_revision_with_header_markers() -> None:
    """Single page with both Modelo and Ejercicio headers — the
    detector returns a TemplateRevision with detected_from='header'."""
    page = "Modelo: 130\nEjercicio: 2025\nOther data follows.\n"

    revision = detect_template_revision_from_pages((page,))

    assert revision is not None
    assert revision.modelo == "130"
    assert revision.año == 2025
    assert revision.detected_from == "header"


def test_detect_returns_none_when_modelo_header_is_missing() -> None:
    page = "Ejercicio: 2025\nOther data follows.\n"

    assert detect_template_revision_from_pages((page,)) is None


def test_detect_returns_none_when_ejercicio_header_is_missing() -> None:
    page = "Modelo: 130\nOther data follows.\n"

    assert detect_template_revision_from_pages((page,)) is None


def test_detect_uses_orden_hac_footer_to_pin_revision_tag() -> None:
    """When the PDF carries an `Orden HAC/819/2024` footer, the
    revision tag uses the year + orden number rather than the
    fallback ``{ejercicio}.01`` sentinel."""
    page = "Modelo: 303\nEjercicio: 2025\nResto del cuerpo...\nAprobado por Orden HAC/819/2024 BOE 30-07-2024.\n"

    revision = detect_template_revision_from_pages((page,))

    assert revision is not None
    assert revision.revision == "2024.orden-819"


def test_detect_falls_back_to_ejercicio_01_when_no_orden_hac() -> None:
    """Without an Orden HAC footer the detector emits the conservative
    ``{ejercicio}.01`` revision tag — registry resolution is then
    responsible for refusing unregistered revisions."""
    page = "Modelo: 130\nEjercicio: 2025\nNo Orden footer here.\n"

    revision = detect_template_revision_from_pages((page,))

    assert revision is not None
    assert revision.revision == "2025.01"


def test_detect_searches_first_two_pages_for_ejercicio_header() -> None:
    """Pre-2022 Modelo 100 justificantes print the
    INFORMACIÓN DE LA PRESENTACIÓN cover page on page 1 and defer
    the Ejercicio marker to page 2; the detector unions pages 1-2
    for the header search."""
    page_one = "Modelo: 100\nINFORMACIÓN DE LA PRESENTACIÓN\n"
    page_two = "Ejercicio: 2021\nDeclaración details.\n"

    revision = detect_template_revision_from_pages((page_one, page_two))

    assert revision is not None
    assert revision.año == 2021


def test_detect_finds_orden_hac_when_only_present_in_last_page_tail() -> None:
    """The Orden HAC regex is searched in the head span first, then
    in the tail of the last page (last 2000 chars). A footer that
    appears only in the tail still pins the revision tag."""
    head_page = "Modelo: 303\nEjercicio: 2025\n" + "body content\n" * 20
    tail_page = "x" * 1500 + "\nAprobado por Orden HAC/100/2024 BOE 2024.\n"

    revision = detect_template_revision_from_pages((head_page, tail_page))

    assert revision is not None
    assert revision.revision == "2024.orden-100"


def test_detect_header_regex_is_case_insensitive() -> None:
    """``modelo:`` / ``EJERCICIO:`` (mixed case) still matches the
    header regexes (compiled with re.IGNORECASE)."""
    page = "modelo: 130\nEJERCICIO: 2025\n"

    revision = detect_template_revision_from_pages((page,))

    assert revision is not None
    assert revision.modelo == "130"
    assert revision.año == 2025
