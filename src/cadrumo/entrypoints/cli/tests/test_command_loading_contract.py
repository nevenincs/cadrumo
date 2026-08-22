"""Universal live-command execution-policy contract.

The command tree, rather than a maintained verb list, supplies the enrolled
set.  Semantic checks use callback ownership and Click registration evidence
that is independent of the attached policy value; policy metadata is never
used to manufacture its own expected result.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest
import typer

from .. import app
from .._app_execution_policies import METADATA
from .._command_policy import CommandExecutionPolicy, command_execution_policy
from .._command_suggestions import CadrumoTyperGroup, LiveCommandNode, walk_live_command_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OWNER_CAPABILITY_EVIDENCE = {
    "google": "google",
    "registry": "registry",
    "calculation": "calculation",
    "browser": "browser",
    "crypto": "crypto",
}


def _require_complete_policy(nodes: Iterable[LiveCommandNode]) -> None:
    missing = tuple(" ".join(node.path) for node in nodes if node.execution_policy is None)
    assert missing == ()


def _require_owner_semantics(nodes: Iterable[LiveCommandNode]) -> None:
    """Require strong module/callback ownership signals to retain authority.

    This is deliberately a lower-bound oracle: a callback owned by a Google,
    registry, calculation, browser, or crypto surface cannot truthfully omit
    that capability.  It does not infer that callbacks without those names are
    safe, so the complete-policy gate remains independently necessary.
    """
    violations: list[str] = []
    for node in nodes:
        policy = node.execution_policy
        if policy is None:
            continue
        owner = node.handler_owner.casefold()
        expanded = policy.classification.expanded_capabilities
        for signal, capability in _OWNER_CAPABILITY_EVIDENCE.items():
            if signal in owner and capability not in expanded:
                violations.append(f"{' '.join(node.path)}: {signal!r} owner lacks {capability!r}")
    assert violations == []


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

    _require_owner_semantics(nodes)


def test_policy_identity_survives_real_tree_materialisation() -> None:
    first = walk_live_command_tree(app)
    second = walk_live_command_tree(app)

    assert tuple((node.path, node.kind, node.handler_owner) for node in first) == tuple(
        (node.path, node.kind, node.handler_owner) for node in second
    )
    first_by_path = {node.path: node.execution_policy for node in first}
    assert all(first_by_path[node.path] is node.execution_policy for node in second)


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


def test_semantic_downgrade_gate_bites_independently_of_policy_identity() -> None:
    planted = typer.Typer(name="semantic-policy-probe", cls=CadrumoTyperGroup)

    @planted.callback()
    @command_execution_policy(METADATA)
    def root() -> None:
        return None

    @planted.command("pull")
    @command_execution_policy(METADATA)
    def google_pull() -> None:
        return None

    # Ownership is external evidence, not a path lookup or a comparison with a
    # policy preset.  A real Google-owned callback downgraded to METADATA must
    # therefore red even though its policy is internally valid and attached.
    google_pull.__module__ = "external.google_adapter"
    with pytest.raises(AssertionError):
        _require_owner_semantics(walk_live_command_tree(planted))


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
    for source in source_root.rglob("*.py"):
        if source == Path(__file__):
            continue
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(source))
        identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        identifiers.update(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute))
        if any(token in identifiers for token in banned):
            offenders.append(str(source.relative_to(source_root)))
    assert offenders == []
