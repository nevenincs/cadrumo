"""Does the competing concept a mined candidate is measured against exist?

`validate_ratification_queue` joins `concept_id` to the Handbook and joins a
ratified candidate to the shipped query vocabulary. Both joins are real. What
neither of them reaches is the OTHER half of every mined row: the competitor.

`relative_margin` is `cosine - nearest_competing_cosine` and `relative_ratio`
is `cosine / nearest_competing_cosine`. Those two derived numbers, together
with the absolute cosine floor, are the whole of `_passes_relative_cosine` --
the predicate that decides whether an observation becomes a queue row at all
and whether a committed row is reported as a violation. So
`nearest_competing_cosine` is a direct input to the figure that drives the
decision, and `competing_concept_id` is the only field that says what that
number was measured against.

Neither field is read by any predicate in the module. Against the committed
queue, rewriting `competing_concept_id` to `concept-that-does-not-exist`
leaves `validate_ratification_queue` reporting 0 violations; so does setting
it equal to `concept_id`, which makes the margin a measurement of a concept
against itself. Worst of the three: a candidate at cosine 0.80 against a real
competitor at 0.78 has ratio 1.026, fails the 1.08 threshold, and is reported
as a violation -- and the same candidate with its competing cosine set to an
unattributed 0.0 has ratio `inf`, passes, and is reported clean. The queue
does not lie about pass or fail; the number it passes on does, and a synonym
argues its way into the shipped query vocabulary on a competition that was
never observed.

Every gate below is keyed on something outside the field it checks -- the live
Handbook, the row's own `concept_id`, the row's own competing cosine -- so
none can be satisfied by editing the value under test.

Residue, sized rather than waved at: a row that names NO competitor
(`competing_concept_id is None`) and claims a competing cosine of exactly 0.0
still takes the `inf` ratio and passes unconditionally. That combination is
internally coherent -- it spells "nothing competed" in both fields at once --
so refusing it is a decision about whether an embedding run may report no
nearest neighbour, not something a gate can settle. Live, 0 of 3 committed
rows name no competitor, so the residue is currently empty.
"""

from __future__ import annotations

import math

import pytest

from ...terminology_handbook.loader import TerminologyHandbook, load_terminology_handbook
from .._synonym_mining import (
    SynonymRatificationQueue,
    load_synonym_ratification_queue,
    validate_ratification_queue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _unresolvable_competitors(
    queue: SynonymRatificationQueue,
    handbook: TerminologyHandbook,
) -> tuple[str, ...]:
    """Rows whose named competitor is not a concept the Handbook enrols."""
    return tuple(
        f"{entry.concept_id}:{entry.candidate} competes against {entry.competing_concept_id!r}"
        for entry in queue.entries
        if entry.competing_concept_id is not None and entry.competing_concept_id not in handbook.by_id
    )


def _self_competitions(queue: SynonymRatificationQueue) -> tuple[str, ...]:
    """Rows whose competitor is the concept the candidate is mined for."""
    return tuple(
        f"{entry.concept_id}:{entry.candidate}"
        for entry in queue.entries
        if entry.competing_concept_id is not None and entry.competing_concept_id == entry.concept_id
    )


def _incoherent_competition(queue: SynonymRatificationQueue) -> tuple[str, ...]:
    """Rows whose two competition fields contradict each other.

    Naming a competitor and reporting its cosine as exactly 0.0 makes
    `relative_ratio` infinite, so the ratio threshold is satisfied by a
    competitor the row itself says was found. Reporting a nonzero competing
    cosine while naming no competitor attributes the margin to nothing.
    """
    problems: list[str] = []
    for entry in queue.entries:
        named = entry.competing_concept_id is not None
        observed = entry.nearest_competing_cosine > 0.0
        if named and not observed:
            problems.append(
                f"{entry.concept_id}:{entry.candidate} names {entry.competing_concept_id!r} "
                f"but reports it at cosine 0.0, taking an unbounded ratio",
            )
        elif observed and not named:
            problems.append(
                f"{entry.concept_id}:{entry.candidate} reports a competing cosine of "
                f"{entry.nearest_competing_cosine} against no named competitor",
            )
    return tuple(problems)


def _revalidated(queue: SynonymRatificationQueue, index: int, **update: object) -> SynonymRatificationQueue:
    """A copy of ``queue`` with one row changed, put back through validation.

    The defect is round-tripped through `model_validate` rather than left as a
    bare `model_copy`, so each tooth below proves the production schema and
    `validate_ratification_queue` both ACCEPT the defect and only the gate
    beside it refuses. Nothing here touches the committed file.
    """
    rows = list(queue.entries)
    rows[index] = rows[index].model_copy(update=update)
    payload = SynonymRatificationQueue(
        schema_version=queue.schema_version,
        generated_by=queue.generated_by,
        thresholds=queue.thresholds,
        entries=tuple(rows),
    ).model_dump(mode="json")
    return SynonymRatificationQueue.model_validate(payload)


def test_every_committed_competitor_is_a_concept_the_handbook_enrols() -> None:
    """A margin is only evidence if the thing it was measured against exists."""
    queue = load_synonym_ratification_queue()
    handbook = load_terminology_handbook()

    # Vacuity floors on both roots: an empty queue or an empty Handbook would
    # satisfy every join below by having nothing to join. Live: 3 rows against
    # 165 enrolled concepts.
    assert queue.entries, "the committed queue is empty, so the joins below range over nothing"
    assert len(handbook.by_id) >= 100, (
        f"the Handbook enrols only {len(handbook.by_id)} concept(s); the existence join is nearly vacuous"
    )

    named = tuple(entry for entry in queue.entries if entry.competing_concept_id is not None)
    assert named, "no committed row names a competitor, so the existence join is bound to nothing"

    unresolvable = _unresolvable_competitors(queue, handbook)
    assert unresolvable == (), (
        "a mined candidate is screened on its distance from a concept the Handbook "
        "does not enrol, so the margin that admitted it measures nothing: " + "; ".join(unresolvable)
    )


def test_the_existence_join_bites_on_a_competitor_that_is_not_enrolled() -> None:
    queue = load_synonym_ratification_queue()
    handbook = load_terminology_handbook()
    defected = _revalidated(queue, 0, competing_concept_id="concept-that-does-not-exist")

    assert validate_ratification_queue(defected, handbook=handbook).violations == (), (
        "the queue validator is expected to accept this defect; the gate under test is what catches it"
    )
    assert _unresolvable_competitors(defected, handbook) != ()


def test_no_committed_row_is_screened_against_its_own_concept() -> None:
    """A concept measured against itself has no separating margin to report."""
    queue = load_synonym_ratification_queue()

    assert queue.entries, "the committed queue is empty, so the distinctness check ranges over nothing"

    self_competing = _self_competitions(queue)
    assert self_competing == (), (
        "a mined candidate reports its own concept as the nearest competing one, "
        "so its margin and ratio compare a concept to itself: " + "; ".join(self_competing)
    )


def test_the_distinctness_check_bites_on_a_row_that_competes_with_itself() -> None:
    queue = load_synonym_ratification_queue()
    handbook = load_terminology_handbook()
    defected = _revalidated(queue, 0, competing_concept_id=queue.entries[0].concept_id)

    assert validate_ratification_queue(defected, handbook=handbook).violations == (), (
        "the queue validator is expected to accept this defect; the gate under test is what catches it"
    )
    assert _self_competitions(defected) != ()


def test_every_committed_row_agrees_with_itself_about_the_competition() -> None:
    """The named competitor and its cosine must tell the same story."""
    queue = load_synonym_ratification_queue()

    assert queue.entries, "the committed queue is empty, so the coherence check ranges over nothing"

    incoherent = _incoherent_competition(queue)
    assert incoherent == (), (
        "a mined candidate's two competition fields contradict each other, so the "
        "ratio it passes on is not the competition it names: " + "; ".join(incoherent)
    )


def test_an_unattributed_zero_turns_a_failing_ratio_into_a_passing_one() -> None:
    """The direction that matters: the defect ARGUES FOR shipping the synonym.

    A real competitor at 0.78 puts this candidate's ratio under the 1.08 floor
    and the validator says so. Zeroing that competing cosine -- while still
    naming the competitor -- sends the ratio to infinity and the violation
    disappears, without the row failing anything else.
    """
    queue = load_synonym_ratification_queue()
    handbook = load_terminology_handbook()

    honest = _revalidated(queue, 1, cosine=0.80, nearest_competing_cosine=0.78)
    assert math.isfinite(honest.entries[1].relative_ratio)
    assert honest.entries[1].relative_ratio < queue.thresholds.minimum_ratio
    honest_reasons = [
        violation.reason for violation in validate_ratification_queue(honest, handbook=handbook).violations
    ]
    assert honest_reasons == ["candidate does not pass relative-cosine thresholds"], honest_reasons
    assert _incoherent_competition(honest) == ()

    fabricated = _revalidated(queue, 1, cosine=0.80, nearest_competing_cosine=0.0)
    assert math.isinf(fabricated.entries[1].relative_ratio)
    assert validate_ratification_queue(fabricated, handbook=handbook).violations == (), (
        "the queue validator is expected to accept the fabricated zero; the gate under test is what catches it"
    )
    assert _incoherent_competition(fabricated) != ()


def test_the_coherence_check_bites_on_a_margin_attributed_to_no_competitor() -> None:
    queue = load_synonym_ratification_queue()
    handbook = load_terminology_handbook()
    defected = _revalidated(queue, 0, competing_concept_id=None)

    assert validate_ratification_queue(defected, handbook=handbook).violations == (), (
        "the queue validator is expected to accept this defect; the gate under test is what catches it"
    )
    assert _incoherent_competition(defected) != ()


def test_the_gates_leave_a_clean_queue_clean() -> None:
    """All three predicates read empty on the committed queue as it stands."""
    queue = load_synonym_ratification_queue()
    handbook = load_terminology_handbook()

    assert _unresolvable_competitors(queue, handbook) == ()
    assert _self_competitions(queue) == ()
    assert _incoherent_competition(queue) == ()
    assert validate_ratification_queue(queue, handbook=handbook).violations == ()
