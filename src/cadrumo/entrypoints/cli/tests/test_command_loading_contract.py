"""Universal live-command execution-policy contract.

The command tree, rather than a maintained verb list, supplies the enrolled
set.  Semantic checks use callback ownership and Click registration evidence
that is independent of the attached policy value; policy metadata is never
used to manufacture its own expected result.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
import typer
from typer._click.core import Context as TyContext
from typer.main import get_command as typer_get_command

from .. import app
from .._app_execution_policies import METADATA, declare_metadata_group
from .._command_policy import CommandExecutionPolicy, command_execution_policy
from .._command_suggestions import (
    CadrumoTyperGroup,
    LazySubcommand,
    LiveCommandNode,
    register_lazy_subcommand,
    walk_live_command_tree,
)
from ._command_policy_semantic_oracle import (
    EXPECTED_CALLBACK_POLICY,
    REPEATED_CALLBACK_OWNERS,
    PolicySignature,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _require_complete_policy(nodes: Iterable[LiveCommandNode]) -> None:
    missing = tuple(" ".join(node.path) for node in nodes if node.execution_policy is None)
    assert missing == ()


def _policy_signature(policy: CommandExecutionPolicy) -> PolicySignature:
    classification = policy.classification
    return (
        tuple(sorted(classification.capabilities)),
        tuple(sorted(classification.side_effects)),
        classification.performance,
        policy.write_route,
        policy.destructive,
        policy.handoff,
        policy.live_write,
    )


def _require_semantic_partition(nodes: Iterable[LiveCommandNode]) -> None:
    """Compare every callback with the independently adjudicated owner oracle."""
    actual: dict[str, PolicySignature] = {}
    for node in nodes:
        policy = node.execution_policy
        if policy is None:
            continue
        signature = _policy_signature(policy)
        key = node.handler_owner
        if key in REPEATED_CALLBACK_OWNERS:
            key = f"{key} @ {' '.join(node.path)}"
        previous = actual.setdefault(key, signature)
        assert previous == signature, f"callback aliases disagree: {key}"
    assert actual == EXPECTED_CALLBACK_POLICY


def test_every_live_root_group_and_leaf_has_one_coherent_policy() -> None:
    nodes = walk_live_command_tree(app)

    assert nodes
    assert len({node.path for node in nodes}) == len(nodes)
    assert nodes[0].kind == "root"
    _require_complete_policy(nodes)

    for node in nodes:
        policy = node.execution_policy
        assert isinstance(policy, CommandExecutionPolicy)
        classification = policy.classification
        expanded = classification.expanded_capabilities

        # Re-state the closure independently of the production implication map.
        if "encrypted-facts" in expanded:
            assert "profile-custody" in expanded
        if "browser" in expanded or "google" in expanded:
            assert "network" in expanded
        if "calculation" in expanded or "filing" in expanded:
            assert "registry" in expanded

        if classification.capabilities == frozenset({"state-free"}):
            assert classification.side_effects == frozenset({"none"})
        if "network" in classification.side_effects:
            assert "network" in expanded
        if "browser" in classification.side_effects:
            assert "browser" in expanded
        if "google" in classification.side_effects:
            assert "google" in expanded
        if policy.write_route != "none" or policy.destructive or policy.handoff:
            assert "local-state" in classification.side_effects
        if policy.write_route != "none":
            assert "profile-custody" in expanded
        if policy.handoff:
            assert "filing" in expanded
        if policy.live_write:
            assert "network" in expanded
            assert {"network", "browser"} & classification.side_effects

    _require_semantic_partition(nodes)


def test_callback_and_policy_identity_survive_fresh_lazy_materialisation() -> None:
    probe = typer.Typer(name="lazy-policy-identity-probe", cls=CadrumoTyperGroup)

    @probe.callback()
    @command_execution_policy(METADATA)
    def root_callback() -> None:
        return None

    @command_execution_policy(METADATA)
    def lazy_callback() -> None:
        return None

    def load_lazy() -> typer.Typer:
        child = typer.Typer(name="lazy", cls=CadrumoTyperGroup, invoke_without_command=True)
        child.callback()(lazy_callback)
        return child

    register_lazy_subcommand(
        "lazy-policy-identity-probe",
        LazySubcommand("lazy", load_lazy),
    )
    root = typer_get_command(probe)
    context = TyContext(root, info_name="lazy-policy-identity-probe")
    try:
        materialised = cast(Any, root).get_command(context, "lazy")
    finally:
        context.close()

    assert materialised is not None
    click_callback = materialised.callback
    assert click_callback is not None
    assert getattr(click_callback, "__wrapped__", None) is lazy_callback
    assert getattr(click_callback, "__cadrumo_command_execution_policy__", None) is METADATA
    assert walk_live_command_tree(probe)[1].execution_policy is METADATA
    assert materialised.callback is click_callback


def test_universal_gate_bites_for_an_externally_injected_unclassified_leaf() -> None:
    planted = typer.Typer(name="external-policy-probe", cls=CadrumoTyperGroup)

    @planted.callback()
    @command_execution_policy(METADATA)
    def root() -> None:
        return None

    @planted.command("new-leaf")
    def new_leaf() -> None:
        return None

    with pytest.raises(AssertionError):
        _require_complete_policy(walk_live_command_tree(planted))


def test_semantic_partition_bites_for_a_future_helper_generated_group() -> None:
    future = typer.Typer(name="future-metadata-group", cls=CadrumoTyperGroup)
    declare_metadata_group(future)
    expanded = (*walk_live_command_tree(app), *walk_live_command_tree(future))

    with pytest.raises(AssertionError):
        _require_semantic_partition(expanded)


@pytest.mark.parametrize(
    "path",
    [
        ("aeat", "config", "profile", "delete"),
        ("aeat", "app", "ledger", "add"),
        ("aeat", "config", "profile", "list"),
        ("aeat", "config", "google", "sync", "push"),
        ("aeat", "app", "modelo", "export"),
        ("aeat", "app", "live", "iva-wallet", "pull-evidence"),
    ],
)
def test_semantic_partition_bites_for_real_callback_downgrades(path: tuple[str, ...]) -> None:
    nodes = list(walk_live_command_tree(app))
    index = next(index for index, node in enumerate(nodes) if node.path == path)
    nodes[index] = replace(nodes[index], execution_policy=METADATA)

    with pytest.raises(AssertionError):
        _require_semantic_partition(nodes)


def test_legacy_path_keyed_policy_authorities_are_physically_absent() -> None:
    source_root = Path(__file__).resolve().parents[3]
    retired_module = source_root / "application" / "operator_surface" / ("_risk" + "_table.py")
    assert not retired_module.exists()

    banned = (
        "COMMAND" + "_RISK",
        "CommandRisk" + "Declaration",
        "PROFILE_BOUND_WRITE" + "_VERB_PATHS",
        "profile_bound_write" + "_verb_paths",
    )
    offenders: list[str] = []
    duplicate_path_authorities: list[str] = []
    for source in source_root.rglob("*.py"):
        if source == Path(__file__):
            continue
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(source))
        identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        identifiers.update(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute))
        if any(token in identifiers for token in banned):
            offenders.append(str(source.relative_to(source_root)))
        if "tests" not in source.parts:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values, strict=True):
                    tuple_path = (
                        isinstance(key, ast.Tuple)
                        and key.elts
                        and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in key.elts)
                    )
                    if tuple_path and "policy" in ast.unparse(value).casefold():
                        duplicate_path_authorities.append(str(source.relative_to(source_root)))
    assert offenders == []
    assert duplicate_path_authorities == []
