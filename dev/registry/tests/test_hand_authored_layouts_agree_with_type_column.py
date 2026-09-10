"""Hand-authored export layouts agree with their official type column, or say why not.

The type-column gate for generated trees reads derivation records, which a
hand-authored ``export_layouts`` tree does not carry, so it cannot see these
revisions at all. This gate joins each shipped record to its revision's own
pinned record design and compares every aligned field's sign with the official
type.

Nothing here is a pass by omission. A field the schema cannot sign, and a record
that cannot be aligned to exactly one design sheet, are each declared below per
revision with a reason, and the declaration is checked against the live tree in
both directions: a new unexplained case fails, and so does a declared case that
has been repaired, so a declaration cannot outlive its cause.
"""

from __future__ import annotations

import collections
import re
import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis.hand_authored_type_column import (
    Alignment,
    hand_authored_revisions,
    revision_findings,
    screen_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Fields the official design types ``N`` that the schema refuses to sign. In
#: modelo 714 these are the twelve "% participación individual/familiar" cells of
#: the exempt-shareholding sections, where the same design types every other
#: percentage ``Num``. A shareholding percentage cannot be negative, so the
#: unsigned declaration writes exactly the bytes a signed one would for every
#: value that can exist, and refuses a negative rather than mis-writing it.
#: Signing them would need a signed integer the schema does not have, for a
#: value no filing can carry, so they are declared here rather than changed.
_BLOCKED_PER_REVISION: dict[str, tuple[int, str]] = {
    f"714/{year}": (12, "data type 'integer' cannot be signed; only money can")
    for year in ("2021", "2022", "2023", "2024", "2025")
}

#: Records that cannot be joined to exactly one sheet of their revision's design.
#: ``no_design``: the revision pins no record design or more than one.
#: ``ambiguous``: several sheets carry every slot of the record, so its sheet is
#: not determined by geometry. ``unmatched``: no sheet carries them all. None of
#: these is compared, so each is an open question rather than a pass.
_UNCHECKED_PER_REVISION: dict[str, dict[str, int]] = {
    "122/2017-y-siguientes": {"unmatched": 1},
    "126/2019-y-siguientes": {"no_design": 2},
    "128/2019-y-siguientes": {"no_design": 2},
    "180/2019-2022": {"unmatched": 2},
    "180/2023-y-siguientes": {"unmatched": 2},
    "190/2024": {"unmatched": 2},
    "190/2025-y-siguientes": {"unmatched": 2},
    "193/2024": {"unmatched": 2},
    "193/2025-y-siguientes": {"unmatched": 2},
    "216/2024-y-siguientes": {"unmatched": 1},
    "270/2013-2022": {"unmatched": 1},
    "270/2023-y-siguientes": {"unmatched": 1},
    "349/2020-y-siguientes": {"unmatched": 3},
    "369/esquema-exterior": {"ambiguous": 2},
    "369/esquema-importacion": {"ambiguous": 2},
    "369/esquema-union": {"ambiguous": 3},
    "490/2022-2t-4t": {"ambiguous": 4},
    "490/2023-y-siguientes": {"ambiguous": 4},
    "576/2008-y-siguientes": {"unmatched": 1},
    "714/2021": {"unmatched": 1},
    "714/2022": {"unmatched": 1},
    "714/2023": {"unmatched": 1},
    "714/2024": {"unmatched": 1},
    "714/2025": {"unmatched": 1},
}


@pytest.fixture(scope="module")
def screened():
    return screen_authority(bundled_authority())


def test_no_aligned_hand_authored_field_contradicts_its_type_column(screened) -> None:
    """Where the design types a campo N and the schema can sign it, the layout signs it."""
    _alignments, contradictions = screened
    open_rows = [
        f"{item.subject} {item.layout_file} {item.field_id} @{item.offset}+{item.length}"
        for item in contradictions
        if item.blocked_reason is None
    ]
    assert not open_rows, "fields the official design types N shipped unsigned:\n" + "\n".join(open_rows[:40])


def test_fields_the_schema_cannot_sign_are_exactly_the_declared_ones(screened) -> None:
    _alignments, contradictions = screened
    live: dict[str, tuple[int, str]] = {}
    for item in contradictions:
        if item.blocked_reason is None:
            continue
        count, _reason = live.get(item.subject, (0, item.blocked_reason))
        live[item.subject] = (count + 1, item.blocked_reason)
    assert live == _BLOCKED_PER_REVISION


def test_unaligned_records_are_exactly_the_declared_ones(screened) -> None:
    alignments, _contradictions = screened
    live: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for item in alignments:
        if item.alignment is not Alignment.ALIGNED:
            live[item.subject][item.alignment.value] += 1
    assert {subject: dict(counts) for subject, counts in live.items()} == _UNCHECKED_PER_REVISION


def _planted_revision(tmp_path: Path, modelo: str, revision: str) -> Path:
    for candidate_modelo, candidate_revision, root in hand_authored_revisions(bundled_authority()):
        if (candidate_modelo, candidate_revision) == (modelo, revision):
            planted = tmp_path / "revision"
            shutil.copytree(root / "export_layouts", planted / "export_layouts")
            return planted
    raise AssertionError(f"{modelo}/{revision} is not a hand-authored revision")


def test_a_planted_unsigned_field_is_reported_by_name(tmp_path: Path) -> None:
    """Unsigning one aligned N field is caught as exactly that field, and nothing else."""
    authority = bundled_authority()
    planted = _planted_revision(tmp_path, "490", "2021")
    layout = next(
        path
        for path in sorted((planted / "export_layouts").glob("*.toml"))
        if "signed = true" in path.read_text("utf-8")
    )
    text = layout.read_text("utf-8")
    field_line = text.index("signed = true")
    field_id = re.findall(r'^id = "([^"]+)"$', text[:field_line], flags=re.MULTILINE)[-1]
    layout.write_text(text[:field_line] + "signed = false" + text[field_line + len("signed = true") :], "utf-8")

    _clean_alignments, clean = revision_findings(
        authority, modelo="490", revision="2021", revision_root=_planted_revision(tmp_path / "clean", "490", "2021")
    )
    _alignments, found = revision_findings(authority, modelo="490", revision="2021", revision_root=planted)

    assert clean == ()
    assert [(item.field_id, item.blocked_reason) for item in found] == [(field_id, None)]


def test_a_record_that_fits_no_sheet_is_unchecked_not_passed(tmp_path: Path) -> None:
    """A record whose geometry matches no design sheet is reported, never compared as if it had."""
    authority = bundled_authority()
    planted = _planted_revision(tmp_path, "490", "2021")
    layout = sorted((planted / "export_layouts").glob("*.toml"))[0]
    text = layout.read_text("utf-8")
    marker = text.index("\noffset = ") + len("\noffset = ")
    end = text.index("\n", marker)
    layout.write_text(text[:marker] + "999999" + text[end:], "utf-8")

    alignments, _found = revision_findings(authority, modelo="490", revision="2021", revision_root=planted)

    assert Alignment.UNMATCHED in {item.alignment for item in alignments}
