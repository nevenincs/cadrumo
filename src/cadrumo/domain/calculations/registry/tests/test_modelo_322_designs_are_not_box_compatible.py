"""Modelo 322's 2022 and 2023 designs each number a box the other does not.

WHY THIS MATTERS. Revision ``2008-2023`` covers both ejercicios and carries ONE
casilla set and ONE export layout, both authored against the 2023 design. That is
only defensible if the two designs agree about which boxes exist. They do not:
2023 adds fifteen boxes, and 2022 carries ``[73]`` -- "Operaciones no sujetas o
con inversion del sujeto pasivo que originan el derecho a deduccion (hasta 30 de
junio, resto a 0)" -- which 2023 drops entirely.

A box only one side declares cannot be carried by the other layout at all. No
offset comparison, length check or digest sees it, because nothing MOVED; the box
simply is not there. That makes this the premise the 2022/2023 split rests on,
and the reason the split cannot be satisfied by re-pointing a source reference.

WHAT THIS FILE DOES NOT ASSERT, DELIBERATELY. It says nothing about the registry's
casilla set. The revision spanning both ejercicios today declares casillas for all
fifteen 2023-only boxes and none for ``[73]``, so a 2022 filing omits that figure
silently -- but asserting that asymmetry here would encode a live defect as the
contract. The defect belongs in the split that fixes it, not in a green test.

DIRECTION IS ASSERTED SEPARATELY. The 2022-only direction is the one that is hard
to see and easy to lose: the registry was authored to 2023, so a reader checking
"does every declared box exist in the design?" finds nothing wrong. Only the
reverse question -- does every DESIGN box have a home? -- surfaces ``[73]``.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources.bundled_data import bundled_path
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A bracketed casilla number as AEAT prints it in a design description.
_TAG = re.compile(r"\[(\d+)\]")
_EARLIER = "aeat-dr-322-2022"
_LATER = "aeat-dr-322-2023"
#: Below this the design was not read and every set comparison would be vacuous.
_MINIMUM_BOXES = 100


def _numbered_boxes(source_ref: str) -> set[str]:
    _, catalogues = _committed_registry_tree()
    extraction = extract_record_design(bundled_path() / catalogues.sources[source_ref].corpus_path)
    assert not extraction.skipped, (
        f"{source_ref} was only partly read ({[s.name for s in extraction.skipped]}), "
        "so an absent box could mean an unread sheet rather than a real difference"
    )
    boxes: set[str] = set()
    for sheet in extraction.sheets:
        for field in sheet.fields:
            boxes.update(_TAG.findall(field.description or ""))
    assert len(boxes) >= _MINIMUM_BOXES, f"only {len(boxes)} boxes read from {source_ref}; the design was not read"
    return boxes


def test_the_earlier_design_numbers_a_box_the_later_one_drops() -> None:
    """The direction the registry cannot see, because it was authored to 2023."""
    earlier = _numbered_boxes(_EARLIER)
    later = _numbered_boxes(_LATER)

    dropped = sorted(earlier - later, key=int)

    assert dropped, (
        "the 2022 design no longer carries any box the 2023 design lacks. If AEAT's "
        "corpus or this parser changed, the 2022/2023 split rests on a premise that "
        "no longer holds and must be re-derived rather than assumed"
    )


def test_the_later_design_numbers_boxes_the_earlier_one_lacks() -> None:
    """The other direction, asserted so the difference is proved MUTUAL.

    Without it, a single-direction check would still pass if 2022's box set were a
    strict superset of 2023's, which is a different relationship needing a
    different remedy.
    """
    earlier = _numbered_boxes(_EARLIER)
    later = _numbered_boxes(_LATER)

    added = sorted(later - earlier, key=int)

    assert added, "the 2023 design adds no box, so the two differ in only one direction"


def test_the_two_designs_are_not_interchangeable() -> None:
    """The conclusion the split rests on, stated once and directly.

    Kept separate from the two directional checks because this is the claim other
    work cites: ONE casilla set cannot serve both ejercicios. Asserted as set
    inequality rather than as a count, so it survives AEAT renumbering a box.
    """
    assert _numbered_boxes(_EARLIER) != _numbered_boxes(_LATER), (
        "the two designs declare the same boxes, so one revision could serve both and the split would be unnecessary"
    )
