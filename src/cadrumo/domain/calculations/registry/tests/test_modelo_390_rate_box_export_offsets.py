"""Every Modelo 390 rate box writes the record position the official design gives it.

The rate-box casillas state their AEAT box number, and a sibling test pins those
numbers. Nothing pinned the other half of the correspondence: the **offset** each
box occupies inside the exported fixed-width record. That half is where a defect
is invisible, because an offset is a bare integer with no label — a value written
seventeen bytes early lands silently in the neighbouring box, and the file still
has a valid digest and a plausible shape.

This gate reads the bundled AEAT Diseño de Registros and derives the expected
offset for each rate box from the design itself, rather than from a table an
author transcribed. A hand-copied mapping would re-assert whatever the author
misread; parsing the design means the corpus, not the test, is the authority.

SCOPE, deliberately narrow. This checks the fourteen Reg. ordinario rate boxes of
this one revision. It is NOT a general box-number cross-check gate: Modelo 390's
casillas are addressed by semantic id while the design is addressed by box
number, the two sets do not intersect, and a number-keyed gate over the whole
form would report every one of its boxes as missing. The rate block is
checkable precisely because its casillas state their numbers explicitly.

THE SEGMENT MATTERS AND IS THE SUBTLE PART. Every position in this design appears
twice — once under "Reg. ordin." and once under "Recargo de equivalencia", whose
twins are boxes [663]/[664], [691]/[692] and [35]/[36] at the SAME offsets,
written by a separate record. Matching on offset alone would look conclusive and
be ambiguous, so the design rows are filtered to the ordinario segment and the
registry side is filtered to the ``page_02`` record.

Real-behaviour: the committed revision through the real registry authority and
the real bundled corpus file. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path, resources
from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_DESIGN_PARTS = (
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_390",
    "files",
    "16-390-ejercicio-2024-actualizado-18-12-24-544-kb-xlsx.xlsx.extracted.md",
)

# "5. Operaciones Reg. Gral. - Base Imponible y cuota - Reg. ordin. - Tipo 7,5% - Cuota [670]"
_ORDINARIO_ROW = re.compile(r"Tipo ([\d,]+)% - (Base imponible|Cuota) \[(\d+)\]")

_ORDINARIO_SEGMENT = "Reg. ordin."
_RECARGO_SEGMENT = "Recargo de equivalencia"

_BOX_RECORD_TYPE = "page_02"
_CASILLA_PREFIX = "iva.anual.repercutido.tipo-"


def _m390_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("390", filing_year=2024, period="0A").revision


def _design_text() -> str:
    return bundled_path(*_DESIGN_PARTS).read_text(encoding="utf-8")


def _design_rate_positions(segment: str) -> dict[int, tuple[str, str, str]]:
    """Map record offset -> (rate, base|cuota, box number) for one régimen segment.

    Derived from the bundled design rather than transcribed, so the corpus is the
    authority and a misreading by this module's author cannot survive.
    """
    positions: dict[int, tuple[str, str, str]] = {}
    for line in _design_text().splitlines():
        if segment not in line:
            continue
        matched = _ORDINARIO_ROW.search(line)
        if matched is None:
            continue
        columns = [column.strip() for column in line.split("|")]
        try:
            offset = int(columns[1])
        except (IndexError, ValueError):
            continue
        rate = matched.group(1).replace(",", "-")
        half = "base" if matched.group(2).startswith("Base") else "cuota"
        positions[offset] = (rate, half, matched.group(3))
    return positions


def _registry_rate_fields() -> dict[int, str]:
    """Map record offset -> casilla id for every rate-box field of the box record."""
    revision = _m390_revision()
    fields: dict[int, str] = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            if record.record_type != _BOX_RECORD_TYPE:
                continue
            for field in record.fields:
                if field.offset is not None and field.casilla_id and field.casilla_id.startswith(_CASILLA_PREFIX):
                    fields[field.offset] = field.casilla_id
    return fields


def test_the_design_yields_the_fourteen_ordinario_rate_positions() -> None:
    """Guard the parser itself: a silent regex miss would make every check vacuous.

    If the corpus file is renamed, re-extracted in another shape, or the pattern
    stops matching, the comparisons below would pass over an empty mapping and
    assert nothing at all. This fails loudly instead.
    """
    positions = _design_rate_positions(_ORDINARIO_SEGMENT)
    assert len(positions) == 14, f"parsed {len(positions)} ordinario rate rows from the design, expected 14"
    assert {half for _, half, _ in positions.values()} == {"base", "cuota"}


def test_every_rate_box_field_writes_its_official_record_position() -> None:
    """Each rate box writes exactly where the official design puts that rate.

    The failure this catches is silent: an offset is an unlabelled integer, so a
    value written at a neighbouring rate's position produces a structurally valid
    record declaring a false breakdown.
    """
    design = _design_rate_positions(_ORDINARIO_SEGMENT)
    registry = _registry_rate_fields()
    assert len(registry) == 14, f"the box record writes {len(registry)} rate fields, expected 14"

    for offset, casilla_id in sorted(registry.items()):
        assert offset in design, f"{casilla_id} writes offset {offset}, which is no rate position in the design"
        expected_rate, expected_half, box = design[offset]
        tier, _, half = casilla_id.removeprefix(_CASILLA_PREFIX).rpartition(".")
        assert tier == expected_rate and half == expected_half, (
            f"offset {offset} is box [{box}] 'Tipo {expected_rate}% - {expected_half}' in the design, "
            f"but the registry writes {casilla_id} there"
        )


def test_the_recargo_segment_reuses_the_same_positions_under_different_boxes() -> None:
    """Why the segment filter is load-bearing rather than defensive.

    The Recargo de equivalencia rows occupy the SAME record positions as the
    ordinario rows and carry entirely different box numbers, written by a
    separate record. A cross-check that matched on offset alone would appear
    conclusive while being ambiguous, so this pins the collision explicitly: if
    the segments ever stopped sharing positions, the filter above would be
    unnecessary and this test says so.
    """
    ordinario = _design_rate_positions(_ORDINARIO_SEGMENT)
    recargo = _design_rate_positions(_RECARGO_SEGMENT)
    shared = set(ordinario) & set(recargo)
    assert shared, "the two régimen segments no longer share record positions"
    for offset in sorted(shared):
        assert ordinario[offset][2] != recargo[offset][2], (
            f"offset {offset} carries box {ordinario[offset][2]} in both segments; "
            "the segments are supposed to be distinguished by their box numbers"
        )


def test_no_rate_position_is_written_twice() -> None:
    """Two fields at one offset means one silently overwrites the other.

    The retired rate-blind tier casillas used to write offsets 98, 200 and 234.
    If a flip left those fields in place beside the box-layer fields, the record
    would carry two writers for one position.
    """
    revision = _m390_revision()
    for layout in revision.export_layouts:
        for record in layout.records:
            offsets = [field.offset for field in record.fields if field.offset is not None]
            duplicated = {offset for offset in offsets if offsets.count(offset) > 1}
            assert not duplicated, f"record {record.record_type} writes offsets {sorted(duplicated)} twice"
