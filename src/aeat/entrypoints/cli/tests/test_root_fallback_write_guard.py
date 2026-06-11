"""Real-entrypoint regressions for the root-fallback write guard."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from ....application.storage_write_policy import is_profile_bound_write_verb_path
from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_GUARDED_WRITE_VERBS: tuple[tuple[str, ...], ...] = (
    ("config", "auth", "login"),
    ("app", "ledger", "link", "tx", "--invoice-id", "inv"),
    ("app", "modelo", "work", "verify", "abc"),
    ("config", "profile", "censo", "refresh"),
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
    "config profile censo refresh",
    "config profile censo apply",
    "app ledger inventory valuation preview actividad 2026",
)

_UNGARDED_PREDICATE_PATHS: tuple[str, ...] = (
    "config switch does-not-exist",
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

    from aeat.core import config as config_module
    from aeat.core.config import Settings, StorageRouteKind, classify_storage_route

    storage_root = Path(sys.argv[1])
    cli_args = sys.argv[2:]
    settings = Settings(
        _env_file=None,
        aeat_local_storage_root=storage_root,
        aeat_active_profile=" ",
        aeat_secret_store_backend="unsecured",
        aeat_allow_unencrypted="1",
        aeat_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        route = classify_storage_route()
        assert route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE, route
        sys.argv = ["aeat", *cli_args]
        from aeat.entrypoints.cli import main

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

    from aeat.core import config as config_module
    from aeat.core.config import Settings, StorageRouteKind, classify_storage_route

    storage_root = Path(sys.argv[1])
    cli_args = sys.argv[2:]
    settings = Settings(
        _env_file=None,
        aeat_local_storage_root=storage_root,
        aeat_database_url=f"sqlite:///{(storage_root / 'explicit.db').as_posix()}",
        aeat_active_profile="operator",
        aeat_secret_store_backend="unsecured",
        aeat_allow_unencrypted="1",
        aeat_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        route = classify_storage_route()
        assert route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL, route
        sys.argv = ["aeat", *cli_args]
        from aeat.entrypoints.cli import main

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


def _run_aeat(storage_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
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


def _run_aeat_explicit_database(storage_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
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


@pytest.mark.parametrize("verb", _GUARDED_WRITE_VERBS, ids=lambda value: " ".join(value))
def test_guarded_write_verbs_refuse_root_fallback_database(tmp_path: Path, verb: tuple[str, ...]) -> None:
    """Profile-bound write verbs refuse before writing to the root fallback database."""

    result = _run_aeat(tmp_path, verb)

    assert result.returncode == 2, _combined_output(result)
    output = _combined_output(result)
    assert "No active profile" in output
    assert "profile create" in output
    assert not (tmp_path / "aeat.db").exists()


@pytest.mark.parametrize("verb", _GUARDED_WRITE_VERBS, ids=lambda value: " ".join(value))
def test_guarded_write_verbs_refuse_explicit_database_url(tmp_path: Path, verb: tuple[str, ...]) -> None:
    """Profile-bound write verbs refuse operator-supplied database URL routes."""

    result = _run_aeat_explicit_database(tmp_path, verb)

    assert result.returncode == 2, _combined_output(result)
    output = _combined_output(result)
    assert "Storage runtime is not ready" in output
    assert "database route is not attached to an active profile bucket" in output
    assert not (tmp_path / "explicit.db").exists()


@pytest.mark.parametrize("verb", _BOOTSTRAP_SAFE_PROBES, ids=lambda value: " ".join(value))
def test_bootstrap_safe_probes_still_run_on_root_fallback_database(tmp_path: Path, verb: tuple[str, ...]) -> None:
    """Help, repair object-integrity, and registry read probes remain available on a fresh root."""

    result = _run_aeat(tmp_path, verb)

    assert result.returncode == 0, _combined_output(result)
    assert "No active profile" not in _combined_output(result)


def test_config_switch_remains_recovery_path_on_root_fallback_database(tmp_path: Path) -> None:
    """`config switch` reaches profile resolution instead of the root-fallback guard."""

    result = _run_aeat(tmp_path, ("config", "switch", "does-not-exist"))

    assert result.returncode == 2, _combined_output(result)
    output = _combined_output(result)
    assert "Unknown profile: does-not-exist" in output
    assert "No active profile" not in output


@pytest.mark.parametrize("verb_path", _GUARDED_PREDICATE_PATHS)
def test_root_fallback_guard_predicate_covers_profile_bound_mutations(verb_path: str) -> None:
    """The central guard covers known mutation surfaces discovered during contract review."""

    assert is_profile_bound_write_verb_path(verb_path)


@pytest.mark.parametrize("verb_path", _UNGARDED_PREDICATE_PATHS)
def test_root_fallback_guard_predicate_leaves_read_and_recovery_paths_open(verb_path: str) -> None:
    """The central guard does not capture read-only probes or profile-switch recovery."""

    assert not is_profile_bound_write_verb_path(verb_path)


def test_cli_root_delegates_route_classification_to_backend_policy() -> None:
    """The CLI root must not own the storage-route write policy."""

    root_source = (PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "__init__.py").read_text(encoding="utf-8")

    assert "classify_storage_route" not in root_source
    assert "StorageRouteKind" not in root_source
    assert "_ROOT_FALLBACK_GUARDED_VERB_PATHS" not in root_source
    assert "inspect_storage_write_policy" in root_source
