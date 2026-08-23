"""Exact-set and import contracts for the demand-loaded config subtree."""

from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from cadrumo.tests.cli_performance import profile_cli_path

from ... import app as root_app
from ..._command_policy import command_execution_policy
from ..._command_suggestions import CadrumoTyperGroup, LiveCommandNode, walk_live_command_tree
from .._execution_policies import STATE_FREE
from .._lazy_registration import _GROUP_HELP_KEYS, _LEAF_HELP_KEYS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _config_nodes(app: typer.Typer) -> tuple[LiveCommandNode, ...]:
    return tuple(node for node in walk_live_command_tree(app) if node.path[1:2] == ("config",))


def _require_exact_config_loader_ownership(nodes: tuple[LiveCommandNode, ...]) -> None:
    for node in nodes:
        if node.path == ("aeat", "config"):
            expected = "cadrumo.entrypoints.cli._config:app"
        else:
            slug = "__".join(node.path[2:]).replace("-", "_")
            expected = (
                "cadrumo.entrypoints.cli._config._lazy_registration:"
                f"config_targets.load_{slug}"
            )
        assert node.loader_owner == expected, (
            f"config node {' '.join(node.path)!r} is not owned by its exact lazy target: "
            f"expected {expected!r}, got {node.loader_owner!r}"
        )


def test_live_config_exact_set_is_nested_lazy_and_path_owned() -> None:
    """The manifest and current live tree agree without freezing a verb count."""
    nodes = _config_nodes(root_app)
    actual = {node.path[2:] for node in nodes if len(node.path) > 2}
    declared = {*_GROUP_HELP_KEYS, *_LEAF_HELP_KEYS}

    assert actual == declared
    assert _GROUP_HELP_KEYS.keys().isdisjoint(_LEAF_HELP_KEYS)
    assert all(node.execution_policy is not None for node in nodes)
    _require_exact_config_loader_ownership(nodes)


def test_eager_and_forged_loader_owners_cannot_satisfy_the_gate() -> None:
    """An eager registrar and a cosmetically inherited owner both fail closed."""
    planted = typer.Typer(name="aeat", cls=CadrumoTyperGroup)

    @planted.callback()
    @command_execution_policy(STATE_FREE)
    def planted_root() -> None:
        return None

    config = typer.Typer(name="config", cls=CadrumoTyperGroup)

    @config.callback()
    @command_execution_policy(STATE_FREE)
    def planted_config() -> None:
        return None

    @config.command("eager")
    @command_execution_policy(STATE_FREE)
    def eager() -> None:
        return None

    planted.add_typer(config, name="config")
    nodes = _config_nodes(planted)
    forged = tuple(
        LiveCommandNode(
            path=node.path,
            kind=node.kind,
            loader_owner=(
                "cadrumo.entrypoints.cli._config._lazy_registration:config_targets.load_other"
                if node.path[-1] == "eager"
                else node.loader_owner
            ),
            handler_owner=node.handler_owner,
            execution_policy=node.execution_policy,
        )
        for node in nodes
    )

    for candidate in (nodes, forged):
        try:
            _require_exact_config_loader_ownership(candidate)
        except AssertionError as error:
            assert "exact lazy target" in str(error)
        else:
            raise AssertionError("planted eager registration escaped the exact-owner gate")


def test_profile_list_resolution_and_help_import_only_owning_config_metadata(tmp_path) -> None:
    profile = profile_cli_path(
        ("config", "profile", "list"),
        invocation_args=("--help",),
        storage_root=tmp_path / "storage",
    )
    allowed_config_modules = {
        "cadrumo.entrypoints.cli._config._execution_policies",
        "cadrumo.entrypoints.cli._config._lazy_registration",
        "cadrumo.entrypoints.cli._config._profile_list_cli",
        "cadrumo.entrypoints.cli._config._root_cli",
    }
    for observation in (profile.resolution, profile.invocation):
        assert observation.exit_code == 0
        assert all(not modules for modules in observation.import_families.values())
        assert not observation.storage_operation_calls
        loaded_config_modules = {
            module
            for module in observation.imported_modules
            if module.startswith("cadrumo.entrypoints.cli._config.")
        }
        assert loaded_config_modules == allowed_config_modules


def test_every_config_family_keeps_a_resolvable_help_surface() -> None:
    runner = CliRunner()
    representatives = (
        ("auth",),
        ("check",),
        ("collab",),
        ("google",),
        ("login",),
        ("passphrase",),
        ("profile",),
        ("provision",),
        ("repair",),
        ("reset",),
        ("storage",),
    )
    for path in representatives:
        result = runner.invoke(root_app, ["config", *path, "--help"])
        assert result.exit_code == 0, (path, result.output, result.exception)
        assert "Usage:" in result.output


def test_empty_profile_list_dispatch_contract_is_preserved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("CADRUMO_DATABASE_URL", f"sqlite:///{tmp_path / 'cadrumo.sqlite3'}")

    result = CliRunner().invoke(root_app, ["--quiet", "config", "profile", "list"])

    assert result.exit_code == 0, (result.output, result.exception)
    assert "active_profile\t<none>" in result.output
    assert "profiles\t<none>" in result.output
