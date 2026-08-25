"""A design an export layout is authored against must not contradict itself.

An export layout encodes byte offsets read out of a bundled AEAT record design.
If that design's extraction disagrees with itself about where a field starts or
ends, every offset taken from it is taken from a reading the design does not
support -- and nothing downstream can tell, because the layout will still be the
right length and still produce a valid digest.

WHAT IS NOT A CONTRADICTION, and why the naive form of this check is wrong.
Fields sharing bytes is ordinary. An amount decomposed into ``ENTERO`` and
``DECIMAL`` parts covers the same span as its components, and a section heading
spans the fields printed beneath it. Both are CONTAINMENT: one field's span
encloses the other's. Measured over the corpus, 154 sheets carry overlap of that
kind and every one of them is legitimate.

WHAT IS. A PARTIAL overlap -- two fields sharing bytes where neither contains
the other -- cannot be a decomposition or a heading. It is the extraction
placing one of the two wrongly. Measured over the 77 designs an export layout
cites, across 404 sheets: zero. The property holds today for everything anything
is authored against, which is what makes it a gate rather than a worklist.

The corpus does contain a design that violates it, and the anchor below pins it
so this is not a rule proven only by synthetic mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from ..export import derive_export_layouts_from_bindings
from .._record_design_coverage import _extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The bundled design known to contradict itself, which anchors the detector
#: against a REAL defect rather than a constructed one. Its PDF is recovered
#: from chart geometry and its columns come back mirrored -- ``PERIODO`` reads
#: ``ODOIREP``, ``SUBCLAVE`` reads ``EVALCBUS`` -- and the same pass misplaces
#: field bounds. Nothing cites it for a layout, which is the state this module
#: exists to keep true.
_KNOWN_SELF_CONTRADICTING_DESIGN = "aeat-dr-038-2024"


@dataclass(frozen=True)
class _Bounds:
    start: int
    end: int
    description: str


def _bounds(sheet) -> list[_Bounds]:
    placed = [
        _Bounds(field.offset, field.offset + (field.length or 1) - 1, (field.description or "")[:40])
        for field in sheet.fields
        if field.offset is not None
    ]
    placed.sort(key=lambda b: (b.start, -(b.end - b.start)))
    return placed


def _partial_overlaps(sheet) -> list[str]:
    """Return pairs sharing bytes where neither span contains the other."""
    found: list[str] = []
    placed = _bounds(sheet)
    for index, first in enumerate(placed):
        for second in placed[index + 1 :]:
            if second.start > first.end:
                break
            contains = (first.start <= second.start and second.end <= first.end) or (
                second.start <= first.start and first.end <= second.end
            )
            if not contains:
                found.append(
                    f"@{first.start}..{first.end} {first.description!r} vs "
                    f"@{second.start}..{second.end} {second.description!r}"
                )
    return found


def _sheets_for(source) -> tuple:
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path
    if not path.exists():
        return ()
    return _extract_record_design(path)


def _cited_design_ids(modelos, catalogues) -> set[str]:
    cited: set[str] = set()
    for definition in modelos:
        for revision in definition.revisions.values():
            if not revision.export_layouts:
                continue
            for layout in derive_export_layouts_from_bindings(revision):
                for ref in layout.source_refs:
                    source = catalogues.sources.get(ref)
                    if source is not None and source.kind == "record_design":
                        cited.add(ref)
    return cited


def test_no_design_an_export_layout_cites_contradicts_its_own_field_bounds() -> None:
    modelos, catalogues = _committed_registry_tree()
    cited = _cited_design_ids(modelos, catalogues)
    assert cited, "no export layout cites a record design, so this gate would prove nothing"

    failures: list[str] = []
    checked_sheets = 0
    for source_id in sorted(cited):
        for sheet in _sheets_for(catalogues.sources[source_id]):
            checked_sheets += 1
            for pair in _partial_overlaps(sheet):
                failures.append(f"{source_id} | {sheet.name}: {pair}")

    assert checked_sheets, "no cited design was readable, so nothing was measured"
    assert not failures, (
        "these designs place two fields across the same bytes without either containing "
        "the other, so an offset authored from them is authored from a reading the design "
        f"does not support: {failures[:8]}"
    )


def test_the_detector_still_finds_the_known_self_contradicting_design() -> None:
    """The rule is anchored on a real corpus defect, not on a constructed one.

    If this fails because the design now extracts cleanly, the record-design
    parser has been fixed and the anchor should move to another violator or be
    retired -- do NOT weaken the sibling gate to compensate.
    """
    _modelos, catalogues = _committed_registry_tree()
    source = catalogues.sources.get(_KNOWN_SELF_CONTRADICTING_DESIGN)
    assert source is not None, f"{_KNOWN_SELF_CONTRADICTING_DESIGN} is no longer in the catalogue; re-anchor"

    sheets = _sheets_for(source)
    assert sheets, f"{_KNOWN_SELF_CONTRADICTING_DESIGN} is not readable; re-anchor"

    found = [pair for sheet in sheets for pair in _partial_overlaps(sheet)]
    assert found, (
        f"{_KNOWN_SELF_CONTRADICTING_DESIGN} no longer contradicts itself, so the sibling "
        "gate is currently proven by nothing in the corpus; re-anchor it on another "
        "violator or retire this pair"
    )


def test_the_known_self_contradicting_design_is_not_authored_against() -> None:
    """A design that cannot be read consistently must not be a layout authority.

    This is the constraint the sibling gate protects, stated where a reader meets
    it: modelo 038 is blocked on its design's EXTRACTION, not on authoring
    effort, and citing it for an export layout would encode offsets the design
    does not support.
    """
    modelos, catalogues = _committed_registry_tree()
    assert _KNOWN_SELF_CONTRADICTING_DESIGN not in _cited_design_ids(modelos, catalogues), (
        f"an export layout now cites {_KNOWN_SELF_CONTRADICTING_DESIGN}, whose extraction "
        "places fields across each other's bytes; the offsets it encodes cannot be trusted"
    )
