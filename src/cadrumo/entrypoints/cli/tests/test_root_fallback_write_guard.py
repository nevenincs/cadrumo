"""Real-entrypoint regressions for the root-fallback write guard."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from ....application.storage_write_policy import (
    PROFILE_BOUND_WRITE_VERB_PATHS,
    is_profile_bound_write_verb_path,
)
from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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


def test_config_switch_remains_recovery_path_on_root_fallback_database(tmp_path: Path) -> None:
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

    def walk(command: object, prefix: list[str], parent: click.Context | None) -> None:
        ctx = click.Context(command, info_name=prefix[-1] if prefix else "aeat", parent=parent)  # type: ignore[arg-type]
        names = list(command.list_commands(ctx)) if hasattr(command, "list_commands") else []
        if not names:
            leaves.append(" ".join(prefix))
            return
        for name in sorted(names):
            child = command.get_command(ctx, name)  # type: ignore[attr-defined]
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

    root_source = (PROJECT_ROOT / "src" / "cadrumo" / "entrypoints" / "cli" / "__init__.py").read_text(encoding="utf-8")

    assert "classify_storage_route" not in root_source
    assert "StorageRouteKind" not in root_source
    assert "_ROOT_FALLBACK_GUARDED_VERB_PATHS" not in root_source
    assert "inspect_storage_write_policy" in root_source
