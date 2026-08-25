"""Exact parser-owned Modelo 390 2022 numbered-page anchor census.

This is deliberately not a semantic map.  It records the compact, source-derived
geometry that a later semantic map must cover: every fixed numbered-page anchor
in the reviewed 2022 design, including its sheet, row, cell, ordinal and record
identity.  The source's eight page shapes are stable enough to state as page
cardinalities; the full 537-element anchor set is derived from that geometry and
then compared exactly with the parser output.

The 13-field auxiliary header is governed separately by
``dev.registry.pipeline._m390_auxiliary_envelope``.  Including it here would
turn a numbered-page census into a second owner for page zero.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from ..pipeline._record_design_ir import RecordDesignIntermediate, RecordDesignIntermediateField

__all__ = [
    "M390_2022_NUMBERED_ANCHOR_COUNT",
    "M390_2022_NUMBERED_PAGE_ANCHORS",
    "M390_2022_NUMBERED_PAGE_COUNTS",
    "M390_2022_SCALAR_CASILLA_BOXES",
    "M390NumberedAnchor",
    "M3902022NumberedAnchorCensus",
    "census_m390_2022_numbered_anchors",
]


M390_2022_NUMBERED_ANCHOR_COUNT: Final[int] = 537
"""Exact number of fixed numbered-page fields in the official 2022 design."""


M390_2022_NUMBERED_PAGE_COUNTS: Final[Mapping[str, int]] = {
    "Pág. 1": 74,
    "Pág. 2": 92,
    "Pág. 3": 97,
    "Pág. 4": 19,
    "Pág. 5": 97,
    "Pág. 6": 49,
    "Pág. 7": 48,
    "Pág. 8": 61,
}
"""The eight official numbered records and their parser-observed field counts."""


M390_2022_SCALAR_CASILLA_BOXES: Final[frozenset[str]] = frozenset(str(box) for box in range(74, 84))
"""Boxes 74--83 arrive through the typed M303/4T handoff, never a row projection."""


@dataclass(frozen=True, slots=True, order=True)
class M390NumberedAnchor:
    """One parser-owned exact coordinate of a fixed Modelo 390 numbered-page field."""

    sheet: str
    source_row: int
    source_cell: str | None
    ordinal: str | None
    record_identity: str


def _expected_anchor(record_identity: str, ordinal: int) -> M390NumberedAnchor:
    """Derive one exact 2022 source anchor from its reviewed page geometry."""
    source_row = ordinal + 5
    return M390NumberedAnchor(
        sheet=record_identity,
        source_row=source_row,
        source_cell=f"A{source_row}",
        ordinal=str(ordinal),
        record_identity=record_identity,
    )


M390_2022_NUMBERED_PAGE_ANCHORS: Final[frozenset[M390NumberedAnchor]] = frozenset(
    _expected_anchor(record_identity, ordinal)
    for record_identity, count in M390_2022_NUMBERED_PAGE_COUNTS.items()
    for ordinal in range(1, count + 1)
)
"""The complete source-derived 537-anchor identity set for the 2022 numbered pages."""


_BOX_SUFFIX = re.compile(r"\[(?P<box>74|75|76|77|78|79|80|81|82|83)\]\s*$")


@dataclass(frozen=True, slots=True)
class M3902022NumberedAnchorCensus:
    """Measured exact-anchor census used by later M390 owner declarations."""

    anchors: frozenset[M390NumberedAnchor]
    anchors_by_record: Mapping[str, frozenset[M390NumberedAnchor]]
    scalar_casilla_anchors: Mapping[str, M390NumberedAnchor]

    @property
    def anchor_count(self) -> int:
        """Return the total source-owned numbered-page anchor count."""
        return len(self.anchors)


def census_m390_2022_numbered_anchors(
    intermediate: RecordDesignIntermediate,
) -> M3902022NumberedAnchorCensus:
    """Require the exact 2022 numbered-page anchor set before owner mapping exists.

    This is intentionally stricter than a count check.  A shifted parser row,
    missing field, duplicate coordinate, new field, or a record renamed beneath
    an unchanged page total all change the exact five-part anchor identity and
    refuse here.  The later semantic-map authoring work consumes this same set;
    it may not replace it with a box-number reverse lookup.
    """
    if str(intermediate.source.source_ref) != "aeat-dr-390-2022":
        raise ValueError("M390 2022 numbered-anchor census requires aeat-dr-390-2022")
    if intermediate.source.design_epoch != "2022":
        raise ValueError("M390 2022 numbered-anchor census requires design epoch '2022'")

    fields = tuple(field for sheet in intermediate.sheets for field in sheet.fields)
    anchors = tuple(_anchor(field) for field in fields)
    duplicates = tuple(sorted(anchor for anchor, count in Counter(anchors).items() if count != 1))
    if duplicates:
        raise ValueError(f"M390 2022 parser repeats numbered-page anchors: {duplicates!r}")
    actual = frozenset(anchors)
    if actual != M390_2022_NUMBERED_PAGE_ANCHORS:
        missing = tuple(sorted(M390_2022_NUMBERED_PAGE_ANCHORS - actual))
        unknown = tuple(sorted(actual - M390_2022_NUMBERED_PAGE_ANCHORS))
        raise ValueError(
            f"M390 2022 parser numbered-anchor set drifted: missing={missing!r}, unknown={unknown!r}",
        )
    if len(actual) != M390_2022_NUMBERED_ANCHOR_COUNT:
        raise ValueError("M390 2022 numbered-anchor count drifted")

    by_record = {
        record_identity: frozenset(anchor for anchor in actual if anchor.record_identity == record_identity)
        for record_identity in M390_2022_NUMBERED_PAGE_COUNTS
    }
    record_counts = {record_identity: len(record_anchors) for record_identity, record_anchors in by_record.items()}
    if record_counts != dict(M390_2022_NUMBERED_PAGE_COUNTS):
        raise ValueError(f"M390 2022 numbered-page record counts drifted: {record_counts!r}")

    scalar_casilla_anchors = _scalar_casilla_anchors(fields)
    if set(scalar_casilla_anchors) != set(M390_2022_SCALAR_CASILLA_BOXES):
        raise ValueError(
            "M390 2022 source no longer exposes exactly scalar/Casilla boxes 74-83: "
            f"{tuple(sorted(scalar_casilla_anchors))!r}",
        )
    if any(anchor not in actual for anchor in scalar_casilla_anchors.values()):
        raise ValueError("M390 2022 scalar/Casilla anchors must belong to the numbered-page source set")
    return M3902022NumberedAnchorCensus(
        anchors=actual,
        anchors_by_record=by_record,
        scalar_casilla_anchors=scalar_casilla_anchors,
    )


def _anchor(field: RecordDesignIntermediateField) -> M390NumberedAnchor:
    return M390NumberedAnchor(
        sheet=str(field.sheet),
        source_row=int(field.source_row),
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        record_identity=str(field.record_identity),
    )


def _scalar_casilla_anchors(
    fields: tuple[RecordDesignIntermediateField, ...],
) -> dict[str, M390NumberedAnchor]:
    result: dict[str, M390NumberedAnchor] = {}
    for field in fields:
        match = _BOX_SUFFIX.search(field.normalized_description)
        if match is None:
            continue
        box = match.group("box")
        if box in result:
            raise ValueError(f"M390 2022 source repeats scalar/Casilla box {box!r}")
        result[box] = _anchor(field)
    return result
