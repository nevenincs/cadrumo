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

from ..tax_id_respelling_census import (
    Finding,
    census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Kinds the canonical forms directly replace, and which must stay at zero.
ACTIONABLE_KINDS = ("comparison", "keying")


@pytest.fixture(scope="module")
def findings() -> list[Finding]:
    """Return the respelling census for the working tree."""
    return census()


def test_no_production_site_open_codes_an_identity_comparison_or_key(
    findings: list[Finding],
) -> None:
    """The two kinds the canonical forms replace must stay at zero."""
    offenders = [f for f in findings if f.kind in ACTIONABLE_KINDS]
    rendered = "\n".join(f"  {f.path}:{f.line} [{f.kind}] {f.snippet}" for f in offenders)
    assert not offenders, (
        "a tax identifier is normalised by hand where a canonical form owns it.\n"
        "A comparison belongs to same_tax_identifier, which strips the separators\n"
        "AEAT prints; a key belongs to tax_id_identity_token, which must not.\n"
        f"{rendered}"
    )
