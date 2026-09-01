"""The hex-64 canonical-home gate: one primitive, no local redeclarations.

Wires ``dev/identity/hex64_redeclaration_census.py`` into the pytest surface as the
enforcement half of a mandate that has been stated for a long time and enforced
never.

WHY A SECOND GATE, WHEN ONE ALREADY EXISTS.
``core/tests/test_hex64_identity.py`` proves the aliases it LISTS are identical
to the canonical primitive. Its ``_ALIASES`` set is hand-written and it never
walks the tree, so it is structurally incapable of seeing a concept that never
enrolled -- and its own comment asks authors to add new ones by hand. An
enrolment gate over a hand-listed set passes under every mutation to an
unenrolled site. That is not a criticism of the older gate: the two ask
different questions, and both are needed. This one asks "did anything declare
the shape somewhere else", which is the question that went unasked while the
bypasses accumulated.

WHAT THIS GATE ASSERTS, and deliberately as a PROPERTY rather than a tally: no
production module outside ``core/hex.py`` declares the hex-64 shape, except
the sites named in the census's allowlist with a stated reason. A hardcoded
count would encode the moment it was written, train every later author to bump
the constant, and then detect nothing.

THE TWO CLASSES ARE ASSERTED SEPARATELY because they are not the same
severity, and collapsing them into one number would let a validation gap hide
inside a drift count.
"""

from __future__ import annotations

import pytest

from ..hex64_redeclaration_census import (
    CANONICAL_HOME,
    Declaration,
    DeclarationKind,
    census,
    stale_exemptions,
    unexempted,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Scanned at ``HEAD`` rather than the working tree: this repository is written
#: to by many agents at once, and a gate whose subject moves between collection
#: and assertion reports a tree nobody can reproduce.
_REVISION = "HEAD"


@pytest.fixture(scope="module")
def declarations() -> tuple[Declaration, ...]:
    """The out-of-home hex-64 declaration ledger at ``HEAD``."""
    return census(_REVISION)


def _worklist(items: tuple[Declaration, ...], header: str) -> str:
    """Render a failure as a worklist, so a red gate is actionable rather than noisy."""
    lines = "\n".join(f"  {item.rendered()}" for item in items)
    return f"{header}\n{lines}\n"


def test_the_scanner_reaches_a_real_population(declarations: tuple[Declaration, ...]) -> None:
    # A zero result from a broken scanner is indistinguishable from a clean
    # tree. This gate's other assertions are only meaningful if the census
    # actually walked something, so prove it reached production modules before
    # reading anything into what it did or did not find.
    assert declarations, "the census returned nothing at all, which means it did not run, not that the tree is clean"


def test_no_module_redeclares_the_hex64_shape_outside_the_canonical_home(
    declarations: tuple[Declaration, ...],
) -> None:
    open_sites = tuple(i for i in unexempted(declarations) if i.kind is DeclarationKind.REDECLARED_PATTERN)
    assert not open_sites, _worklist(
        open_sites,
        f"The hex-64 shape is declared outside {CANONICAL_HOME}. Each site below must "
        "declare its own semantic alias assigned FROM core.Hex64Str (or consume "
        "HEX_PATTERN_64 where a bare pattern string is what the site needs), never "
        "re-declare the shape. A site that genuinely cannot be retyped belongs in the "
        "census allowlist with a stated reason.",
    )


def test_no_field_is_constrained_to_length_64_without_a_pattern(declarations: tuple[Declaration, ...]) -> None:
    open_sites = tuple(i for i in unexempted(declarations) if i.kind is DeclarationKind.UNPATTERNED_LENGTH)
    assert not open_sites, _worklist(
        open_sites,
        "These fields pin a length of exactly 64 and assert nothing about the "
        "characters, so 64 'Z's or 64 exclamation marks satisfy them and a malformed "
        "digest reaches a persisted record -- surfacing only when something later "
        "recomputes the hash. Retype each to core.Hex64Str, or to the semantic alias "
        "for its concept (ContentDigest for a payload digest).",
    )


def test_every_allowlist_entry_answers_a_live_occurrence(declarations: tuple[Declaration, ...]) -> None:
    stale = stale_exemptions(declarations)
    assert not stale, (
        "These allowlist entries no longer match any site. A stale exemption reads as a "
        "considered judgement about code that has since moved or been fixed, and it "
        "silently widens to whatever later occupies its key. Remove each, or correct "
        "its path/symbol:\n" + "\n".join(f"  {entry.path}:{entry.symbol} -- {entry.reason}" for entry in stale)
    )
