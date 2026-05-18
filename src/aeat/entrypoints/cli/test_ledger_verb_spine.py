"""Boundary regression: lock the `aeat app ledger` verb roster + vocabulary.

The 2026-05-15 amendment to app-modelo-shape locks ``link``, ``check``,
and ``preflight`` onto the ledger noun-group root. This test pins the
exact verb set so a future refactor cannot silently drop, rename, or
re-parent any of them, and asserts that the help-text vocabulary for
each of the three orthogonal-axis verbs honours the "local-only"
mandate.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli import app
from aeat.entrypoints.cli._ledger import app as ledger_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Canonical ledger verb roster. Adding a verb here without the
# corresponding ADR amendment is a contract drift; removing one
# breaks an established CLI surface. Sorted alphabetically.
EXPECTED_LEDGER_VERBS: frozenset[str] = frozenset(
    {
        "add",
        "allocate",
        "archive",
        "attach",
        "check",
        "classify",
        "export",
        "history",
        "import",
        "link",
        "list",
        "merge",
        "preflight",
        "remove",
        "reset",
        "review",
        "split",
        "stash",
        "status",
        "track",
        "update",
        "view",
    },
)

LINK_CHECK_PREFLIGHT: frozenset[str] = frozenset({"link", "check", "preflight"})


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_ledger_verb_roster_matches_canonical_spine() -> None:
    """The set of mounted ledger verbs equals the canonical roster.

    A missing verb means a service was un-mounted; an extra verb
    indicates an un-reviewed addition to the noun-group. Both cases
    require an ADR amendment + an update to this expected set."""

    registered = frozenset(cmd.name for cmd in ledger_app.registered_commands)
    missing = EXPECTED_LEDGER_VERBS - registered
    extras = registered - EXPECTED_LEDGER_VERBS
    assert not missing, f"ledger verbs disappeared: {sorted(missing)}"
    assert not extras, f"ledger verbs added without test update: {sorted(extras)}"


def test_ledger_link_check_preflight_sit_at_noun_group_root() -> None:
    """The link/check/preflight trio is mounted directly under
    `aeat app ledger`, not under a sub-noun-group. The orthogonal-axis
    verbs must sit alongside the CRUD spine."""

    top_level = frozenset(cmd.name for cmd in ledger_app.registered_commands)
    assert LINK_CHECK_PREFLIGHT.issubset(top_level), (
        f"link/check/preflight not at root; mounted verbs: {sorted(top_level)}"
    )


@pytest.mark.parametrize("verb", ["link", "check", "preflight"])
def test_ledger_orthogonal_verb_help_states_local_only(
    cli_runner: CliRunner, verb: str,
) -> None:
    """Every orthogonal-axis verb's help text must signal `local-only`
    so the operator cannot mistake it for an AEAT-contacting call.

    Spanish/Catalan/Hungarian translations must convey the same
    invariant. Tokens cover all four locales."""

    result = cli_runner.invoke(app, ["app", "ledger", verb, "--help"])
    assert result.exit_code == 0, result.output
    haystack = result.output.lower()
    assert any(
        token in haystack
        for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output
