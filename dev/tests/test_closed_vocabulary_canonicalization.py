"""Architecture gate: no closed vocabulary is declared at more than one schema field.

A value set with two declarations has two definitions, and a member added to one
leaves the other validating the old set. This gate asserts that population is empty,
and it carries no allowlist, no baseline and no exemption ledger.

WHAT IT ASSERTS, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------

It asserts the campaign's actual charter: zero vocabularies declared at more than one
field. That number was fourteen when the canonical scan first measured it and is zero
now, which is what makes an unconditional assertion honest rather than aspirational.

It does NOT assert that every closed vocabulary is an enum. Seventy-odd single-site
unions remain and are not defects: a union declared once is already one definition,
so promoting it buys typing and member documentation, not de-duplication. Asserting
zero of those would be asserting a goal the campaign has not met and did not set.

It especially does not assert that a vocabulary appears exactly once in the type
system. The casilla data-type taxonomy is deliberately narrowed by two surfaces --
a manual input may not carry a tax identifier, an export field may not carry a ratio
-- and those narrowings are contracts. They are rooted in the canonical enum rather
than independent, so they are one definition with two restrictions, and the scan
counts them once for exactly that reason.

WHY A PREDICATE AND NOT A LIST
-------------------------------

Four earlier counting methods each measured where the tokens were WRITTEN, and each
was superseded within a day by a place they were also written: behind an alias, then
nested inside a generic, then both. Every one of those moves is available to a future
author without any intent to evade. The scan this gate reads resolves alias chains
and walks the whole annotation subtree, so it measures the structure rather than the
spelling, and there is no line here for a new exception to be added to.

ITS OWN BLIND SPOT
------------------

The scan reads annotations. A vocabulary enforced somewhere else -- a validator
comparing against a tuple of literals, a membership test against a module constant --
is invisible to it, and this gate inherits that limit exactly. Its zero is a zero for
DECLARED ANNOTATIONS, not a claim about the codebase's whole vocabulary surface.
Finding the rest is semantic search by meaning, which is how this campaign found an
aliasing normaliser and two byte-identical enums that no name search reached.

See Also:
    :mod:`dev.quality.closed_vocabulary_scan`
        Owns the scan. This module only asserts on it, so the rule has one
        definition rather than two that can disagree.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from ..quality.closed_vocabulary_scan import VocabularyField, scan

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _independent_declarations(
    rows: tuple[VocabularyField, ...],
) -> dict[tuple[str, ...], list[VocabularyField]]:
    """Group by member set, counting one shared alias as ONE declaration.

    Fields that reach the same named alias are consumers of a single definition, which
    is the outcome this campaign wants rather than the defect it hunts. Grouping on
    members alone cannot see that: it reports four fields importing one alias exactly
    as it reports four independent unions, and the first is not a defect at all. Each
    distinct alias counts once, and every inline spelling counts on its own.
    """
    grouped: dict[tuple[str, ...], list[VocabularyField]] = defaultdict(list)
    for members, rows_for_members in _by_members(rows).items():
        seen_aliases: set[str] = set()
        for row in rows_for_members:
            if row.alias_name is not None:
                if row.alias_name in seen_aliases:
                    continue
                seen_aliases.add(row.alias_name)
            grouped[members].append(row)
    return grouped


def _by_members(rows: tuple[VocabularyField, ...]) -> dict[tuple[str, ...], list[VocabularyField]]:
    grouped: dict[tuple[str, ...], list[VocabularyField]] = defaultdict(list)
    for row in rows:
        grouped[tuple(sorted(row.members))].append(row)
    return grouped


def test_no_closed_vocabulary_is_declared_at_more_than_one_field() -> None:
    """Zero. Not a ceiling, not a baselined set -- zero, with nothing to exempt."""
    duplicated = {members: sites for members, sites in _independent_declarations(scan()).items() if len(sites) > 1}

    if duplicated:
        listing = "\n".join(
            f"  [{', '.join(members)}]\n"
            + "\n".join(f"      {site.location}  {site.model}.{site.field}" for site in sites)
            for members, sites in sorted(duplicated.items())
        )
        pytest.fail(
            f"{len(duplicated)} closed vocabular{'y is' if len(duplicated) == 1 else 'ies are'} "
            "declared at more than one field.\n"
            "Give the value set one named enum the schema imports, and express any narrowing "
            "as a literal over that enum's members rather than as a second declaration. There "
            "is deliberately no exemption list to add to.\n" + listing,
        )


def test_the_detector_fires_on_a_planted_duplicate() -> None:
    """Anti-tautology control: the zero above must be a measurement, not a blind spot.

    Constructed rather than written to the tree. Planting a real duplicate in a shared
    package to make a gate's point is a fleet hazard -- a concurrent agent hits an
    unattributable failure, and a peer's pathspec commit can capture the plant.
    """
    shared = ("alpha", "beta")
    planted = (
        VocabularyField(
            path="src/zzz/one.py",
            lineno=1,
            model="One",
            field="kind",
            members=shared,
            reached_through_alias=False,
            nested_in_generic=False,
        ),
        VocabularyField(
            path="src/zzz/two.py",
            lineno=2,
            model="Two",
            field="kind",
            members=shared,
            reached_through_alias=True,
            nested_in_generic=True,
        ),
    )

    duplicated = {m: s for m, s in _independent_declarations(planted).items() if len(s) > 1}

    assert list(duplicated) == [shared], (
        "the grouping did not see two declarations of one vocabulary, so the zero asserted above proves nothing"
    )


def test_the_gate_reads_a_real_population() -> None:
    """A scan that silently found nothing would also report zero duplicates."""
    rows = scan()
    assert len(rows) > 25, f"only {len(rows)} declarations scanned; the scan is not reaching the tree"


def test_one_shared_alias_at_many_fields_is_not_a_duplicate() -> None:
    """The distinction the grouping exists to make, proven rather than assumed.

    Four fields importing one alias are four consumers of a single definition. An
    earlier grouping keyed only on members reported exactly that as a four-site
    duplicate, and acting on it would have "fixed" a vocabulary that was already
    canonical.
    """
    shared = ("alpha", "beta")
    consumers = tuple(
        VocabularyField(
            path=f"src/zzz/consumer_{n}.py",
            lineno=n,
            model=f"Model{n}",
            field="kind",
            members=shared,
            reached_through_alias=True,
            nested_in_generic=False,
            alias_name="OneSharedAlias",
        )
        for n in range(1, 5)
    )

    duplicated = {m: s for m, s in _independent_declarations(consumers).items() if len(s) > 1}

    assert duplicated == {}, (
        "four consumers of one alias were counted as duplicate declarations, so the "
        "gate would demand a fix for a vocabulary that already has one definition"
    )


def test_two_distinct_aliases_of_one_vocabulary_do_fire() -> None:
    """Two names for one value set are still two definitions, alias or not."""
    shared = ("alpha", "beta")
    rival = (
        VocabularyField(
            path="src/zzz/one.py",
            lineno=1,
            model="One",
            field="kind",
            members=shared,
            reached_through_alias=True,
            nested_in_generic=False,
            alias_name="AliasOne",
        ),
        VocabularyField(
            path="src/zzz/two.py",
            lineno=2,
            model="Two",
            field="kind",
            members=shared,
            reached_through_alias=True,
            nested_in_generic=False,
            alias_name="AliasTwo",
        ),
    )

    duplicated = {m: s for m, s in _independent_declarations(rival).items() if len(s) > 1}

    assert list(duplicated) == [shared], "two rival aliases for one vocabulary must still count as two"
