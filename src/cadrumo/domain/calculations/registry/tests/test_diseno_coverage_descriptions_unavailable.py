"""An empty casilla set must say which of its two causes produced it.

``DisenoCoverageReport.extraction_found_no_casillas`` already tells a reader that a
report carries no coverage information, and its own docstring instructs them to
"distinguish the two by whether the source yielded fields at all". Until
``extracted_fields`` and ``described_fields`` existed the report carried no count
with which to do that, so the instruction could not be followed.

The two causes are genuinely different:

* Modelo 185's Diseño is read in full -- 35 fields carrying thousands of characters
  of real prose -- and declares no numbered box anywhere. Its empty casilla set is
  the correct answer about the form.
* Modelo 038's Diseño is recovered from chart GEOMETRY alone. Every field carries
  the visual-chart type code and a placeholder where the description column would
  be. Casilla tags are only ever recognised inside descriptions, so this source can
  never yield one however many boxes the form prints. Its empty set is an artefact
  of what could be read.

Reported identically, the second reads as the first, and a revision gets credited
with "the form numbers nothing" when the truth is "we could not read it".
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources import bundled_path

from .._loader import load_registry_tree
from .._record_design_coverage import build_diseno_coverage_report

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_GEOMETRY_ONLY = ("038", "2002-y-siguientes", "modelo_038/files/01-038-diseno-de-registro-actualizado-28-06-2024.pdf")
_DESCRIBED = ("185", "2025-y-siguientes", "modelo_185/files/01-185-ejercicio-2026-y-siguientes.pdf")


def _report(modelo_id: str, revision_id: str, relative: str):
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    revision = {definition.id: definition for definition in modelos}[modelo_id].revisions[revision_id]
    path = bundled_path("corpus", "aeat_official", "disenos_registro", *relative.split("/"))
    return build_diseno_coverage_report(path, modelo_id, revision, multi_segment=False)


def test_a_geometry_only_source_reports_its_descriptions_as_unavailable() -> None:
    """Fields were extracted, none carried prose, so no casilla could ever be found."""
    report = _report(*_GEOMETRY_ONLY)

    assert report.extracted_fields > 0, "nothing was extracted, so this proves nothing about descriptions"
    assert report.described_fields == 0
    assert report.descriptions_unavailable is True
    assert report.extraction_found_no_casillas is True


def test_a_fully_described_source_that_numbers_nothing_is_not_reported_as_unreadable() -> None:
    """The empty set here is a statement about the form, not about the parser."""
    report = _report(*_DESCRIBED)

    assert report.described_fields == report.extracted_fields > 0
    assert report.descriptions_unavailable is False
    assert report.extraction_found_no_casillas is True


def test_the_two_causes_are_not_conflated() -> None:
    """Both report an empty casilla set; only one is an extraction artefact."""
    geometry_only = _report(*_GEOMETRY_ONLY)
    described = _report(*_DESCRIBED)

    assert geometry_only.extraction_found_no_casillas == described.extraction_found_no_casillas
    assert geometry_only.descriptions_unavailable != described.descriptions_unavailable, (
        "the flag that separates an unreadable source from a form that numbers "
        "nothing reports the same value for both, so it separates nothing"
    )
