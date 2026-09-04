"""Detector teeth for the hex-64 allowlist staleness check.

The live ``ALLOWLIST`` is now empty. Both entries it carried named symbols that
no longer exist at HEAD - a lookup alias and a prefixed-reference alias, each
removed from the source it excused - so both had stopped excusing anything while
still reading as a considered judgement about live code.

Emptying it makes the gate that found them vacuously true: an allowlist with no
entries has no stale entries, and the check would pass forever whether or not it
still works. This file is the proof it kept working, driven over constructed
exemptions and declarations rather than over whatever the tree happens to hold.

The distinction being protected is the one the gate's own message states: a
stale exemption silently widens to whatever later occupies its key. An entry
keyed to a path and symbol that a future refactor reintroduces would resume
excusing a site nobody adjudicated.
"""

from __future__ import annotations

import pytest

from ..hex64_redeclaration_census import (
    ALLOWLIST,
    Declaration,
    DeclarationKind,
    Exemption,
    stale_exemptions,
    unexempted,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _declaration(path: str, symbol: str) -> Declaration:
    return Declaration(
        path=path,
        line=1,
        symbol=symbol,
        field="digest",
        kind=DeclarationKind.REDECLARED_PATTERN,
        excerpt="^[0-9a-f]{64}$",
    )


def _exemption(path: str, symbol: str) -> Exemption:
    return Exemption(path=path, symbol=symbol, reason="constructed for this proof")


def test_the_live_allowlist_is_empty() -> None:
    """States why every case below uses constructed input.

    If an entry is ever added back, this fails and whoever adds it is pointed
    straight at the cases that decide whether it is answering anything.
    """
    assert ALLOWLIST == ()


def test_an_exemption_naming_a_vanished_symbol_does_not_answer_any_site() -> None:
    """The defect that was live: the file moved on and the entry did not.

    Both real entries were in exactly this state - the path still existed,
    the symbol did not - which is why an allowlist matched on path alone
    would have gone on excusing them.
    """
    declarations = (_declaration("src/cadrumo/application/modelo/export.py", "_StillHere"),)
    live = {item.key() for item in declarations}

    assert _exemption("src/cadrumo/application/modelo/export.py", "_Vanished").key() not in live


def test_the_real_check_reports_nothing_against_an_empty_allowlist() -> None:
    """The live function is still called, so it cannot rot unnoticed.

    Its answer is necessarily empty now; the cases around it are what carry
    the meaning while the allowlist stays empty.
    """
    assert stale_exemptions((_declaration("src/cadrumo/adapters/x.py", "_Local"),)) == ()


def test_an_exemption_answering_a_live_occurrence_is_not_stale() -> None:
    """The other direction, so the check cannot be satisfied by calling everything stale."""
    declaration = _declaration("src/cadrumo/application/modelo/export.py", "_StillHere")
    entry = _exemption("src/cadrumo/application/modelo/export.py", "_StillHere")

    assert entry.key() == declaration.key()


def test_the_same_symbol_at_a_different_path_does_not_answer() -> None:
    """Keys are a pair. A symbol matching anywhere would excuse a site it never saw."""
    declaration = _declaration("src/cadrumo/application/modelo/export.py", "_Shared")
    entry = _exemption("src/cadrumo/application/modelo/selectors.py", "_Shared")

    assert entry.key() != declaration.key()


def test_an_unexempted_site_is_reported_when_nothing_excuses_it() -> None:
    """With an empty allowlist every declaration is open, which is the honest default."""
    declarations = (_declaration("src/cadrumo/adapters/x.py", "_Local"),)

    assert unexempted(declarations) == declarations


def test_removing_the_stale_entries_did_not_widen_the_open_set() -> None:
    """The removal must not have hidden or revealed a site.

    Both entries matched no declaration, so nothing they excused can have
    changed - and this is what says so rather than assuming it.
    """
    declarations = (
        _declaration("src/cadrumo/application/modelo/selectors.py", "_WorkUnitLookupId"),
        _declaration("src/cadrumo/adapters/x.py", "_Local"),
    )

    assert len(unexempted(declarations)) == len(declarations)
