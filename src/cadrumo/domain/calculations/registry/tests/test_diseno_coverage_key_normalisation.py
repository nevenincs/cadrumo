"""The Diseño coverage inventory must compare the two sides on the same key.

The report contrasts the box numbers a design prints against the boxes the
registry declares. Both halves of that key are written differently on the two
sides, and comparing them verbatim made the inventory report authored work as
missing: modelo 714 scored 0 of 120 covered while declaring 85 numeric casillas,
because the design writes the sheet name ``714-01 Patrimonio`` where the registry
declares ``714-01``, and the design prints ``1`` where the registry pads ``01``.

The report is advisory and never a load gate, which is exactly why this matters:
a gap count that reads "nothing authored" for a mostly-authored revision is an
advisory nobody can act on. These tests pin the correspondence to the SOURCE
rather than to a count, so a modelo gaining or losing boxes does not rewrite
them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .._record_design_coverage import (
    _normalised_box_number,
    _segmento_addresses_sheet,
    build_diseno_coverage_report,
)
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _coverage_report(modelo_id: str, revision_id: str):
    modelo, catalogues = _committed_modelo(modelo_id)
    revision = modelo.revisions[revision_id]
    design_refs = [
        ref
        for ref in revision.source_refs
        if (source := catalogues.sources.get(ref)) is not None and source.kind == "record_design"
    ]
    assert design_refs, f"{modelo_id}/{revision_id} cites no record design to measure against"

    source = catalogues.sources[design_refs[0]]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path
    assert path.exists(), f"{source.id} is not readable at {path}"

    multi_segment = any(getattr(casilla, "segmento", None) for casilla in revision.casillas)
    return revision, build_diseno_coverage_report(path, modelo_id, revision, multi_segment=multi_segment)


def test_a_padded_box_number_is_the_same_box_as_the_bare_numeral() -> None:
    assert _normalised_box_number("01") == _normalised_box_number("1")
    assert _normalised_box_number("00016") == _normalised_box_number("16")
    assert _normalised_box_number("0") == "0"


def test_a_position_range_is_never_normalised_into_a_box_number() -> None:
    """Ranges are a different AXIS, so normalising them would manufacture matches.

    Without this the helper could be "fixed" into stripping a range down to its
    first component, which would report byte positions as covered boxes and turn
    a real gap into a clean inventory.
    """
    for value in ("124-173", "107-108", "78-79", "ejercicio", ""):
        assert _normalised_box_number(value) == value.strip()


def test_a_segmento_addresses_its_sheet_only_to_a_word_boundary() -> None:
    assert _segmento_addresses_sheet("714-01", "714-01 Patrimonio")
    assert _segmento_addresses_sheet("DP200012", "DP200012")
    # The reason this is not a bare startswith: 714-1 must not claim 714-10.
    assert not _segmento_addresses_sheet("714-1", "714-10 Patrimonio")
    assert not _segmento_addresses_sheet("714-01", "714-02 Patrimonio")


@pytest.mark.parametrize("revision_id", ["2021", "2025"])
def test_modelo_714_declared_boxes_are_reported_covered(revision_id: str) -> None:
    """Every box modelo 714 declares under a sheet the design prints must be covered.

    Asserted as a relationship rather than a tally: a revision that gains or
    loses a box changes the count but not the property.
    """
    revision, report = _coverage_report("714", revision_id)

    declared = {
        (casilla.segmento, _normalised_box_number(casilla.form_number or casilla.number))
        for casilla in revision.casillas
        if str(casilla.form_number or casilla.number or "").isdigit()
    }
    assert declared, "714 must declare numeric boxes for this test to mean anything"

    unreported = [
        gap
        for gap in report.coverage_gap_casillas
        if any(
            _segmento_addresses_sheet(segmento, gap.segmento) and number == _normalised_box_number(gap.number)
            for segmento, number in declared
        )
    ]
    assert not unreported, (
        "these boxes are declared by the registry under the design's own sheet yet "
        f"reported as gaps: {[(g.segmento, g.number) for g in unreported[:8]]}"
    )
    assert report.covered_count > 0, "the inventory must find the declared boxes it was given"


def test_modelo_151_position_keyed_casillas_stay_uncovered() -> None:
    """The normalisation must not paper over a genuine axis difference.

    Modelo 151 declares byte-position ranges, not box numbers. Its coverage is
    honestly near zero and must STAY near zero: a change that made it look
    covered would be manufacturing matches across incommensurable axes, which is
    the failure this whole module guards against.
    """
    revision, report = _coverage_report("151", "2015-2022")

    ranged = [
        casilla for casilla in revision.casillas if "-" in str(casilla.form_number or casilla.number or "")
    ]
    assert len(ranged) > len(revision.casillas) // 2, "151 must be position-keyed for this test to mean anything"
    assert report.coverage_gap_count > report.covered_count, (
        "151's design boxes cannot be covered by position ranges; a high covered "
        "count here means the comparison started matching across axes"
    )
