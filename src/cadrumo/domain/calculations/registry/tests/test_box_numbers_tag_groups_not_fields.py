"""A printed box number tags a logical GROUP, not every field in it.

AEAT numbers a box once and lets it span several physical positions. Modelo
840's ``Pág. 1`` shows it plainly around the sujeto pasivo's address::

    @213+2   [11]  Apart. I: ... Provincia. [11]
    @215+5   [10]  Apart. I: ... Municipio. [10]
    @220+30        Apart. I: ... Municipio          <- same concept, NO tag
    @250+6         Reservado ... Cod. M             <- reserved, no tag
    @256+5   [12]  Apart. I: ... Cód. Postal. [12]

The number sits on the CODE field and the adjacent NAME field carries none,
while the registry declares a single ``sujeto.domicilio-municipio`` casilla
numbered 10.

WHY THIS MODULE EXISTS. A coverage measure was built on the obvious join --
count a design field as covered when its OWN text carries a tag matching some
casilla's number -- and used to conclude that three revisions awaiting a layout
had hundreds of data fields no casilla covers, and therefore needed casillas
authored before a map. That conclusion was withdrawn: the join under-counts by
construction, because every untagged sibling of a tagged field scores as
uncovered no matter how well the registry models it.

HOW BIG THE ERROR IS, measured rather than assumed. On this sheet 15 of 106
fields carry no tag, so the join is wrong about a minority, not a majority --
and that is enough, because those few were read as hundreds once summed across
four modelos and several sheets. Of the seven non-structural ones here, at least
four correspond to casillas the registry already declares:
``sujeto.domicilio-municipio``, ``representante.domicilio-municipio``,
``local-indirecto.municipio`` and ``act.codigo-provincia``.

WHAT CANNOT BE MEASURED THIS WAY. Which physical position a casilla occupies is
recorded only by an export layout, and these revisions have none -- that is why
they are on the worklist. So until a layout exists there is NO mechanical
field-to-casilla coverage measure for them, and a tag join must not be
substituted for one. That is the whole finding, and this module fixes the
evidence for it so the same shortcut is not rebuilt.

The sibling module ``test_casilla_number_is_printed_by_its_design`` is
unaffected and still sound: it runs the other direction, asking whether each
casilla's declared number appears ANYWHERE in the design, which needs no
per-field attribution.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from ..authority import bundled_authority
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TAG = re.compile(r"\[(\d+)\]")
_DESIGN = "aeat-dr-840"
_SHEET_SUFFIX = "1"


def _page_one_fields():
    _modelos, catalogues = _committed_registry_tree()
    design = extract_record_design(bundled_path() / catalogues.sources[_DESIGN].corpus_path)
    sheet = next(s for s in design.sheets if s.name.strip().endswith(_SHEET_SUFFIX))
    return sheet, sorted(sheet.fields, key=lambda field: field.offset)


def test_the_sheet_is_read_whole_so_the_evidence_is_trustworthy() -> None:
    sheet, fields = _page_one_fields()

    occupied: set[int] = set()
    for field in fields:
        occupied |= set(range(field.offset, field.offset + field.length))
    unwritten = sorted(set(range(1, (sheet.total_positions or 0) + 1)) - occupied)

    assert not unwritten, unwritten[:8]


def test_an_untagged_field_shares_its_concept_with_a_tagged_neighbour() -> None:
    """The pattern that breaks a per-field tag join, shown on the worked case.

    The municipio NAME at 220 carries no number while the municipio CODE
    immediately before it carries ``[10]``, and both describe the same concept.
    A join keyed on the field's own text scores the name as uncovered.
    """
    _sheet, fields = _page_one_fields()

    by_offset = {field.offset: field for field in fields}
    tagged = by_offset.get(215)
    untagged = by_offset.get(220)
    assert tagged is not None and untagged is not None, sorted(by_offset)[:12]

    assert _TAG.findall(tagged.description or "") == ["10"], tagged.description
    assert not _TAG.findall(untagged.description or ""), untagged.description
    assert "municipio" in (tagged.description or "").casefold()
    assert "municipio" in (untagged.description or "").casefold()


def test_the_registry_models_that_concept_with_a_casilla_all_the_same() -> None:
    """So the untagged field is not evidence of a modelling gap.

    This is the step the withdrawn measure got wrong: it read the missing tag as
    a missing casilla.
    """
    revision = next(m for m in bundled_authority().modelos if m.id == "840").revisions["2003-y-siguientes"]

    municipio = [c for c in revision.casillas if str(c.id) == "sujeto.domicilio-municipio"]

    assert municipio, [str(c.id) for c in revision.casillas][:10]
    assert municipio[0].number == "10"
