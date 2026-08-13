"""Real-entrypoint regressions for the root-fallback write guard.

The ``"cadrumo.db"`` literal below is deliberate, the same shape as
``core.tests.test_storage_route_classification``: the ``not (tmp_path /
"cadrumo.db").exists()`` assertions prove the guard refuses BEFORE writing
to the canonical root-fallback path, not merely before writing somewhere.
An accessor aimed at the wrong location by a Settings/classifier defect
would leave the assertion trivially satisfied -- the exact silent-pass
shape a refusal test must not risk.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from ....application.storage_write_policy import (
    PROFILE_BOUND_WRITE_VERB_PATHS,
    is_profile_bound_write_verb_path,
)
from ....tests import REPO_ROOT
from .._bootstrap_exempt import is_bootstrap_exempt

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"cadrumo.db"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


_GUARDED_WRITE_VERBS: tuple[tuple[str, ...], ...] = (
    ("config", "auth", "login"),
    ("app", "ledger", "link", "tx", "--invoice-id", "inv"),
    ("app", "modelo", "work", "verify", "abc"),
    ("app", "modelo", "work", "file", "abc"),
    ("app", "modelo", "export", "abc", "--output", "out.txt"),
)

_BOOTSTRAP_SAFE_PROBES: tuple[tuple[str, ...], ...] = (
    ("config", "--help"),
    ("app", "ledger", "--help"),
    ("config", "repair", "integrity", "objects"),
    ("app", "registry", "inspect"),
)

_GUARDED_PREDICATE_PATHS: tuple[str, ...] = (
    "app ledger link tx --invoice-id inv",
    "app ledger export --output out.csv",
    "app modelo work verify abc",
    "app modelo work file abc",
    "app modelo work amend --from-filing-record-id rec --kind complementaria --reason correction --set 1=2",
    "app modelo filing-record import work --evidence-kind justificante --evidence-id ev --set 1=2",
    "app modelo reconcile file work --file justificante.pdf",
    "app modelo export work --output out.txt",
    "app live verify nif-iva ESB12345678",
    "app live verify tgvi 12345678Z",
    "app live filed pull",
    "app live filed pull-sources",
    "app live notifications pull",
    "app live expedientes pull",
    "app live iva-wallet pull-history",
    "app ledger inventory valuation preview actividad 2026",
)

_UNGARDED_PREDICATE_PATHS: tuple[str, ...] = (
    "config login does-not-exist",
    "app registry inspect",
    "app ledger list",
    "app ledger view tx",
    "app modelo describe 303",
    "app live verify list",
    "config auth status",
)

_CLI_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings, StorageRouteKind, classify_storage_route

    storage_root = Path(sys.argv[1])
    cli_args = sys.argv[2:]
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=" ",
        cadrumo_secret_store_backend="unsecured",
        cadrumo_allow_unencrypted="1",
        cadrumo_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        route = classify_storage_route()
        assert route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE, route
        sys.argv = ["cadrumo", *cli_args]
        from cadrumo.entrypoints.cli import main

        main()
    finally:
        config_module._settings_override.reset(token)
    """,
)

_EXPLICIT_DATABASE_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings, StorageRouteKind, classify_storage_route

    storage_root = Path(sys.argv[1])
    cli_args = sys.argv[2:]
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_database_url=f"sqlite:///{(storage_root / 'explicit.db').as_posix()}",
        cadrumo_active_profile="operator",
        cadrumo_secret_store_backend="unsecured",
        cadrumo_allow_unencrypted="1",
        cadrumo_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        route = classify_storage_route()
        assert route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL, route
        sys.argv = ["cadrumo", *cli_args]
        from cadrumo.entrypoints.cli import main

        main()
    finally:
        config_module._settings_override.reset(token)
    """,
)


def _root_fallback_env(storage_root: Path) -> dict[str, str]:
    del storage_root
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    return env


def _run_cadrumo(storage_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _CLI_HARNESS, str(storage_root), *args],
        cwd=Path(__file__).parents[3],
        env=_root_fallback_env(storage_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120.0,
    )


def _run_cadrumo_explicit_database(storage_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _EXPLICIT_DATABASE_HARNESS, str(storage_root), *args],
        cwd=Path(__file__).parents[3],
        env=_root_fallback_env(storage_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120.0,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _case_output(args: tuple[str, ...], result: subprocess.CompletedProcess[str]) -> str:
    return f"case={' '.join(args)}\n{_combined_output(result)}"


def _assert_no_internal_import_leak(output: str) -> None:
    assert "Traceback" not in output
    assert "ImportError" not in output
    assert "register_work_revision_commands" not in output
    assert "_modelo_work_revision_cli" not in output


def test_guarded_write_verbs_refuse_root_fallback_database(tmp_path: Path) -> None:
    """Profile-bound write verbs refuse before writing to the root fallback database."""

    for verb in _GUARDED_WRITE_VERBS:
        result = _run_cadrumo(tmp_path, verb)

        output = _case_output(verb, result)
        _assert_no_internal_import_leak(output)
        assert result.returncode == 2, output
        assert "No active profile" in output
        assert "profile create" in output
        assert not (tmp_path / "cadrumo.db").exists(), output


def test_guarded_write_verbs_refuse_explicit_database_url(tmp_path: Path) -> None:
    """Profile-bound write verbs refuse operator-supplied database URL routes."""

    for verb in _GUARDED_WRITE_VERBS:
        result = _run_cadrumo_explicit_database(tmp_path, verb)

        output = _case_output(verb, result)
        _assert_no_internal_import_leak(output)
        assert result.returncode == 2, output
        assert "Storage runtime is not ready" in output
        assert "database route is not attached to an active profile bucket" in output
        assert "CADRUMO_DATABASE_URL" in output
        assert "CADRUMO_LOCAL_STORAGE_ROOT" in output
        assert not (tmp_path / "explicit.db").exists(), output


def test_bootstrap_safe_probes_still_run_on_root_fallback_database(tmp_path: Path) -> None:
    """Help, repair object-integrity, and registry read probes remain available on a fresh root."""

    for verb in _BOOTSTRAP_SAFE_PROBES:
        result = _run_cadrumo(tmp_path, verb)

        output = _case_output(verb, result)
        assert result.returncode == 0, output
        assert "No active profile" not in output


def test_config_login_remains_recovery_path_on_root_fallback_database(tmp_path: Path) -> None:
    """`config login` reaches profile resolution instead of the root-fallback guard."""

    result = _run_cadrumo(tmp_path, ("config", "login", "does-not-exist"))

    assert result.returncode == 2, _combined_output(result)
    output = _combined_output(result)
    assert "Unknown profile: does-not-exist" in output
    assert "No active profile" not in output


def test_minimal_registry_modelo_work_create_reaches_leaf_refusal_on_root_fallback_database(tmp_path: Path) -> None:
    """Minimal-registry modelos refuse with their legal route before the root profile guard."""

    result = _run_cadrumo(
        tmp_path,
        (
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "210",
            "--year",
            "2025",
            "--period",
            "EVENT-1",
            "--revision",
            "2025",
        ),
    )

    assert result.returncode == 2, _combined_output(result)
    output = _combined_output(result)
    assert "REFUSED_CLI_BOUNDARY" in output
    assert "Modelo 210" in output
    assert "G320" in output
    assert "No active profile" not in output
    assert "perfil activo" not in output
    assert not (tmp_path / "cadrumo.db").exists()


def test_root_fallback_guard_predicate_covers_profile_bound_mutations() -> None:
    """The central guard covers known mutation surfaces discovered during contract review."""

    for verb_path in _GUARDED_PREDICATE_PATHS:
        assert is_profile_bound_write_verb_path(verb_path), verb_path


def test_root_fallback_guard_predicate_leaves_read_and_recovery_paths_open() -> None:
    """The central guard does not capture read-only probes or profile-switch recovery."""

    for verb_path in _UNGARDED_PREDICATE_PATHS:
        assert not is_profile_bound_write_verb_path(verb_path), verb_path


def _live_leaf_paths() -> tuple[str, ...]:
    """Return every leaf command path in the fully-materialised CLI tree.

    The tree is lazy: walking it without draining the lazy registry yields a
    single leaf and would make every conformance assertion below vacuously
    true. The subtrees are materialised first for that reason.
    """
    import click
    import typer

    from ...cli import app
    from ._lazy_command_tree import materialise_lazy_subcommands

    materialise_lazy_subcommands(app)
    root = typer.main.get_command(app)

    leaves: list[str] = []

    # `command` stays `object` and the suppression below is load-bearing, not
    # laziness. Typer vendors its own click: the real runtime chain here is
    # `CadrumoTyperGroup -> typer.core.TyperGroup -> typer._click.core.Command`,
    # which shares NO ancestry with `click.core.Command` -- `isinstance(root,
    # click.Command)` is False, measured. So the walker genuinely hands a
    # typer-vendored command to a real `click.Context`, and that works only
    # because the two are structurally compatible. Annotating `click.Command`
    # here type-checks but asserts a subtype relation that does not hold, and
    # the tests fail on it. Removing the suppression honestly needs an adapter
    # across the two hierarchies, which is a design decision, not a cleanup.
    def walk(command: object, prefix: list[str], parent: click.Context | None) -> None:
        ctx = click.Context(command, info_name=prefix[-1] if prefix else "aeat", parent=parent)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        names = list(command.list_commands(ctx)) if hasattr(command, "list_commands") else []  # ty: ignore[call-non-callable]
        if not names:
            leaves.append(" ".join(prefix))
            return
        for name in sorted(names):
            child = command.get_command(ctx, name)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
            if child is not None:
                walk(child, [*prefix, name], ctx)

    walk(root, [], None)
    return tuple(leaves)


def _entry_matches_a_live_leaf(entry: str, leaves: tuple[str, ...]) -> bool:
    """Whether ``entry`` names, or prefixes, at least one live leaf path."""

    return any(leaf == entry or leaf.startswith(f"{entry} ") for leaf in leaves)


def test_every_guarded_write_path_names_a_live_command() -> None:
    """No catalogue entry may name a command path the CLI no longer exposes.

    The write guard matches by prefix, so an entry left behind by a verb
    rename silently stops matching anything: the renamed command is answered
    ``NON_PROFILE_BOUND_VERB`` and drops out of the profile-bound write guard
    entirely. That is a fail-OPEN, and it is invisible to the manifest parity
    gate because an unknown command key classifies as not-read-only, exactly
    like a live write verb.

    This binds the catalogue to the live command tree, which is the only
    surface that cannot drift away from what the operator can actually run.
    """

    leaves = _live_leaf_paths()
    assert len(leaves) > 100, f"materialisation failed; only {len(leaves)} leaves walked"

    stale = sorted(entry for entry in PROFILE_BOUND_WRITE_VERB_PATHS if not _entry_matches_a_live_leaf(entry, leaves))

    assert stale == [], (
        "write-guard catalogue entries naming no live command (these fall out of "
        f"the profile-bound write guard and fail OPEN): {stale}"
    )


def test_live_command_check_rejects_a_stale_catalogue_entry() -> None:
    """Anti-tautology proof for the catalogue conformance gate above.

    If the matcher accepted anything, the green result would carry no
    information. A path from the pre-collapse invoice grammar — the exact
    drift that put every invoice mutation outside the guard — must be
    rejected, while its live replacement is accepted.
    """

    leaves = _live_leaf_paths()

    assert not _entry_matches_a_live_leaf("app ledger payable-invoice add", leaves)
    assert not _entry_matches_a_live_leaf("app ledger collectible-invoice add", leaves)
    assert _entry_matches_a_live_leaf("app ledger invoice add", leaves)


def test_invoice_mutations_are_profile_bound_writes() -> None:
    """Invoice mutations write profile-bound storage and must stay guarded."""

    for verb_path in ("app ledger invoice add", "app ledger invoice update", "app ledger invoice remove"):
        assert is_profile_bound_write_verb_path(verb_path), verb_path


def test_cli_root_delegates_route_classification_to_backend_policy() -> None:
    """The CLI root must not own the storage-route write policy."""

    root_source = (REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli" / "__init__.py").read_text(encoding="utf-8")

    assert "classify_storage_route" not in root_source
    assert "StorageRouteKind" not in root_source
    assert "_ROOT_FALLBACK_GUARDED_VERB_PATHS" not in root_source
    assert "inspect_storage_write_policy" in root_source


# ---------------------------------------------------------------------------
# The profile-bound criterion, enforced rather than hand-maintained
# ---------------------------------------------------------------------------

#: Final tokens under ``app`` whose mutation of active-bucket state is
#: UNAMBIGUOUS across every family that mounts them.
#:
#: Deliberately narrow, and the exclusions are the interesting part. ``verify``,
#: ``export``, ``extract``, ``reconcile``, ``preview`` and ``wizard`` are NOT
#: here, because the same token means different things in different families:
#: ``app modelo work verify`` mutates revision state while ``app registry
#: verify`` reads bundled data, and ``app modelo export`` writes a file rather
#: than bucket state. Sorting those requires reading each verb, which is a
#: per-verb judgement and must not be performed mechanically -- a first cut of
#: this gate did exactly that and flagged eleven registry-read and
#: file-writing leaves as unguarded mutations.
#:
#: So this set buys a real, total guarantee over the verbs whose semantics are
#: not in doubt, and the ambiguous tail is tracked as a named residue rather
#: than silently swept into either half.
_APP_MUTATION_TOKENS: frozenset[str] = frozenset(
    {
        "add",
        "allocate",
        "apply",
        "archive",
        "attach",
        "classify",
        "confirm",
        "create",
        "discard",
        "exclude",
        "import",
        "link",
        "merge",
        "remove",
        "rename",
        "restore",
        "resume",
        "seed",
        "set",
        "split",
        "stash",
        "track",
        "unset",
        "update",
    }
)


def _app_leaves() -> tuple[str, ...]:
    """Live leaf paths under the ``app`` root."""

    return tuple(leaf for leaf in _live_leaf_paths() if leaf.split()[:1] == ["app"])


def test_every_unambiguously_mutating_app_leaf_is_guarded_or_bootstrap_exempt() -> None:
    """A TOKEN-MATCHED mutating ``app`` leaf must be guarded OR exempt, never neither.

    ``aeat app`` commands operate on the active profile bucket by definition,
    so a leaf that mutates one while sitting outside BOTH the profile-bound
    write guard and the bootstrap exemption is unreachable by either safety
    mechanism: it is answered ``NON_PROFILE_BOUND_VERB`` and the root write
    guard cannot refuse it under any storage route. That is the same fail-open
    that let every invoice mutation escape the guard after a verb rename, found
    only by asking the policy directly rather than by reading the catalogue.

    Stated as a rule so the catalogue is enforced rather than curated. Nine
    leaves were outside both mechanisms when this gate was written -- evidence
    confirm, ledger restore, three invoice-catalogue verbs, justificante pull,
    iva-wallet seed, m145 create and work resume. This gate is what stops the
    tenth.

    SCOPE, STATED HONESTLY: the guarantee is total over the leaves
    :data:`_APP_MUTATION_TOKENS` SELECTS, and silent everywhere else. It reads
    the last word of each leaf, so it examines a minority of the tree and never
    looks at the rest -- 38 of 200 live ``app`` leaves when this note was
    written, measured rather than estimated, and left undated-in-code on
    purpose so no assertion depends on a count that drifts with the tree. A
    mutating verb whose final token is absent from the set is invisible here no
    matter how plainly it writes: ``app modelo aggregate`` owns a durable
    observation write and ``app live iva-wallet pull-evidence`` persists an
    acquisition manifest, and neither is token-matched. Lengthening the token
    list does not fix that -- it re-arms the same failure one verb later, which
    is why the whole-tree census below exists as a second, name-independent
    mechanism. Do not read a green result here as "every mutating leaf is
    covered"; read it as "every leaf this set names is covered".
    """

    leaves = _app_leaves()
    assert len(leaves) > 100, f"materialisation failed; only {len(leaves)} app leaves walked"

    mutating = [leaf for leaf in leaves if leaf.split()[-1] in _APP_MUTATION_TOKENS]
    assert len(mutating) > 20, (
        f"only {len(mutating)} unambiguously-mutating app leaves found; the token set has "
        "collapsed against the live tree and this gate would pass while checking almost nothing"
    )

    unreachable = sorted(
        leaf for leaf in mutating if not is_profile_bound_write_verb_path(leaf) and not is_bootstrap_exempt(leaf)
    )

    assert unreachable == [], (
        "mutating `app` leaf/leaves reachable by NEITHER the profile-bound write guard NOR the "
        f"bootstrap exemption, so no storage-route refusal can apply to them: {unreachable}. "
        "Add each to `PROFILE_BOUND_WRITE_VERB_PATHS`, or to `BOOTSTRAP_EXEMPT_VERB_PATHS` if it "
        "must legitimately run before a profile is unlocked."
    )


def test_mutation_token_set_still_matches_live_verbs() -> None:
    """Every token in the set must name at least one live ``app`` leaf.

    The anti-vacuity companion. The gate above proves a property over the
    leaves the token set selects; this proves the set still selects real
    verbs. A token left behind by a rename silently narrows the guarantee, and
    a set that drifted entirely out of the tree would let the gate above pass
    over an empty selection while looking identical.
    """

    live_tokens = {leaf.split()[-1] for leaf in _app_leaves()}
    dead = sorted(_APP_MUTATION_TOKENS - live_tokens)

    assert dead == [], (
        f"mutation token(s) naming no live app verb: {dead}. Each silently narrows the "
        "criterion gate's coverage; remove it or restore the verb it was written for."
    )


# ---------------------------------------------------------------------------
# The whole-tree census: classification is mandatory, and names carry no weight
# ---------------------------------------------------------------------------

#: Every ``app`` leaf reviewed and determined NOT to mutate the active profile
#: bucket. Membership is a reviewer's assertion about what the handler WRITES,
#: reached by tracing it to its persistence call -- never an inference from the
#: verb's name.
#:
#: This roster exists so that "outside both safety mechanisms" stops being the
#: silent default. The token gate above answers a question only about the
#: leaves it selects; this set plus the two production catalogues must together
#: account for EVERY live ``app`` leaf, so a newly-added verb is unclassified
#: until somebody reads it. That is the whole point: the previous criterion
#: went blind whenever a mutating verb was named something its token list did
#: not anticipate, and a longer token list would only move the blind spot.
#:
#: The determinations behind the entries, grouped by why they do not write:
#:
#: - Pure reads and projections -- every ``list`` / ``view`` / ``show`` /
#:   ``status`` / ``history`` / ``latest`` leaf, plus ``ledger check``,
#:   ``ledger preflight``, ``ledger review``, ``modelo project``,
#:   ``modelo readiness``, ``modelo requires``, ``modelo compare``,
#:   ``modelo audit *``, ``m145 export`` / ``validate``, and the
#:   ``overview`` family. ``overview prepare`` is here despite its imperative
#:   name: it composes reads into a walkthrough and emits, writing nothing.
#: - Writes that land OUTSIDE the bucket -- ``modelo review-package build``,
#:   ``encrypt-for-recipient`` and ``encrypt-feedback`` write only to their
#:   ``--output`` path, and ``app agent`` materialises shipped harness data
#:   into an operator directory (its handler documents that it never enters
#:   the bucket session). Their signing / decrypting siblings are NOT here --
#:   those mint and persist a keypair into the bucket on first use.
#: - Reads that decrypt but never write -- ``diagnostics telemetry flush``
#:   builds a payload and hands it to the telemetry sink, and
#:   ``ledger evidence extract`` runs the extractor over stored bytes and
#:   returns a draft ("never mints or persists", per its own handler).
#:
#: Adding a leaf here is a claim that its write path was traced and found
#: absent. Do not add one to silence the census.
_REVIEWED_NON_MUTATING_APP_LEAVES: frozenset[str] = frozenset(
    {
        "app agent",
        "app contract",
        "app diagnostics errors",
        "app diagnostics latency",
        "app diagnostics llm-usage",
        "app diagnostics run-health",
        "app diagnostics runs",
        "app diagnostics telemetry flush",
        "app ledger bienes-inversion list",
        "app ledger check",
        "app ledger evidence extract",
        "app ledger evidence list",
        "app ledger evidence view",
        "app ledger history",
        "app ledger inventory list",
        "app ledger invoice list",
        "app ledger invoice view",
        "app ledger list",
        "app ledger llm-diagnostics",
        "app ledger preflight",
        "app ledger prorrata list",
        "app ledger ratios eligible",
        "app ledger ratios list",
        "app ledger ratios validate",
        "app ledger review",
        "app ledger rule list",
        "app ledger status",
        "app ledger view",
        "app live borrador 100 latest",
        "app live borrador 100 list",
        "app live borrador 100 view",
        "app live deudas latest",
        "app live deudas list",
        "app live deudas view",
        "app live expedientes latest",
        "app live expedientes list",
        "app live expedientes view",
        "app live filed list",
        "app live iva-wallet history",
        "app live justificante list",
        "app live justificante view",
        "app live notifications latest",
        "app live notifications list",
        "app live notifications view",
        "app live notifications document history",
        "app live notifications document view",
        "app live verify latest",
        "app live verify list",
        "app live verify view",
        "app modelo audit check",
        "app modelo audit export",
        "app modelo audit show",
        "app modelo bindings list",
        "app modelo bindings resolve",
        "app modelo compare",
        "app modelo filing-record list",
        "app modelo filing-record view",
        "app modelo history",
        "app modelo iva-wallet balance",
        "app modelo m036 list",
        "app modelo m036 view",
        "app modelo m145 export",
        "app modelo m145 validate",
        "app modelo project",
        "app modelo readiness",
        "app modelo requires",
        "app modelo review-package build",
        "app modelo review-package encrypt-feedback",
        "app modelo review-package encrypt-for-recipient",
        "app modelo verification-report list",
        "app modelo verification-report view",
        "app modelo work compare-taxation",
        "app modelo work dependencies",
        "app modelo work history",
        "app modelo work list",
        "app modelo work observations",
        "app modelo work preview-maritime-exemption",
        "app modelo work revision",
        "app modelo work revisions",
        "app modelo work runs",
        "app modelo work status",
        "app overview agenda",
        "app overview backlog",
        "app overview calendar",
        "app overview explain",
        "app overview pipeline",
        "app overview prepare",
        "app overview status",
        "app review queue",
        "app review view",
    }
)


def _classify_app_leaf(leaf: str) -> str:
    """Return which mechanism accounts for ``leaf``, or ``"unclassified"``.

    The three accounting mechanisms are mutually exclusive by intent, and
    :func:`test_app_leaf_classification_is_unambiguous` proves no leaf claims
    two of them.
    """

    if is_profile_bound_write_verb_path(leaf):
        return "guarded"
    if is_bootstrap_exempt(leaf):
        return "bootstrap_exempt"
    if leaf in _REVIEWED_NON_MUTATING_APP_LEAVES:
        return "reviewed_non_mutating"
    return "unclassified"


def test_every_app_leaf_is_accounted_for_by_name_independent_census() -> None:
    """Every live ``app`` leaf must be guarded, exempt, or reviewed non-mutating.

    The name-independent companion to the token gate above, and the mechanism
    that answers its blind spot. Where that gate asks "of the leaves whose last
    word I recognise, are they all covered?", this one walks the whole live
    tree and asks "is this leaf accounted for AT ALL?" -- so it cannot be
    defeated by a verb named something the token list never anticipated, which
    is exactly how the previous criterion went blind over 162 of 200 leaves.

    A leaf reaches ``unclassified`` only by being newly added, or by a rename
    that moved it out of a catalogue prefix. Either way the correct response is
    to READ the handler and trace what it writes, then record the answer in the
    matching mechanism. There is deliberately no fourth outcome and no
    allowlist: an unread verb is the failure this gate exists to surface.

    Twenty-five mutating leaves were unclassified when this census was
    written -- among them the three ``m036`` census declarations, both ``iva-wallet``
    correction verbs, the ledger and amend wizards, four ``review-package``
    verbs that mint a signing keypair into the bucket, and
    ``app modelo aggregate``, whose handler owns a durable observation write
    while carrying a name no mutation-token list would ever have selected.
    """

    leaves = _app_leaves()
    assert len(leaves) > 100, f"materialisation failed; only {len(leaves)} app leaves walked"

    unclassified = sorted(leaf for leaf in leaves if _classify_app_leaf(leaf) == "unclassified")

    assert unclassified == [], (
        f"`app` leaf/leaves accounted for by NO mechanism: {unclassified}. Read each handler and "
        "trace what it writes. If it mutates the active profile bucket, add it to "
        "`PROFILE_BOUND_WRITE_VERB_PATHS` (or to `BOOTSTRAP_EXEMPT_VERB_PATHS` when it must "
        "legitimately run before a profile is unlocked). If it does not, add it to "
        "`_REVIEWED_NON_MUTATING_APP_LEAVES` -- which asserts you traced its write path and found "
        "none, not that its name reads like a query."
    )


def test_app_leaf_classification_is_unambiguous() -> None:
    """No leaf may be claimed by two accounting mechanisms at once.

    The anti-vacuity floor for the census: it classifies by first match, so a
    roster entry that is ALSO guarded or exempt would be silently shadowed and
    the roster could accumulate contradictory claims without ever failing. A
    leaf declared non-mutating while sitting in the write catalogue is a
    genuine disagreement about what the verb does, and must be resolved rather
    than ranked.
    """

    contradictory = sorted(
        leaf
        for leaf in _REVIEWED_NON_MUTATING_APP_LEAVES
        if is_profile_bound_write_verb_path(leaf) or is_bootstrap_exempt(leaf)
    )

    assert contradictory == [], (
        f"leaf/leaves declared non-mutating while ALSO guarded or bootstrap-exempt: {contradictory}. "
        "One of the two declarations is wrong; read the handler and remove the other."
    )


def test_reviewed_non_mutating_roster_names_only_live_commands() -> None:
    """Every roster entry must name a live leaf, and the roster must be populated.

    The second anti-vacuity floor, and the same failure mode
    :func:`test_every_guarded_write_path_names_a_live_command` guards on the
    production catalogue. A roster entry left behind by a rename is a
    determination about a verb that no longer exists, and it makes the census
    look better-reviewed than it is. Emptiness is checked too: an empty roster
    would make the census above pass only because everything else is guarded,
    which is a different property than the one claimed.
    """

    leaves = set(_app_leaves())
    assert len(_REVIEWED_NON_MUTATING_APP_LEAVES) > 50, (
        f"only {len(_REVIEWED_NON_MUTATING_APP_LEAVES)} reviewed non-mutating leaves declared; the "
        "roster has collapsed against the live tree and the census would be asserting far less "
        "than it appears to"
    )

    stale = sorted(entry for entry in _REVIEWED_NON_MUTATING_APP_LEAVES if entry not in leaves)

    assert stale == [], (
        f"reviewed-non-mutating entries naming no live leaf: {stale}. Each is a determination about "
        "a command that no longer exists; drop it, or restore the entry to the name the verb now has."
    )


def test_census_covers_leaves_the_mutation_token_heuristic_cannot_see() -> None:
    """Anti-tautology proof that the census is a genuinely wider mechanism.

    A second gate that merely re-derived the first one's selection would add
    confidence without adding coverage. This pins the difference concretely.

    ``app modelo aggregate`` and ``app live iva-wallet pull-evidence`` both
    mutate the active bucket -- the first owns a durable observation write, the
    second persists an acquisition manifest -- and NEITHER is selected by
    :data:`_APP_MUTATION_TOKENS`, so the token gate is green over both no
    matter how they are classified. The census reaches them because it walks
    every leaf.

    The second half proves the property is about names carrying no weight, not
    about these two verbs: a leaf whose final token is entirely unknown to the
    heuristic is invisible to it and unclassified to the census.
    """

    token_blind = ("app modelo aggregate", "app live iva-wallet pull-evidence")
    for leaf in token_blind:
        assert leaf.split()[-1] not in _APP_MUTATION_TOKENS, (
            f"{leaf!r} is now token-matched, so it no longer demonstrates the gap this proof pins; "
            "pick another leaf the heuristic cannot see"
        )
        assert _classify_app_leaf(leaf) != "unclassified", f"{leaf!r} must be accounted for by the census"

    unregistered = "app ledger a-verb-that-was-just-invented"
    assert unregistered.split()[-1] not in _APP_MUTATION_TOKENS
    assert _classify_app_leaf(unregistered) == "unclassified", (
        "a leaf in no catalogue and no roster must be reported unclassified; if this passes "
        "trivially the census has stopped distinguishing reviewed leaves from unread ones"
    )


# ---------------------------------------------------------------------------
# The hyphenated near-miss: a leaf that LOOKS covered by prefix matching
# ---------------------------------------------------------------------------


def _hyphenated_near_miss_findings(
    leaves: tuple[str, ...],
    *,
    catalogue: tuple[str, ...] = PROFILE_BOUND_WRITE_VERB_PATHS,
) -> tuple[tuple[str, str], ...]:
    """Return ``(leaf, guarded_stem)`` pairs for leaves that hyphen-extend a guarded entry.

    :func:`is_profile_bound_write_verb_path` continues past a catalogue entry
    only on a SPACE, because the characters that follow a matched prefix are
    meant to be positional arguments. A leaf that continues the same stem with
    a HYPHEN is therefore a different verb wearing a guarded verb's name, and
    it matches nothing -- which is invisible precisely because it reads as
    though it were covered.

    Reported, never auto-guarded. Widening the matcher to treat ``-`` as a
    boundary would silently pull every future hyphenated verb under a refusal
    nobody reviewed, trading a visible fail-open for an invisible fail-closed.
    The point of surfacing the near-miss is that the next one gets a decision.
    """

    findings: list[tuple[str, str]] = []
    for leaf in leaves:
        if is_profile_bound_write_verb_path(leaf) or is_bootstrap_exempt(leaf):
            continue
        stem = next((entry for entry in catalogue if leaf.startswith(f"{entry}-")), None)
        if stem is not None:
            findings.append((leaf, stem))
    return tuple(sorted(findings))


def test_no_leaf_hyphen_extends_a_guarded_entry_without_its_own_decision() -> None:
    """A hyphenated sibling of a guarded verb must carry its own decision.

    The trap this surfaces is structural rather than a spelling mistake:
    ``app live iva-wallet pull`` is guarded, so ``pull-evidence`` reads as
    covered to anyone scanning the catalogue -- and is not, because the matcher
    joins on a space. It persisted an acquisition manifest into the encrypted
    live-IVA namespace while answerable by no storage-route refusal, and the
    same shape put ``app modelo work amend-wizard`` outside the guard that
    covers ``app modelo work amend``.

    Both are now explicitly guarded, so this gate is EMPTY at rest. That is the
    hazard it has to be built against: an empty finding set is what a working
    detector and a broken one both look like, which is why
    :func:`test_hyphenated_near_miss_detector_fires_on_a_planted_leaf` plants a
    leaf of exactly this shape and proves it is caught.

    A finding here is not automatically a fail-open -- the leaf may genuinely
    read. It is a leaf whose coverage was decided by punctuation instead of by
    somebody reading it, and the fix is an explicit catalogue entry or an
    explicit roster entry, never a wider matcher.
    """

    leaves = _live_leaf_paths()
    assert len(leaves) > 100, f"materialisation failed; only {len(leaves)} leaves walked"
    assert len(PROFILE_BOUND_WRITE_VERB_PATHS) > 40, (
        f"write-guard catalogue collapsed to {len(PROFILE_BOUND_WRITE_VERB_PATHS)} entries; with no "
        "stems to extend, a green result below would mean 'nothing was screened'"
    )

    findings = _hyphenated_near_miss_findings(leaves)

    assert findings == (), (
        "leaf/leaves that hyphen-extend a guarded catalogue entry while guarded by nothing "
        f"themselves: {[f'{leaf} (extends {stem!r})' for leaf, stem in findings]}. Prefix matching "
        "continues only on a space, so each reads as covered and is not. Read the handler, then add "
        "it to `PROFILE_BOUND_WRITE_VERB_PATHS` if it mutates the active bucket or to "
        "`_REVIEWED_NON_MUTATING_APP_LEAVES` if it does not. Do NOT widen the matcher to split on "
        "`-`: that would auto-guard every future hyphenated verb without anyone deciding it should be."
    )


def test_hyphenated_near_miss_detector_fires_on_a_planted_leaf() -> None:
    """Positive control for the gate above, which is empty at rest.

    Without this, the green result carries no information: a detector that
    never matches anything and a tree that genuinely holds no near-miss are
    indistinguishable from the outside. So a leaf of exactly the trapped shape
    is planted into the walked set and must come back flagged.

    ``app ledger add-batch`` does not exist. It is built to extend the real
    guarded entry ``app ledger add`` with a hyphen, which is the precise
    construction that made ``pull-evidence`` unreachable. Its preconditions are
    asserted rather than assumed, so if a future catalogue entry ever covers it
    this control fails loudly instead of quietly proving nothing.
    """

    planted = "app ledger add-batch"
    stem = "app ledger add"

    assert stem in PROFILE_BOUND_WRITE_VERB_PATHS, f"{stem!r} left the catalogue; the control needs a live stem"
    assert not is_profile_bound_write_verb_path(planted), (
        f"{planted!r} is now guarded, so planting it proves nothing; pick an unguarded hyphen-extension"
    )
    assert not is_bootstrap_exempt(planted)

    findings = _hyphenated_near_miss_findings((*_live_leaf_paths(), planted))

    assert findings == ((planted, stem),), (
        f"the detector failed to flag a planted hyphen-extension of a guarded entry: {findings}. It "
        "could not have flagged a real one either, so the empty result above is not evidence."
    )


def test_the_known_hyphenated_near_misses_carry_their_own_catalogue_entries() -> None:
    """Regression pin on the two live members of the class.

    Both were found by tracing rather than by any gate, and both are guarded
    only because an explicit entry was added -- the stem's entry does not and
    cannot cover them. Dropping either explicit entry silently reopens the
    original fail-open while the stem still sits in the catalogue looking like
    coverage, so the relationship is pinned here rather than left to be
    rediscovered.
    """

    for leaf, stem in (
        ("app live iva-wallet pull-evidence", "app live iva-wallet pull"),
        ("app modelo work amend-wizard", "app modelo work amend"),
    ):
        assert leaf.startswith(f"{stem}-"), f"{leaf!r} no longer hyphen-extends {stem!r}"
        assert stem in PROFILE_BOUND_WRITE_VERB_PATHS, f"{stem!r} left the catalogue"
        assert leaf in PROFILE_BOUND_WRITE_VERB_PATHS, (
            f"{leaf!r} lost its own catalogue entry. The {stem!r} entry does NOT cover it -- prefix "
            "matching continues only on a space -- so it is unguarded again."
        )
