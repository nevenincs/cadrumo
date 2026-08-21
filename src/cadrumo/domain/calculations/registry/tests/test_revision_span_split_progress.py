"""Which revisions still span a re-layout — pinned, so a split cannot silence the gate.

The sibling gate ``test_no_revision_spans_a_design_relayout`` answers one
question: is anything spanning. That is the right question to fail on, and the
wrong one to measure progress by, because it cannot distinguish "M200 was split
correctly" from "the boundary detector stopped seeing anything".

Those two outcomes are indistinguishable from a red-to-green transition, and the
second is a real hazard here: the detector reads bundled designs and pairs them
by filing year, so a mis-keyed pair, a renamed corpus file or a narrowed revision
that accidentally excludes both sides all produce silence. A split that silences
the gate has broken the gate.

So this module pins the SET. A split must remove exactly its own modelo and
leave the others reporting. Anything else — an extra modelo appearing, or the
set collapsing to empty — fails here even while the sibling gate is content.

Kept separate from the gate rather than folded into it on purpose: the gate's
verdict is "this must not ship", and this module's is "the split is proceeding
as intended". Merging them would make a bookkeeping update look like a
correctness change.
"""

from __future__ import annotations

from typing import Final

import pytest

from .test_revision_span_matches_published_designs import _boundaries_for, _exporting_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Revisions known to span a design re-layout, with the row tracking each split.
#:
#: Remove an entry ONLY when that revision has actually been partitioned. The
#: entry is not a suppression — the sibling gate still fails on every one of
#: these. It records which spans are known and owned, so a NEW one cannot arrive
#: unnoticed inside an already-red gate, which is the way a red gate hides its
#: own growth.
_KNOWN_SPANNING: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # The four revisions that genuinely cite two designs across a YEAR
        # boundary and still await their split. Each is recorded in the
        # export-layout authoring backlog audit with the boundary it crosses.
        ("184", "2015-y-siguientes"),
        ("200", "2024-y-siguientes"),
        ("322", "2008-2025"),
        ("347", "2008-y-siguientes"),
    },
)
#: `("303", "2022")` removed: its split landed, and the detector confirms it --
#: `_boundaries_for` returns nothing for that revision now.
#:
#: Four entries left this set at the same time, and NOT because anything was
#: split. Modelo 303's two 2024 halves and modelo 490's two 2022 halves were
#: reported as spanning by a detector that claimed designs per YEAR: AEAT splits
#: an ejercicio mid-course by publishing two designs sharing a coverage year, so
#: each half received both and reported a boundary inside its own year. They
#: were already correctly scoped. `_designs_claimed_by` now restricts a
#: half-year revision to the design it cites, and the four false positives
#: stopped reporting while every genuine cross-year span above kept doing so.
#: `("390", "2010-y-siguientes")` (rows #110, #115, #118) removed: the revision-span
#: split replaced the open-ended revision with four exact-year revisions (2022,
#: 2023, 2024, 2025), each claiming exactly one design year. Verified rather than
#: assumed -- `_boundaries_for` run against each of the four returns no boundary,
#: so the span genuinely resolved rather than moved. This is a DIFFERENT question
#: from `test_fed_alias_beside_starved_box.py`'s `_KNOWN_PAIRINGS`: that module's
#: box-alias mis-declaration is untouched by this split and still reports under
#: all four new revision ids.


def _spanning() -> set[tuple[str, str]]:
    return {
        (modelo.id, revision_id)
        for modelo, revision_id, revision in _exporting_revisions()
        if _boundaries_for(modelo.id, revision)
    }


def test_the_detector_still_sees_something() -> None:
    """Anti-vacuity, and the failure mode this module exists for.

    An empty result reads as "every span is fixed" and is far more likely to
    mean the boundary detector stopped resolving designs at all. Until the last
    known span is genuinely split, empty is a defect.
    """
    assert _spanning(), (
        "no revision is reported as spanning a re-layout. If the splits really have all landed, "
        "delete this module together with the last entry in _KNOWN_SPANNING; until then an empty "
        "result means the detector has stopped seeing designs, not that the tree is clean"
    )


def test_no_unknown_revision_has_started_spanning() -> None:
    """A NEW span must not hide inside an already-red gate.

    The sibling gate is red today, so a fifth spanning revision would change its
    message and nothing else — no transition, no signal. This is what notices.
    """
    unexpected = sorted(_spanning() - _KNOWN_SPANNING)

    assert not unexpected, (
        f"these revisions now span a design re-layout and are on no tracked row: {unexpected}. "
        "Either the revision gained a filing year it should not cover, or a newly bundled design "
        "revealed a boundary that was always there. Open a row before adding it below."
    )


def test_a_split_removes_exactly_its_own_modelo() -> None:
    """The control the M200 split must pass, and the reason it is written first.

    Landing the split makes this fail with a stale entry, and correcting it is
    the step that PROVES the other three still report. Written before the split
    rather than after, because a control authored afterwards is written by
    someone who already knows the answer they want.
    """
    resolved = _spanning()
    stale = sorted(_KNOWN_SPANNING - resolved)

    assert not stale, (
        f"these revisions no longer span, so their split has landed: {stale}. Remove them from "
        f"_KNOWN_SPANNING. Still spanning and correctly reported: {sorted(resolved)} — confirm that "
        "list is the one you expected, because a split that removed MORE than its own modelo "
        "silenced the detector rather than fixing a span"
    )
