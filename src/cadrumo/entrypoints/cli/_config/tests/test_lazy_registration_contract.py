"""Exact-set and import contracts for the demand-loaded config subtree."""

from __future__ import annotations

import sys

import pytest
import typer
from typer.testing import CliRunner

from cadrumo.tests.cli_performance import profile_cli_path

from ... import app as root_app
from ..._command_policy import command_execution_policy
from ..._command_schema import command_registration_projection
from ..._command_suggestions import (
    CadrumoTyperGroup,
    LazyFactoryTarget,
    LazyNodeTarget,
    LiveCommandNode,
    lazy_subcommand_target,
    walk_live_command_tree,
)
from .._execution_policies import STATE_FREE
from .._lazy_registration import (
    _CONFIG_TARGETS,
    _GROUP_HELP_KEYS,
    _LEAF_HELP_KEYS,
    ConfigCommandTarget,
    _apoderado_source,
    _collab_source,
    _descendiente_source,
    _google_folder_source,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _config_nodes(app: typer.Typer) -> tuple[LiveCommandNode, ...]:
    return tuple(node for node in walk_live_command_tree(app) if node.path[1:2] == ("config",))


def _require_exact_config_loader_ownership(
    nodes: tuple[LiveCommandNode, ...],
    targets: dict[tuple[str, ...], ConfigCommandTarget],
) -> None:
    for node in nodes:
        if node.path == ("aeat", "config"):
            expected = "cadrumo.entrypoints.cli._config:app"
        else:
            relative = node.path[2:]
            target = targets.get(relative)
            assert target is not None, f"config node {' '.join(node.path)!r} has no concrete target"
            assert target.path == relative
            assert target.kind == node.kind
            parent_key = "config" if len(relative) == 1 else "config." + ".".join(relative[:-1])
            registered_target = lazy_subcommand_target(parent_key, relative[-1])
            assert isinstance(registered_target, LazyFactoryTarget)
            assert registered_target.factory is target
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
    assert len({id(target) for target in _CONFIG_TARGETS.values()}) == len(_CONFIG_TARGETS)
    assert all(node.execution_policy is not None for node in nodes)
    _require_exact_config_loader_ownership(nodes, _CONFIG_TARGETS)


def _require_generated_source_oracle(nodes: tuple[LiveCommandNode, ...]) -> None:
    expected = {
        node.path: (node.kind, node.loader_owner, node.handler_owner)
        for node in command_registration_projection().nodes
        if node.path[1:2] == ("config",)
    }
    actual = {
        node.path: (node.kind, node.loader_owner, node.handler_owner)
        for node in nodes
    }
    assert actual == expected


def test_generated_source_oracle_independently_covers_every_live_config_node() -> None:
    """The checked-in source projection detects omission and ownership drift."""
    nodes = _config_nodes(root_app)
    _require_generated_source_oracle(nodes)

    with pytest.raises(AssertionError):
        _require_generated_source_oracle(nodes[1:])

    first = nodes[0]
    forged = LiveCommandNode(
        path=first.path,
        kind=first.kind,
        loader_owner="forged:owner",
        handler_owner=first.handler_owner,
        execution_policy=first.execution_policy,
    )
    with pytest.raises(AssertionError):
        _require_generated_source_oracle((forged, *nodes[1:]))


def test_registrar_backed_sources_materialize_once_without_duplicate_mounts() -> None:
    """Repeated target resolution cannot mutate the legacy registrar sources."""
    sources = (
        _apoderado_source,
        _collab_source,
        _google_folder_source,
        _descendiente_source,
    )
    for source in sources:
        first = source()
        before = (
            tuple(command.name for command in first.registered_commands),
            tuple(group.name for group in first.registered_groups),
        )
        assert source() is first
        after = (
            tuple(command.name for command in first.registered_commands),
            tuple(group.name for group in first.registered_groups),
        )
        assert after == before
        assert len(after[0]) == len(set(after[0]))
        assert len(after[1]) == len(set(after[1]))

    first_walk = _config_nodes(root_app)
    second_walk = _config_nodes(root_app)
    assert first_walk == second_walk


def test_eager_and_forged_concrete_targets_cannot_satisfy_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """An eager registrar and a target bound to another path both fail closed."""
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
    eager_targets: dict[tuple[str, ...], ConfigCommandTarget] = {}
    forged_targets: dict[tuple[str, ...], ConfigCommandTarget] = {
        ("eager",): ConfigCommandTarget(("other",), "leaf"),
    }

    for targets in (eager_targets, forged_targets):
        try:
            _require_exact_config_loader_ownership(nodes, targets)
        except AssertionError as error:
            assert "concrete target" in str(error) or "other" in str(error)
        else:
            raise AssertionError("planted eager registration escaped the exact-owner gate")

    real_lookup = lazy_subcommand_target
    victim = next(node for node in _config_nodes(root_app) if node.path[2:] == ("profile", "list"))

    def impostor() -> typer.Typer:
        return typer.Typer()

    impostor.__module__ = ConfigCommandTarget.__module__
    impostor.__qualname__ = "config_targets.load_profile__list"
    forged_target = LazyFactoryTarget(impostor)

    def forged_lookup(group_key: str, name: str) -> LazyNodeTarget | None:
        if (group_key, name) == ("config.profile", "list"):
            return forged_target
        return real_lookup(group_key, name)

    monkeypatch.setattr(sys.modules[__name__], "lazy_subcommand_target", forged_lookup)
    with pytest.raises(AssertionError):
        _require_exact_config_loader_ownership((victim,), _CONFIG_TARGETS)


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
