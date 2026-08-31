"""Where a casilla's number IS a printed box number, the two sets must match exactly.

WHY THIS IS A DECLARED SET AND NOT EVERY MODELO. The equality only means anything
where a casilla's ``number`` is the number AEAT prints in the diseno, and that is
not universal. Modelo 151's 2015 design tags boxes 1..43 while its revision
numbers casillas 58, 103, 235, 279; modelo 308 numbers two declaration-metadata
casillas 13 and 109 against a design of twenty boxes. Those are different
numbering universes, not defects, and a registry-wide version of this check
reported both as errors. Each modelo below was measured before being enrolled.

WHY THE LAYOUT'S DESIGN, NOT THE REVISION'S ``source_refs``. A revision may cite
several designs -- modelo 200's cites both the 2024 and the 2025 edition -- but
its export layout writes against exactly one, and that is the design its casilla
set must match. Keying on ``source_refs`` would compare the boxes against a union
of two eras and could not fail on a revision built entirely on the later one.

WHAT IT CAUGHT. Modelo 322's revision carried casilla ``171`` -- operaciones
intragrupo, base imponible -- which appears in the 2024-2025 and 2026 designs and
in neither design that revision cites, routed to a ``filler`` slot so its value
was computed and never written. Era bleed, invisible to every other check.

WHY EQUALITY RATHER THAN CONTAINMENT. Both directions are defects and they are
different ones. A casilla with no box declares a figure the record cannot carry.
A box with no casilla is a slot nothing can fill. Asserting containment either
way would license one of them.

A BRACKETED NUMBER IS NOT ALWAYS THE FIELD'S OWN BOX. AEAT sometimes labels a
computed field with its FORMULA instead of its number: modelo 123's 2019-2023
design prints ``Suma de retenciones e ingresos a cuenta y regularizacion. [03] +
[05]`` at the slot that IS box 06, so 06 never appears as a tag while 03 and 05
appear away from their own fields. Read naively that modelo shows one stray
casilla -- and the casilla is correct; the reading is not. Modelo 123 is
therefore NOT enrolled. The enrolled modelos are unaffected because an operand
is itself a real box elsewhere in the same design and so is already in the set;
the failure only appears where a field's own number is printed nowhere.

THE KEY IS THE BRACKET, AND THAT MATTERS. AEAT prints a box number bracketed --
``Bonificacion personal investigador (RD 475/2014) [00065]``. Reading bare digit
runs instead is wrong in both directions and was measured to be: a 5-digit rule
misses real 4-digit boxes such as ``[1501]``, and a 4-or-5-digit rule swallows
every year printed in prose, inventing 28 phantom boxes for modelo 200 out of
``Detalle compensacion bases imponibles negativas - 2015 -``. Leading zeros are
stripped so ``[00065]`` and casilla ``65`` compare equal.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources.bundled_data import bundled_path
from ..authority import bundled_authority
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A bracketed casilla number as AEAT prints it in a design description.
_TAG = re.compile(r"\[(\d+)\]")

#: Modelos whose casilla numbers ARE their design's printed box numbers, each
#: verified by measurement before enrolment. Not a suppression list: adding a
#: modelo here subjects it to the check, it does not excuse it.
_BOX_NUMBERED_MODELOS: dict[str, str] = {
    "117": "measured exact on every revision carrying a layout",
    "130": "measured exact on every revision carrying a layout",
    "131": "measured exact on every revision carrying a layout",
    "200": "measured exact: 3427 numbered casillas against 3427 bracketed boxes",
    "202": "measured exact on every revision carrying a layout",
    "210": "measured exact on every revision carrying a layout",
    "222": "measured exact on every revision carrying a layout",
    "322": "measured exact on all four revisions (165, 179, 188, 189 boxes)",
    "341": "measured exact on every revision carrying a layout",
    "353": "measured exact on every revision carrying a layout",
    "490": "measured exact on every revision carrying a layout",
    "604": "measured exact on every revision carrying a layout",
    "714": "measured exact on every revision carrying a layout",
}
#: A design that yields NO boxes was not read, and the comparison would be
#: vacuous. Deliberately not a numeric floor: modelo 117 carries 11 boxes and
#: modelo 200 carries 3,427, so any fixed threshold either passes vacuously for
#: the large ones or fails honestly-small designs. Emptiness is the property that
#: actually distinguishes "unread" from "small"; the extraction's own
#: ``skipped`` check below covers the partially-read case.


def _subjects():
    subjects = []
    for modelo in bundled_authority().modelos:
        if str(modelo.id) not in _BOX_NUMBERED_MODELOS:
            continue
        for revision_id, revision in sorted(modelo.revisions.items()):
            if revision.export_layouts:
                subjects.append((str(modelo.id), revision_id, revision))
    return subjects


def _layout_design_boxes(modelo_id: str, revision) -> set[str]:
    """Return the bracketed box numbers of the design the LAYOUT writes against."""
    _, catalogues = _committed_registry_tree()
    refs = [r for r in revision.export_layouts[0].source_refs if r.startswith(f"aeat-dr-{modelo_id}")]
    assert len(refs) == 1, f"a layout must write against exactly one design, got {refs}"
    extraction = extract_record_design(bundled_path() / catalogues.sources[refs[0]].corpus_path)
    assert not extraction.skipped, (
        f"{refs[0]} was only partly read ({[s.name for s in extraction.skipped]}); an "
        "absent box could mean an unread sheet rather than a real difference"
    )
    boxes: set[str] = set()
    for sheet in extraction.sheets:
        for field in sheet.fields:
            for tag in _TAG.findall(field.description or ""):
                boxes.add(tag.lstrip("0") or "0")
    return boxes


def _numbered_casillas(revision) -> set[str]:
    return {str(c.number).lstrip("0") or "0" for c in revision.casillas if str(c.number).isdigit()}


def test_no_revision_declares_a_box_its_layout_design_does_not_print() -> None:
    """The era-bleed direction: a casilla whose figure the record cannot carry."""
    subjects = _subjects()
    assert subjects, "no enrolled modelo carried an export layout; nothing was checked"

    for modelo_id, revision_id, revision in subjects:
        boxes = _layout_design_boxes(modelo_id, revision)
        assert boxes, f"{modelo_id}/{revision_id}: the design yielded no boxes; it was not read"
        stray = sorted(_numbered_casillas(revision) - boxes, key=int)

        assert not stray, (
            f"modelo {modelo_id} revision {revision_id} declares casillas its layout's "
            f"design does not print: {stray}. Check whether they belong to a LATER "
            "design before assuming the design is wrong"
        )


def test_no_design_box_is_left_without_a_casilla() -> None:
    """The opposite direction, which containment alone would license."""
    for modelo_id, revision_id, revision in _subjects():
        boxes = _layout_design_boxes(modelo_id, revision)
        assert boxes, f"{modelo_id}/{revision_id}: the design yielded no boxes; it was not read"

        unclaimed = sorted(boxes - _numbered_casillas(revision), key=int)

        assert not unclaimed, (
            f"modelo {modelo_id} revision {revision_id} writes against a design printing "
            f"boxes it declares no casilla for: {unclaimed}"
        )


def test_every_enrolled_modelo_states_why_it_qualifies() -> None:
    """An entry without its measurement is an assertion nobody checked.

    The premise is modelo-specific, so the reason each modelo qualifies has to
    travel with it -- otherwise the next author enrols one whose numbers are not
    box numbers and the check starts reporting a correct registry as broken.
    """
    thin = sorted(m for m, why in _BOX_NUMBERED_MODELOS.items() if len(why.strip()) < 25)
    assert not thin, f"these entries state no measurement: {thin}"

    enrolled = {m for m, _, _ in _subjects()}
    assert enrolled == set(_BOX_NUMBERED_MODELOS), (
        "every enrolled modelo must actually be reached by the walk; "
        f"declared {sorted(_BOX_NUMBERED_MODELOS)} but checked {sorted(enrolled)}"
    )
