"""An empty casilla set must say how completely its source was read.

``DisenoCoverageReport.extraction_found_no_casillas`` tells a reader that a report
carries no coverage information, and its own docstring instructs them to
"distinguish the two by whether the source yielded fields at all". Until
``extracted_fields`` and ``described_fields`` existed the report carried no count
with which to do that.

**This module previously overstated the distinction and is corrected.** It claimed a
chart-geometry design "can never yield a casilla however many boxes the form
prints", because tags live only in descriptions. That is false twice over:
``_sheet_record_numbers`` scans ``description``, ``validation`` and ``content``, and
the geometry fallback DOES populate ``description`` -- modelo 038's 58 fields each
carry one. Its descriptions were scanned and held no tag.

The true difference is one of evidential weight, and it is still worth recording:

* Modelo 185 is text-parsed in full -- 35 fields carrying thousands of characters of
  content prose -- and numbers nothing. Strong evidence about the form.
* Modelo 038 is recovered from chart geometry, so the long per-field content column
  is absent and only the short description labels were available to scan. A tag
  written only in that prose would be missed. Weaker evidence, same empty result.

Reported identically, the second reads as strongly as the first.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from ..loader import load_registry_tree
from ..record_design_coverage import build_diseno_coverage_report

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_GEOMETRY_ONLY = ("038", "2024-desde-06", "modelo_038/files/01-038-diseno-de-registro-actualizado-28-06-2024.pdf")
_DESCRIBED = ("185", "2025-y-siguientes", "modelo_185/files/01-185-ejercicio-2026-y-siguientes.pdf")


def _report(modelo_id: str, revision_id: str, relative: str):
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    revision = {definition.id: definition for definition in modelos}[modelo_id].revisions[revision_id]
    path = bundled_path("corpus", "aeat_official", "disenos_registro", *relative.split("/"))
    return build_diseno_coverage_report(path, modelo_id, revision, multi_segment=False)


def test_a_geometry_only_source_reports_how_it_was_recovered() -> None:
    """Fields were extracted, none carried the design's own content column."""
    report = _report(*_GEOMETRY_ONLY)

    assert report.extracted_fields > 0, "nothing was extracted, so this proves nothing about descriptions"
    assert report.described_fields == 0
    assert report.recovered_from_chart_geometry is True
    assert report.extraction_found_no_casillas is True


def test_a_text_parsed_source_that_numbers_nothing_is_not_flagged_as_degraded() -> None:
    """The empty set here is strong evidence about the form."""
    report = _report(*_DESCRIBED)

    assert report.described_fields == report.extracted_fields > 0
    assert report.recovered_from_chart_geometry is False
    assert report.extraction_found_no_casillas is True


def test_the_two_readings_are_not_conflated() -> None:
    """Both report an empty casilla set; only one rests on a complete parse."""
    geometry_only = _report(*_GEOMETRY_ONLY)
    described = _report(*_DESCRIBED)

    assert geometry_only.extraction_found_no_casillas == described.extraction_found_no_casillas
    assert geometry_only.recovered_from_chart_geometry != described.recovered_from_chart_geometry, (
        "the flag that separates a geometry-recovered source from a fully "
        "text-parsed one reports the same value for both, so it separates nothing"
    )
