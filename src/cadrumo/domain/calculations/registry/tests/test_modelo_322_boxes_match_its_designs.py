"""Modelo 322's numbered casillas are exactly the boxes its cited design prints.

WHY MODELO 322 AND NOT EVERY MODELO. This equality only means something where a
casilla's ``number`` IS the box number AEAT prints in the design, and that is not
universal. Modelo 151's 2015 design tags boxes 1..43 while its revision numbers
casillas 58, 103, 235, 279; modelo 308 numbers two declaration-metadata casillas
13 and 109 against a design of twenty boxes. Those are different numbering
universes, not defects, and a registry-wide version of this check reported both
as errors. It is scoped here because for modelo 322 the correspondence was
measured and is exact -- 179, 188 and 189 boxes against 179, 188 and 189 numbered
casillas, across its three revisions.

WHAT IT CAUGHT. Revision ``2008-2023`` carried casilla ``171`` -- operaciones
intragrupo, base imponible -- which appears in the 2024-2025 and 2026 designs and
in NEITHER design that revision cites. It was routed to a ``filler`` slot, so its
value was computed, grounded, and never written. Era bleed: a box from a later
form left behind in an earlier revision. Removing it is what makes the counts
equal.

WHY EQUALITY RATHER THAN CONTAINMENT. Both directions are defects and they are
different ones. A casilla with no box (the 171 case) declares a figure the record
cannot carry. A box with no casilla is the opposite failure -- the record has a
slot the registry cannot fill, which is how modelo 322's box [73] hides in the
2022 design today. Asserting containment either way would license one of them.

The design is the authority: box numbers are read from the bundled file, never
transcribed here, so AEAT renumbering a box moves both sides together.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from .. import bundled_authority, extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A bracketed casilla number as AEAT prints it in a design description.
_TAG = re.compile(r"\[(\d+)\]")
_MODELO = "322"
#: Below this the design was not read and the comparison would be vacuous.
_MINIMUM_BOXES = 100


def _revisions():
    modelo = next(m for m in bundled_authority().modelos if str(m.id) == _MODELO)
    return sorted(modelo.revisions.items())


def _design_boxes(revision) -> set[str]:
    _, catalogues = _committed_registry_tree()
    refs = [ref for ref in (getattr(revision, "source_refs", []) or []) if ref.startswith(f"aeat-dr-{_MODELO}")]
    assert refs, "the revision cites no record design, so there is nothing to compare against"
    boxes: set[str] = set()
    for ref in refs:
        extraction = extract_record_design(bundled_path() / catalogues.sources[ref].corpus_path)
        assert not extraction.skipped, (
            f"{ref} was only partly read ({[s.name for s in extraction.skipped]}); a "
            "missing box could mean an unread sheet rather than a real difference"
        )
        for sheet in extraction.sheets:
            for field in sheet.fields:
                boxes.update(_TAG.findall(field.description or ""))
    return boxes


def _numbered_casillas(revision) -> set[str]:
    return {str(c.number) for c in revision.casillas if str(c.number).isdigit()}


def test_no_revision_declares_a_box_its_design_does_not_print() -> None:
    """The era-bleed direction: a casilla whose figure the record cannot carry."""
    for revision_id, revision in _revisions():
        boxes = _design_boxes(revision)
        assert len(boxes) >= _MINIMUM_BOXES, f"{revision_id}: only {len(boxes)} boxes read; the design was not read"
        stray = sorted(_numbered_casillas(revision) - boxes, key=int)

        assert not stray, (
            f"modelo {_MODELO} revision {revision_id} declares casillas the design it "
            f"cites does not print: {stray}. Check whether they belong to a LATER "
            "design before assuming the design is wrong"
        )


def test_no_design_box_is_left_without_a_casilla() -> None:
    """The opposite direction, which containment alone would license.

    A box the design prints and the registry does not declare is a slot nothing
    can fill. Asserted separately from the check above because the remedy differs:
    that one deletes a casilla, this one authors one.
    """
    for revision_id, revision in _revisions():
        boxes = _design_boxes(revision)
        assert len(boxes) >= _MINIMUM_BOXES

        unclaimed = sorted(boxes - _numbered_casillas(revision), key=int)

        assert not unclaimed, (
            f"modelo {_MODELO} revision {revision_id} cites a design printing boxes it "
            f"declares no casilla for: {unclaimed}"
        )
