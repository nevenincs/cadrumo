"""Modelo 210 devengos of January to May 2022 are answered by projection from 2023.

AEAT publishes a separate design for devengos from 01-01-2022 to 01-06-2022
(aeat-dr-210-2022-hasta-05, vers. 1.5) and one from 01-06-2022 (aeat-dr-210-2022,
vers. 1.6), which the 2023 edition renders. The two print the same records, fields,
positions, widths and contents except that record T21002 prints positions 1285-1391
as two blank "Reservado para la Administracion" fields (35 and 72 bytes) where the
later one prints one of 107. The bytes written are the same, so no edition is
authored for those months and the projection stands.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EARLY = "aeat-dr-210-2022-hasta-05"
_LATE = "aeat-dr-210-2022"
_RESERVED = "Reservado para la Administración"


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("210")


def _rows(source_id: str) -> dict[str, list[tuple[int, int, str, str]]]:
    """Sheet -> [(position, length, type, description)] from the design's workbook sidecar."""
    _, catalogues = _modelo()
    corpus_path = catalogues.sources[source_id].corpus_path
    assert corpus_path is not None
    path = bundled_path("corpus", *corpus_path.removeprefix("corpus/").split("/"))
    sheets: dict[str, list[tuple[int, int, str, str]]] = {}
    sheet = ""
    for line in path.with_name(path.name + ".extracted.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            sheet = line[2:].strip()
            sheets[sheet] = []
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if sheet and len(cells) >= 5 and cells[1].isdigit() and cells[2].isdigit():
            sheets[sheet].append((int(cells[1]), int(cells[2]), cells[3], cells[4]))
    return sheets


def _differing() -> tuple[list[tuple[int, int, str, str]], list[tuple[int, int, str, str]]]:
    """The one sheet whose rows differ: (rows only the early design prints, rows only the late one prints)."""
    early, late = _rows(_EARLY), _rows(_LATE)
    assert early.keys() == late.keys()
    differing = [
        (sorted(set(early[sheet]) - set(late[sheet])), sorted(set(late[sheet]) - set(early[sheet])))
        for sheet in early
        if early[sheet] != late[sheet]
    ]
    assert len(differing) == 1
    return differing[0]


def test_the_two_designs_meet_at_june_2022() -> None:
    _, catalogues = _modelo()
    early, late = catalogues.sources[_EARLY], catalogues.sources[_LATE]
    assert early.applies_to is not None and late.applies_from is not None
    assert early.applies_to + timedelta(days=1) == late.applies_from
    assert early.applies_from == date(late.applies_from.year, 1, 1)


def test_the_designs_differ_only_in_how_a_blank_reserved_run_is_split() -> None:
    only_early, only_late = _differing()
    assert {row[3] for row in only_early + only_late} == {_RESERVED}
    early_span = (min(row[0] for row in only_early), max(row[0] + row[1] for row in only_early))
    late_span = (min(row[0] for row in only_late), max(row[0] + row[1] for row in only_late))
    assert early_span == late_span
    assert (len(only_early), len(only_late)) == (2, 1)


def test_january_to_may_2022_projects_to_the_edition_rendering_the_later_design() -> None:
    modelo, catalogues = _modelo()
    early = catalogues.sources[_EARLY]
    assert early.applies_to is not None
    year = early.applies_to.year
    assert catalogues.supported_filing_years is not None
    assert year in catalogues.supported_filing_years.years
    assert all(_EARLY not in edition.source_refs for edition in modelo.revisions.values())
    ((position, length, _, _),) = _differing()[1]
    for period in ("EVENT-N", "0A"):
        revision = select_revision(modelo, filing_year=year, period=period, support=catalogues.supported_filing_years)
        resolution = revision_temporal_resolution(
            revision, filing_year=year, period=period, support=catalogues.supported_filing_years
        )
        assert resolution.projection_direction is TemporalProjectionDirection.BACKWARD
        assert _LATE in revision.source_refs
        written = [
            field.kind
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if (field.offset, field.length) == (position, length)
        ]
        assert written == ["filler"]
