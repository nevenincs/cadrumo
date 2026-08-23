"""Tests for the Cadrumo CLI command-suggestion group.

The base Typer group only suggests typo-distance near misses. These
tests cover the two operator-facing gaps :class:`CadrumoTyperGroup`
closes: a semantic synonym (``modify`` -> ``edit``) and a cross-path
command (``app status`` -> ``app overview status``).
"""

from __future__ import annotations

from typing import Any, cast

import pytest
import typer
from typer.main import get_command
from typer.testing import CliRunner

from ....tests.cli_runner import invoke_cached_cli
from .. import app
from .._command_policy import CommandExecutionPolicy, command_execution_policy
from .._command_schema import CommandCapabilityClass
from .._command_suggestions import (
    _LAZY_REGISTRY,
    CadrumoTyperGroup,
    LazyFactoryTarget,
    LazySubcommand,
    register_lazy_subcommand,
    walk_live_command_tree,
)
from ._runtime_profile_cli_fixture import _isolated_cli_state

__all__ = ["_isolated_cli_state"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_STATE_FREE_POLICY = CommandExecutionPolicy(
    classification=CommandCapabilityClass(
        capabilities=frozenset({"state-free"}),
        side_effects=frozenset({"none"}),
        performance="metadata",
    ),
    write_route="none",
)

_PROFILE_WRITE_POLICY = CommandExecutionPolicy(
    classification=CommandCapabilityClass(
        capabilities=frozenset({"encrypted-facts"}),
        side_effects=frozenset({"local-state"}),
        performance="local-io",
    ),
    write_route="profile-bound",
)


def test_profile_modify_suggests_edit() -> None:
    """``config profile modify`` suggests the canonical ``edit`` verb.

    The edit distance between ``modify`` and ``edit`` is too large for
    Typer's fuzzy matcher; the synonym table bridges the gap.
    """

    result = invoke_cached_cli(["config", "profile", "modify", "alice"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "modify" in flat
    assert "edit" in flat


def test_app_status_suggests_overview_status() -> None:
    """``app status`` suggests the cross-path ``app overview status``."""

    result = invoke_cached_cli(["app", "status"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "overview status" in flat


def test_unknown_command_with_no_synonym_still_fails_cleanly() -> None:
    """A genuinely unknown command with no synonym still fails without a trace."""

    result = invoke_cached_cli(["config", "profile", "zzzznonsense"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output


def test_live_command_walker_censuses_every_runtime_node_stably() -> None:
    """The census reaches deep lazy leaves and emits stable ownership."""
    first = walk_live_command_tree(app)
    second = walk_live_command_tree(app)

    assert first == second
    assert first == tuple(sorted(first, key=lambda node: node.path))
    assert len({node.path for node in first}) == len(first)
    assert first[0].path == ("aeat",)
    assert first[0].kind == "root"

    by_path = {node.path: node for node in first}
    assert by_path[("aeat", "config")].kind == "group"
    assert by_path[("aeat", "config", "profile", "delete")].kind == "leaf"
    assert by_path[("aeat", "app", "modelo", "work", "calculate")].kind == "leaf"
    assert all(node.handler_owner != "<none>" for node in first if node.kind == "leaf")
    assert any(node.loader_owner is not None for node in first)
    assert all(":" in node.loader_owner for node in first if node.loader_owner is not None)
    assert all(":" in node.handler_owner for node in first if node.handler_owner != "<none>")


def test_live_command_walker_distinguishes_eager_and_lazy_ownership() -> None:
    """An eager mount never borrows its handler's identity as loader ownership."""
    root = typer.Typer(name="command-census-proof", cls=CadrumoTyperGroup)
    eager = typer.Typer(name="eager", cls=CadrumoTyperGroup)

    @eager.command("show")
    def _show() -> None:
        pass

    root.add_typer(eager, name="eager")

    def _load_lazy() -> typer.Typer:
        lazy = typer.Typer(name="lazy", cls=CadrumoTyperGroup)

        @lazy.command("run")
        def _run() -> None:
            pass

        return lazy

    register_lazy_subcommand("command-census-proof", LazySubcommand("lazy", LazyFactoryTarget(_load_lazy)))

    first = walk_live_command_tree(root)
    second = walk_live_command_tree(root)
    by_path = {node.path: node for node in first}

    assert first == second
    assert by_path[("command-census-proof", "eager")].loader_owner is None
    assert by_path[("command-census-proof", "lazy")].loader_owner == (
        f"{__name__}:test_live_command_walker_distinguishes_eager_and_lazy_ownership.<locals>._load_lazy"
    )
    assert by_path[("command-census-proof", "lazy")].handler_owner.endswith(".<locals>._run")


def test_live_command_walker_reads_policy_from_real_eager_and_lazy_callbacks() -> None:
    """Policy survives both Typer decorator orders and lazy materialisation."""
    root = typer.Typer(name="policy-census-proof", cls=CadrumoTyperGroup)
    eager = typer.Typer(name="eager", cls=CadrumoTyperGroup, invoke_without_command=True)

    @command_execution_policy(_STATE_FREE_POLICY)
    @eager.callback()
    def _eager_group() -> None:
        pass

    @eager.command("show")
    @command_execution_policy(_STATE_FREE_POLICY)
    def _show() -> None:
        pass

    root.add_typer(eager, name="eager")

    def _load_lazy() -> typer.Typer:
        lazy = typer.Typer(name="lazy", cls=CadrumoTyperGroup)

        @lazy.callback()
        def _lazy_group() -> None:
            pass

        @command_execution_policy(_PROFILE_WRITE_POLICY)
        @lazy.command("run")
        def _run() -> None:
            pass

        return lazy

    register_lazy_subcommand("policy-census-proof", LazySubcommand("lazy", LazyFactoryTarget(_load_lazy)))

    by_path = {node.path: node for node in walk_live_command_tree(root)}

    assert by_path[("policy-census-proof",)].execution_policy is None
    assert by_path[("policy-census-proof", "eager")].execution_policy == _STATE_FREE_POLICY
    assert by_path[("policy-census-proof", "eager", "show")].execution_policy == _STATE_FREE_POLICY
    assert by_path[("policy-census-proof", "lazy")].execution_policy is None
    assert by_path[("policy-census-proof", "lazy", "run")].execution_policy == _PROFILE_WRITE_POLICY
    assert by_path[("policy-census-proof", "lazy", "run")].handler_owner.endswith(".<locals>._run")


def test_live_command_policy_is_callback_attached_not_path_inferred() -> None:
    """The same operator path reports the callback's changed declaration."""

    def census(policy: CommandExecutionPolicy) -> CommandExecutionPolicy | None:
        probe = typer.Typer(name="policy-anti-tautology", cls=CadrumoTyperGroup)

        @probe.callback()
        def _root() -> None:
            pass

        @probe.command("same-path")
        @command_execution_policy(policy)
        def _handler() -> None:
            pass

        nodes = {node.path: node for node in walk_live_command_tree(probe)}
        return nodes[("policy-anti-tautology", "same-path")].execution_policy

    assert census(_STATE_FREE_POLICY) == _STATE_FREE_POLICY
    assert census(_PROFILE_WRITE_POLICY) == _PROFILE_WRITE_POLICY
    assert _STATE_FREE_POLICY != _PROFILE_WRITE_POLICY


def _metadata_probe(key: str, *, hidden: bool = False) -> tuple[typer.Typer, LazySubcommand, list[str]]:
    loaded: list[str] = []
    root = typer.Typer(name=key, cls=CadrumoTyperGroup)

    @root.callback()
    def _root() -> None:
        pass

    def _load() -> typer.Typer:
        loaded.append("loaded")
        child = typer.Typer(name="deferred", help="Deferred command help.", cls=CadrumoTyperGroup)

        @child.command("run")
        def _run() -> None:
            pass

        return child

    declaration = LazySubcommand(
        "deferred",
        LazyFactoryTarget(_load),
        help="Deferred command help.",
        hidden=hidden,
    )
    register_lazy_subcommand(key, declaration)
    return root, declaration, loaded


def test_help_and_completion_use_lazy_registration_metadata_without_materialising() -> None:
    """Parent discovery preserves text and descriptions without loading a handler."""
    root, declaration, loaded = _metadata_probe("metadata-help-probe")
    command = cast(Any, get_command(root))
    context = typer.Context(command, info_name="metadata-help-probe")
    try:
        rendered = command.get_help(context)
        completions = command.shell_complete(context, "def")
    finally:
        context.close()

    assert loaded == []
    assert declaration.is_materialized is False
    assert "deferred  Deferred command help." in rendered
    assert [(item.value, item.help) for item in completions] == [("deferred", "Deferred command help.")]


def test_hidden_lazy_metadata_stays_out_of_help_and_completion_without_loading() -> None:
    root, declaration, loaded = _metadata_probe("metadata-hidden-probe", hidden=True)
    command = cast(Any, get_command(root))
    context = typer.Context(command, info_name="metadata-hidden-probe")
    try:
        rendered = command.get_help(context)
        completions = command.shell_complete(context, "def")
    finally:
        context.close()

    assert loaded == []
    assert declaration.is_materialized is False
    assert "deferred" not in rendered
    assert completions == []


def test_unknown_resolution_does_not_materialise_candidate_handlers() -> None:
    root, declaration, loaded = _metadata_probe("metadata-suggestion-probe")
    result = CliRunner().invoke(root, ["defered"])

    assert result.exit_code == 2
    assert "No such command 'defered'" in result.output
    assert loaded == []
    assert declaration.is_materialized is False


def test_live_lazy_help_and_visibility_metadata_match_materialised_targets() -> None:
    """Registration metadata cannot silently drift from its handler target."""
    initial = tuple(
        declaration
        for group_key in ("aeat", "app")
        for declaration in tuple(_LAZY_REGISTRY.get(group_key, {}).values())
    )
    assert initial

    for declaration in initial:
        command = declaration.load()
        assert declaration.help == command.help, declaration.loader_owner
        assert declaration.hidden is command.hidden, declaration.loader_owner
        assert declaration.short_help == command.short_help, declaration.loader_owner
        assert declaration.deprecated == command.deprecated, declaration.loader_owner


def test_eager_registration_keeps_dispatch_precedence_over_duplicate_lazy_metadata() -> None:
    """Discovery and dispatch agree when an eager name shadows a lazy row."""
    loaded: list[str] = []
    root = typer.Typer(name="metadata-eager-precedence", cls=CadrumoTyperGroup)

    @root.callback()
    def _root() -> None:
        pass

    @root.command("same", help="Eager help.")
    def _eager() -> None:
        pass

    def _load() -> typer.Typer:
        loaded.append("loaded")
        child = typer.Typer(name="same", help="Lazy help.")
        return child

    register_lazy_subcommand(
        "metadata-eager-precedence",
        LazySubcommand("same", LazyFactoryTarget(_load), help="Lazy help."),
    )
    command = cast(Any, get_command(root))
    context = typer.Context(command, info_name="metadata-eager-precedence")
    try:
        rendered = command.get_help(context)
        completions = command.shell_complete(context, "sa")
        resolved = command.get_command(context, "same")
    finally:
        context.close()

    assert "same  Eager help." in rendered
    assert "Lazy help." not in rendered
    assert [(item.value, item.help) for item in completions] == [("same", "Eager help.")]
    assert resolved is not None
    assert resolved.help == "Eager help."
    assert loaded == []
