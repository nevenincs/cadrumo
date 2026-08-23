"""Boundary regression: lock the `aeat app ledger` verb roster + vocabulary.

The 2026-05-15 amendment to app-modelo-shape locks ``link``, ``check``,
and ``preflight`` onto the ledger noun-group root. This test pins the
exact verb set so a future refactor cannot silently drop, rename, or
re-parent any of them, and asserts that the help-text vocabulary for
each of the three orthogonal-axis verbs honours the "local-only"
mandate.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from .._ledger import app as ledger_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Canonical ledger verb roster. Adding a verb here without updating the
# reviewed surface contract is drift; removing one breaks an established
# CLI surface. Sorted alphabetically.
EXPECTED_LEDGER_VERBS: frozenset[str] = frozenset(
    {
        "add",
        "allocate",
        "archive",
        "attach",
        "categories",
        "check",
        "classify",
        "doclink",
        "exclude",
        "export",
        "history",
        "import",
        "link",
        "list",
        "llm-diagnostics",
        "merge",
        "preflight",
        "pull-folder",
        "remove",
        "reset",
        "restore",
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


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def test_ledger_verb_roster_matches_canonical_spine() -> None:
    """The set of mounted ledger verbs equals the canonical roster.

    A missing verb means a service was un-mounted; an extra verb
    indicates an un-reviewed addition to the noun-group. Both cases
    require an explicit contract update to this expected set."""

    registered = frozenset(cmd.name for cmd in ledger_app.registered_commands)
    missing = EXPECTED_LEDGER_VERBS - registered
    extras = registered - EXPECTED_LEDGER_VERBS
    assert not missing, f"ledger verbs disappeared: {sorted(n for n in missing if n)}"
    assert not extras, f"ledger verbs added without test update: {sorted(n for n in extras if n)}"


def test_ledger_link_check_preflight_sit_at_noun_group_root() -> None:
    """The link/check/preflight trio is mounted directly under
    `aeat app ledger`, not under a sub-noun-group. The orthogonal-axis
    verbs must sit alongside the CRUD spine."""

    top_level = frozenset(n for n in (cmd.name for cmd in ledger_app.registered_commands) if n)
    assert LINK_CHECK_PREFLIGHT.issubset(top_level), (
        f"link/check/preflight not at root; mounted verbs: {sorted(top_level)}"
    )


# Count-side companion to the set-equality roster gate above.
# The canonical spine for `aeat app ledger` is the CRUD spine (add / view /
# list / update / remove / archive / reset) plus the ratified orthogonal axes
# (link / check / preflight) plus the ratified workflow axes (allocate / attach
# / categories / classify / doclink / export / history / import / merge /
# pull-folder / review / split / stash / status / track). Counting
# them independently of the set membership catches accidental verb-count
# drift (e.g. a verb silently re-parented but replaced by a similarly-named
# alias) that an exact-set match might still happen to satisfy if both the
# missing and the extra are accounted for in the expected set update.
_CRUD_SPINE_COUNT: int = 7  # add, view, list, update, remove, archive, reset
_RATIFIED_ORTHOGONAL_AXIS_COUNT: int = 3  # link, check, preflight
_RATIFIED_WORKFLOW_AXIS_COUNT: int = 18  # allocate attach categories classify
# doclink exclude export history import llm-diagnostics merge pull-folder
# restore review split stash status track
# `providers` listed the cloud LLM CLIs on PATH. The cloud inference path was
# deleted, so the verb had nothing left to list and went with it.
_EXPECTED_LEDGER_VERB_COUNT: int = _CRUD_SPINE_COUNT + _RATIFIED_ORTHOGONAL_AXIS_COUNT + _RATIFIED_WORKFLOW_AXIS_COUNT


def test_ledger_verb_count_matches_canonical_spine() -> None:
    """The mounted `aeat app ledger` verb count matches the canonical
    spine (CRUD + ratified orthogonal axes + ratified workflow axes).

    Count-side companion to :func:`test_ledger_verb_roster_matches_canonical_spine`.
    The two gates together pin both *which* verbs are mounted and *how many*,
    so an accidental verb swap (one removed + one added of similar name)
    cannot satisfy both gates without an explicit count update."""

    registered_count = len(ledger_app.registered_commands)
    assert registered_count == _EXPECTED_LEDGER_VERB_COUNT, (
        f"ledger verb count drifted: expected {_EXPECTED_LEDGER_VERB_COUNT} "
        f"(CRUD {_CRUD_SPINE_COUNT} + orthogonal axes "
        f"{_RATIFIED_ORTHOGONAL_AXIS_COUNT} + workflow axes "
        f"{_RATIFIED_WORKFLOW_AXIS_COUNT}); got {registered_count}: "
        f"{sorted(n for n in (cmd.name for cmd in ledger_app.registered_commands) if n)!r}"
    )


@pytest.mark.parametrize("verb", ["link", "check", "preflight"])
def test_ledger_orthogonal_verb_help_states_local_only(
    verb: str,
) -> None:
    """Every orthogonal-axis verb's help text must signal `local-only`
    so the operator cannot mistake it for an AEAT-contacting call.

    Spanish/Catalan/Hungarian translations must convey the same
    invariant. Tokens cover all four locales."""

    result = _invoke(["app", "ledger", verb, "--help"])
    assert result.exit_code == 0, result.output
    haystack = result.output.lower()
    assert any(token in haystack for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")), (
        result.output
    )


# Help-text enumeration gate. The `aeat app ledger --help`
# and `aeat app modelo --help` surfaces are the operator's first encounter
# with the noun-group's verb tree; if a canonical verb is mounted but
# omitted from help (e.g. by a missing tr() entry), the operator cannot
# discover it. This gate fails when help text omits any registered verb,
# catching that drift without depending on locale-string content.
def test_ledger_help_enumerates_every_registered_verb() -> None:
    """`aeat app ledger --help` lists every mounted verb so the operator
    can discover the noun-group's full surface from the help output alone."""

    result = _invoke(["app", "ledger", "--help"])
    assert result.exit_code == 0, result.output
    missing = sorted(cmd.name for cmd in ledger_app.registered_commands if cmd.name and cmd.name not in result.output)
    assert not missing, f"`aeat app ledger --help` omits registered verbs {missing!r}; help output: {result.output!r}"


def test_ledger_attach_help_names_purchase_evidence_creation_path() -> None:
    """`ledger attach --help` tells operators how to create the evidence id it consumes."""

    result = _invoke(["app", "ledger", "attach", "--help"])
    assert result.exit_code == 0, result.output
    assert "aeat app ledger evidence add" in result.output
    assert "--purchase-invoice-evidence-id" in result.output


def test_modelo_help_enumerates_every_registered_verb() -> None:
    """`aeat app modelo --help` lists every mounted verb so the operator
    can discover the noun-group's full surface from the help output alone."""

    from .._modelo import app as modelo_app

    result = _invoke(["app", "modelo", "--help"])
    assert result.exit_code == 0, result.output
    missing = sorted(cmd.name for cmd in modelo_app.registered_commands if cmd.name and cmd.name not in result.output)
    assert not missing, f"`aeat app modelo --help` omits registered verbs {missing!r}; help output: {result.output!r}"


# Canonical modelo top-level verb roster. The verbs are the registry/work
# surface (list, describe, casillas, formulas, readiness, aggregate),
# the work-unit lifecycle continuum (history, export), and the
# cross-modelo analytics (project, compare). Subgroups (`bindings`, `work`,
# `filing-record`, `verification-report`, `audit`, `iva-wallet`, `m036`,
# `reconcile`) carry the operational surfaces and are intentionally excluded
# from this top-level roster. The `reconcile` surface became a subgroup
# (`reconcile pull` | `reconcile file --file PATH` | `reconcile history`) in the
# cli-pull-file-standard rollout, which also retired the standalone
# `reconcile-from-justificante` sugar verb and folded `reconciliation-history`
# into `reconcile history`.
EXPECTED_MODELO_TOP_LEVEL_VERBS: frozenset[str] = frozenset(
    {
        "aggregate",
        "casilla",
        "casillas",
        "compare",
        "describe",
        "export",
        "formulas",
        "history",
        "list",
        "project",
        "readiness",
        "requires",
        "support-matrix",
    },
)


def test_modelo_top_level_verb_roster_matches_canonical_spine() -> None:
    """The set of top-level `aeat app modelo` verbs equals the canonical roster.

    Missing or extra entries are contract drift that requires an explicit
    update to :data:`EXPECTED_MODELO_TOP_LEVEL_VERBS`.
    Subgroup verbs (`work verify`, `audit export`, etc.) are governed by
    their own per-subgroup gates, not by this roster."""

    from .._modelo import app as modelo_app

    registered = frozenset(n for n in (cmd.name for cmd in modelo_app.registered_commands) if n)
    missing = EXPECTED_MODELO_TOP_LEVEL_VERBS - registered
    extras = registered - EXPECTED_MODELO_TOP_LEVEL_VERBS
    assert not missing, f"modelo verbs disappeared: {sorted(n for n in missing if n)}"
    assert not extras, f"modelo verbs added without test update: {sorted(n for n in extras if n)}"


# The append-only event-history verb is the sole operator-facing bucket
# surface and now mounts under the `config profile` group as
# `config profile history` (D1 family rename: the operator means their
# profile, not the storage bucket). This pins the live demand-loaded path.
def test_profile_history_verb_is_reachable_on_the_live_profile_path() -> None:
    """`config profile history` is the only operator-facing event-history verb.

    The standalone `config bucket` group was retired; the `history` verb
    merged into the existing `config profile` group. Resolve the live path so
    an eager Typer-object assertion cannot bypass the loader contract."""

    from .. import app
    from .._command_suggestions import resolve_command_path

    command = resolve_command_path(app, ("config", "profile", "history"))

    assert command.name == "history"


def test_profile_history_help_exposes_profile_argument_not_bucket_id() -> None:
    """The event-history surface accepts an operator profile token, not a storage noun."""

    result = _invoke(["config", "profile", "history", "--help"])

    assert result.exit_code == 0, result.output
    assert "BUCKET_ID" not in result.output
    # The optional positional is the operator "profile" token. Omission means
    # the authenticated active profile; the storage noun stays internal.
    assert "[profile]" in result.output
