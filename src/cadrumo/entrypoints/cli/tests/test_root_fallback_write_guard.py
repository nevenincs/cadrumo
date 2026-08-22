"""Live callback-policy contract for the root storage write guard."""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from ....application.storage_write_policy import StorageWritePolicyCode, inspect_storage_write_policy
from ....core.config import Settings, override_settings
from ....tests.cli_runner import cadrumo_click_command
from ....tests.secure_sql import isolated_profile_storage_root
from ...cli import app
from .. import _activate_active_bucket_session
from .._bootstrap_exempt import LOGIN_GATED_VERB_PATHS, is_bootstrap_exempt
from .._command_policy import command_execution_policy
from .._command_suggestions import execution_policy_for_cli_path, walk_live_command_tree
from .._errors import CliRefusedBoundaryError, error_boundary_under_test
from .._ledger_execution_policies import LEDGER_WRITE

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _live_leaf_routes() -> dict[tuple[str, ...], str]:
    return {
        node.path[1:]: node.execution_policy.write_route
        for node in walk_live_command_tree(app)
        if node.kind == "leaf" and node.execution_policy is not None
    }


def test_every_live_leaf_route_comes_from_its_callback_policy() -> None:
    """Exact-set enrollment follows the live tree, with no path roster."""
    nodes = tuple(node for node in walk_live_command_tree(app) if node.kind == "leaf")
    routes = _live_leaf_routes()

    assert set(routes) == {node.path[1:] for node in nodes}
    for node in nodes:
        assert node.execution_policy is not None
        assert execution_policy_for_cli_path(app, node.path[1:]) is node.execution_policy


def test_profile_bound_policy_reaches_the_route_refusal(tmp_path: Path) -> None:
    policy = execution_policy_for_cli_path(app, ("app", "ledger", "add"))
    assert policy.write_route == "profile-bound"

    decision = inspect_storage_write_policy(
        policy.write_route,
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    assert decision.allowed is False
    assert decision.code is StorageWritePolicyCode.REFUSED_ROOT_FALLBACK


def test_bootstrap_root_policy_bypasses_route_inspection(tmp_path: Path) -> None:
    policy = execution_policy_for_cli_path(app, ("config", "profile", "create"))
    assert policy.write_route == "bootstrap-root"

    decision = inspect_storage_write_policy(
        policy.write_route,
        settings=Settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        ),
    )
    assert decision.allowed is True
    assert decision.code is StorageWritePolicyCode.BOOTSTRAP_EXEMPT


def test_every_mutating_session_exemption_declares_bootstrap_root() -> None:
    failures = []
    for node in walk_live_command_tree(app):
        policy = node.execution_policy
        path = " ".join(node.path[1:])
        if (
            node.kind == "leaf"
            and policy is not None
            and "local-state" in policy.classification.side_effects
            and is_bootstrap_exempt(path)
            and policy.write_route != "bootstrap-root"
        ):
            failures.append(path)
    assert failures == []


def test_every_non_exempt_bootstrap_root_route_has_a_login_gate_justification() -> None:
    login_gated = {entry.verb_path for entry in LOGIN_GATED_VERB_PATHS}
    unexplained = []
    for path, write_route in _live_leaf_routes().items():
        rendered = " ".join(path)
        if write_route == "bootstrap-root" and not is_bootstrap_exempt(rendered) and rendered not in login_gated:
            unexplained.append(rendered)
    assert unexplained == []


def test_login_recovery_door_reaches_its_target_resolver(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path), override_settings(cadrumo_output_language="en"):
        result = CliRunner().invoke(app, ["config", "login", "does-not-exist"])

    assert result.exit_code != 0
    assert "Unknown profile" in result.output
    assert "No active profile" not in result.output


def test_real_root_dispatch_refuses_profile_write_before_root_database_creation(tmp_path: Path) -> None:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError),
    ):
        cadrumo_click_command().main(
            args=["app", "modelo", "work", "verify", "revision-id"],
            prog_name="aeat",
            standalone_mode=False,
        )

    assert tuple(storage_root.rglob("*.db")) == ()


def test_real_root_dispatch_refuses_profile_write_before_explicit_database_creation(tmp_path: Path) -> None:
    explicit_database = tmp_path / "explicit.db"
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_database_url=f"sqlite:///{explicit_database.as_posix()}"),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError),
    ):
        cadrumo_click_command().main(
            args=["config", "google", "login"],
            prog_name="aeat",
            standalone_mode=False,
        )

    assert not explicit_database.exists()


def test_unclassified_planted_leaf_fails_closed() -> None:
    planted = typer.Typer(name="planted", invoke_without_command=True)

    @planted.callback()
    @command_execution_policy(LEDGER_WRITE)
    def _root() -> None:
        return None

    @planted.command("write")
    def _write() -> None:
        return None

    with pytest.raises(LookupError, match="no execution policy"):
        execution_policy_for_cli_path(planted, ("write",))


def test_a_policy_downgrade_changes_the_guard_decision(tmp_path: Path) -> None:
    guarded = inspect_storage_write_policy(
        LEDGER_WRITE.write_route,
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    downgraded_policy = replace(LEDGER_WRITE, write_route="none")
    downgraded = inspect_storage_write_policy(
        downgraded_policy.write_route,
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )

    assert guarded.allowed is False
    assert downgraded.allowed is True


def test_callback_policy_survives_a_command_rename() -> None:
    renamed = typer.Typer(name="renamed")

    @command_execution_policy(LEDGER_WRITE)
    def _write() -> None:
        return None

    renamed.command("before")(_write)
    renamed.command("after")(_write)

    before = execution_policy_for_cli_path(renamed, ("before",))
    after = execution_policy_for_cli_path(renamed, ("after",))
    assert before is after is LEDGER_WRITE


def test_root_guard_has_no_path_catalogue_or_eager_policy_query_import() -> None:
    source = inspect.getsource(_activate_active_bucket_session)

    assert "_execution_policy_for_cli_path" in source
    assert source.index('execution_policy.write_route == "profile-bound"') < source.index(
        "from ...application.storage_write_policy import inspect_storage_write_policy"
    )


def test_profile_inventory_does_not_import_the_application_write_query(tmp_path: Path) -> None:
    script = """
import json
import sys
from typer.testing import CliRunner
from cadrumo.entrypoints.cli import app
result = CliRunner().invoke(app, ["config", "profile", "list"])
print(json.dumps({
    "exit_code": result.exit_code,
    "write_query_imported": "cadrumo.application.storage_write_policy" in sys.modules,
}))
"""
    environment = dict(os.environ)
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(tmp_path / "storage")
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv; probe source is a test-local literal.
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == '{"exit_code": 0, "write_query_imported": false}'
