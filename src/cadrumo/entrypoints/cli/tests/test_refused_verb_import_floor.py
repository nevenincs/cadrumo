"""A refused or metadata-only CLI run must not import work it never reaches."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.tests.cli_fixture_ports import FreshCliInvocation

from ....adapters.persistence.storage.tests.secure_sql import dev_test_database_password, isolated_profile_storage_root
from ....core.i18n.render import tr

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEDGER_WORK = (
    "cadrumo.entrypoints.cli._ledger_support",
    "cadrumo.entrypoints.cli._ledger_list",
    "cadrumo.entrypoints.ledger_action_composition",
)
_ECB_ADAPTER = "cadrumo.adapters.outbound.fx.ecb_provider"
_SQL_PROFILE_STORAGE = (
    "cadrumo.adapters.persistence.profile.buckets",
    "cadrumo.adapters.persistence.profile._secure_enveloped_document",
    "cadrumo.adapters.persistence.storage.sql.secure_objects",
)
_WATCHED = (*_LEDGER_WORK, _ECB_ADAPTER, *_SQL_PROFILE_STORAGE)


def _loaded_after(
    fresh_cli: FreshCliInvocation,
    *args: str,
    tmp_path: Path,
    storage_root: Path,
    site_dir: Path | None = None,
) -> tuple[int, str, list[str]]:
    """Run the console entry point in a fresh interpreter and report watched imports."""
    report = tmp_path / "imports.json"
    env = os.environ.copy()
    for name in ("CADRUMO_ACTIVE_PROFILE", "CADRUMO_DATABASE_URL", "CADRUMO_OUTPUT_LANGUAGE"):
        env.pop(name, None)
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(),
            "CADRUMO_OUTPUT_LANGUAGE": "es",
        }
    )
    result = fresh_cli(args, env=env, watched_modules=_WATCHED, import_report=report, site_dir=site_dir)
    completed = result.completed
    return completed.returncode, completed.stdout + completed.stderr, list(result.loaded_modules)


def test_a_ledger_verb_refused_for_want_of_a_profile_imports_no_ledger_or_sql_storage(
    tmp_path: Path, fresh_cli: FreshCliInvocation
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        returncode, output, loaded = _loaded_after(
            fresh_cli, "app", "ledger", "list", tmp_path=tmp_path, storage_root=storage_root
        )

    assert returncode == 2, output
    assert tr("cli.config.errors.no_active_profile", locale="es") in output
    assert loaded == []


def test_a_profile_free_verb_imports_no_sql_profile_storage(tmp_path: Path, fresh_cli: FreshCliInvocation) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        returncode, output, loaded = _loaded_after(
            fresh_cli,
            "--format",
            "json",
            "app",
            "live",
            "portals",
            "list",
            tmp_path=tmp_path,
            storage_root=storage_root,
        )

    assert returncode == 0, output
    assert loaded == []


def test_help_does_not_import_the_exchange_rate_adapter(tmp_path: Path, fresh_cli: FreshCliInvocation) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        returncode, output, loaded = _loaded_after(
            fresh_cli, "app", "ledger", "list", "--help", tmp_path=tmp_path, storage_root=storage_root
        )

    assert returncode == 0, output
    assert loaded == []


def test_the_import_probe_reports_an_eagerly_imported_module(tmp_path: Path, fresh_cli: FreshCliInvocation) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "sitecustomize.py").write_text(
        "".join(f"import {name}\n" for name in _WATCHED),
        encoding="utf-8",
    )
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _, output, loaded = _loaded_after(
            fresh_cli, "app", "ledger", "list", tmp_path=tmp_path, storage_root=storage_root, site_dir=site_dir
        )

    assert loaded == sorted(_WATCHED), output
