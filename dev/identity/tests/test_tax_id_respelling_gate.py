"""The tax-identifier normal-form gate: two canonical forms, no respellings.

Wires ``dev/identity/tax_id_respelling_census.py`` into the pytest surface. This class
has been declared closed TWICE on false completeness claims -- once for
"the last same-bearer comparisons" and once for "the last key builder" -- and
both times the claim was exhaustion of a PATTERN reported as exhaustion of the
CLASS. Neither author was careless; both had run a grep that returned nothing
and read that as a clean tree.

WHAT THIS GATE ASSERTS, as a property and never as a tally: no production site
open-codes a tax-identifier normal form that
:func:`~core.identity.tax_id_identity_token` or
:func:`~core.identity.same_tax_identifier` already owns, except sites named in
the census's ``EXEMPTIONS`` with a stated reason.

WHY THE ACTIONABLE KINDS ARE ASSERTED SEPARATELY from the rest. A ``comparison``
respelling and a ``keying`` respelling are the two the canonical forms directly
replace, and each is a live defect: the comparison kind is how a printed
``B-1234567-4`` failed to match a stored ``B12345674`` and read as a different
bearer. ``unclassified`` and ``free_standing`` sites are normalisations whose
use this walker cannot attribute; they are reported so they cannot be silently
dropped, but a site there may be legitimate and forcing them to zero would
push authors to disguise a respelling rather than route it.

THE VACUITY GUARD MATTERS MORE THAN THE ASSERTION. Every previous false
closure here came from an instrument that could not see, and a scanner
returning nothing is indistinguishable from a clean tree. So the population
test runs first and fails on an empty scan, and the census carries its own
positive control. While building it the base resolver was found to resolve
7 of 182 chains, which had made the tree look nearly clean; that defect would
have passed any assertion written against its output.
"""

from __future__ import annotations

import pytest
from dev.identity.tax_id_respelling_census import (
    EXEMPTIONS,
    Finding,
    census,
    stale_exemptions,
    unexempted,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Kinds the canonical forms directly replace, and which must stay at zero.
ACTIONABLE_KINDS = ("comparison", "keying")


@pytest.fixture(scope="module")
def findings() -> list[Finding]:
    """Return the respelling census for the working revision."""
    return census("HEAD")


def test_the_scanner_reaches_a_real_population(findings: list[Finding]) -> None:
    """Fail on an empty scan before any assertion is allowed to pass.

    A census that returns nothing because its walker broke reads exactly like
    a clean tree. That is not hypothetical here: an earlier base resolver
    handled 7 of 182 normalising chains and reported the rest as unmatched.
    Every assertion below was green against it.
    """
    scanned = census("HEAD")
    assert scanned, "the respelling census returned nothing -- the scanner is broken, not the tree clean"
    assert findings == scanned


def test_no_production_site_open_codes_an_identity_comparison_or_key(
    findings: list[Finding],
) -> None:
    """The two kinds the canonical forms replace must stay at zero."""
    offenders = [f for f in unexempted(findings) if f.kind in ACTIONABLE_KINDS]
    rendered = "\n".join(f"  {f.path}:{f.line} [{f.kind}] {f.snippet}" for f in offenders)
    assert not offenders, (
        "a tax identifier is normalised by hand where a canonical form owns it.\n"
        "A comparison belongs to same_tax_identifier, which strips the separators\n"
        "AEAT prints; a key belongs to tax_id_identity_token, which must not.\n"
        f"{rendered}"
    )


def test_every_exemption_answers_a_live_occurrence(findings: list[Finding]) -> None:
    """An exemption excusing nothing is worse than no exemption.

    It reads as a considered judgement while excusing nothing, and the next
    author inherits it as precedent for adding another.
    """
    stale = stale_exemptions(findings)
    rendered = "\n".join(f"  {entry.path}::{entry.symbol} -- {entry.reason}" for entry in stale)
    assert not stale, f"exemptions no longer answering a live site:\n{rendered}"


def test_every_exemption_states_a_reason() -> None:
    """The judgement an exemption encodes must be readable, not implied."""
    unreasoned = [entry for entry in EXEMPTIONS if not entry.reason.strip()]
    assert not unreasoned, f"exemptions without a stated reason: {unreasoned}"
