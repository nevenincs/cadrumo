"""Exact-set, identity, and import gates for the complete app subtree."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import typer

from cadrumo.tests.cli_performance import profile_cli_path

from .. import app
from .._app_lazy_registration import APP_COMMAND_RECORDS, APP_COMMAND_TARGETS, AppCommandTarget
from .._command_suggestions import (
    LazyFactoryTarget,
    LazyImportTarget,
    LiveCommandNode,
    lazy_subcommand_target,
    walk_live_command_tree,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FAMILIES = frozenset(
    {"diagnostics", "ledger", "live", "maintenance", "modelo", "overview", "quickfile", "registry", "review"}
)


def _app_nodes(root: typer.Typer) -> tuple[LiveCommandNode, ...]:
    return tuple(
        node
        for node in walk_live_command_tree(root)
        if len(node.path) >= 3 and node.path[1] == "app" and node.path[2] in _FAMILIES
    )


def _require_exact_targets(nodes: tuple[LiveCommandNode, ...]) -> None:
    records = {record.path: record for record in APP_COMMAND_RECORDS}
    for node in nodes:
        relative = node.path[2:]
        record = records.get(relative)
        assert record is not None, f"app node {' '.join(node.path)!r} is absent from generated source evidence"
        assert record.kind == node.kind
        if len(relative) == 1:
            target = lazy_subcommand_target("app", relative[0])
            if relative == ("quickfile",):
                assert isinstance(target, LazyImportTarget)
                assert target.owner == "cadrumo.entrypoints.cli._app_quickfile:app"
            else:
                assert isinstance(target, LazyImportTarget)
                assert target.owner == f"cadrumo.entrypoints.cli._app_lazy_families:{relative[0]}_app"
            assert node.loader_owner == target.owner
            continue
        concrete = APP_COMMAND_TARGETS.get(relative)
        assert isinstance(concrete, AppCommandTarget)
        parent_key = "app." + ".".join(relative[:-1])
        target = lazy_subcommand_target(parent_key, relative[-1])
        assert isinstance(target, LazyFactoryTarget)
        assert target.factory is concrete
        assert node.loader_owner == target.owner


def test_complete_live_app_tree_is_generated_nested_lazy_and_path_owned() -> None:
    nodes = _app_nodes(app)
    actual = {node.path[2:] for node in nodes}
    expected = {record.path for record in APP_COMMAND_RECORDS}
    assert actual == expected
    assert len({id(target) for target in APP_COMMAND_TARGETS.values()}) == len(APP_COMMAND_TARGETS)
    _require_exact_targets(nodes)
    assert _app_nodes(app) == nodes


def test_generated_four_locale_source_manifest_is_current() -> None:
    completed = subprocess.run(  # noqa: S603 - repository-owned generator with fixed argv
        [sys.executable, "dev/quality/generate_app_lazy_manifest.py", "--check"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_omission_forged_owner_and_eager_registration_fail_the_exact_gate() -> None:
    nodes = _app_nodes(app)
    with pytest.raises(AssertionError):
        _require_exact_targets(nodes[1:])

    victim = next(node for node in nodes if node.path[2:] == ("modelo", "audit", "check"))
    forged = replace(victim, loader_owner="forged:owner")
    with pytest.raises(AssertionError):
        _require_exact_targets(tuple(forged if node is victim else node for node in nodes))

    eager = replace(victim, loader_owner=None)
    with pytest.raises(AssertionError):
        _require_exact_targets(tuple(eager if node is victim else node for node in nodes))


@pytest.mark.parametrize(
    ("path", "owning_modules", "forbidden_modules"),
    [
        (("app", "diagnostics", "run-health"), {"_app_diagnostics"}, {"_app_diagnostics_telemetry"}),
        (("app", "ledger", "view"), {"_ledger_read_cli"}, {"_ledger", "_ledger_import_cli"}),
        (("app", "live", "notifications", "list"), {"_app_live_notifications_cli"}, {"_app_live"}),
        (("app", "maintenance", "reconcile"), {"_app_maintenance"}, set()),
        (("app", "modelo", "audit", "check"), {"_modelo_audit_cli"}, {"_modelo"}),
        (("app", "overview", "status"), {"_overview"}, set()),
        (("app", "registry", "inspect"), {"registry"}, set()),
        (("app", "review", "queue"), {"_review"}, set()),
    ],
)
def test_selected_leaf_imports_only_its_own_app_subfamily(
    path: tuple[str, ...],
    owning_modules: set[str],
    forbidden_modules: set[str],
    tmp_path: Path,
) -> None:
    observation = profile_cli_path(path, storage_root=tmp_path / "storage").resolution
    assert observation.exit_code == 0
    cli_modules = {
        module.rsplit(".", 1)[-1]
        for module in observation.imported_modules
        if module.startswith("cadrumo.entrypoints.cli.")
    }
    assert owning_modules <= cli_modules
    assert cli_modules.isdisjoint(forbidden_modules)
