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


def _by_vocabulary(rows: tuple[VocabularyField, ...]) -> dict[tuple[str, ...], list[VocabularyField]]:
    grouped: dict[tuple[str, ...], list[VocabularyField]] = defaultdict(list)
    for row in rows:
        grouped[tuple(sorted(row.members))].append(row)
    return grouped


def test_no_closed_vocabulary_is_declared_at_more_than_one_field() -> None:
    """Zero. Not a ceiling, not a baselined set -- zero, with nothing to exempt."""
    duplicated = {
        members: sites for members, sites in _by_vocabulary(scan()).items() if len(sites) > 1
    }

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
            path="src/zzz/one.py", lineno=1, model="One", field="kind",
            members=shared, reached_through_alias=False, nested_in_generic=False,
        ),
        VocabularyField(
            path="src/zzz/two.py", lineno=2, model="Two", field="kind",
            members=shared, reached_through_alias=True, nested_in_generic=True,
        ),
    )

    duplicated = {m: s for m, s in _by_vocabulary(planted).items() if len(s) > 1}

    assert list(duplicated) == [shared], (
        "the grouping did not see two declarations of one vocabulary, so the zero "
        "asserted above proves nothing"
    )


def test_the_gate_reads_a_real_population() -> None:
    """A scan that silently found nothing would also report zero duplicates."""
    rows = scan()
    assert len(rows) > 25, f"only {len(rows)} declarations scanned; the scan is not reaching the tree"
