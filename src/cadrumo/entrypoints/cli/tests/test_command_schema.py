"""Exact production reconciliation for the CLI result-schema projection."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import cast, get_args

import pytest

from ....core import scan_directory
from ....core.json_contract import SCHEMA_REGISTRY
from ...schema_surface import RESULT_SCHEMA_MODULES
from .. import _command_schema
from .._command_schema import (
    CommandCapability,
    CommandCapabilityClass,
    CommandPerformanceClass,
    CommandSideEffectClass,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _register_schema_owner_modules() -> tuple[str, ...]:
    cadrumo_root = Path(__file__).resolve().parents[3]
    owners: set[str] = set()
    for path in scan_directory(cadrumo_root, pattern="*.py", recursive=True):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not any(
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "register_schema")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "register_schema")
            )
            for node in ast.walk(tree)
        ):
            continue
        parts = path.relative_to(cadrumo_root).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        owners.add(".".join(("cadrumo", *parts)))
    return tuple(sorted(owners))


def test_canonical_schema_module_declaration_has_every_in_tree_schema_owner() -> None:
    assert _register_schema_owner_modules() == RESULT_SCHEMA_MODULES


def test_declared_schema_modules_reconcile_exactly_to_registry_projection() -> None:
    failures = _command_schema._ensure_result_schemas_registered()
    assert failures == ()

    references = _command_schema.command_schema_refs()
    registry_references = {(command, schema.__name__) for command, schema in SCHEMA_REGISTRY.items()}
    assert {(reference.command, reference.schema_name) for reference in references} == registry_references
    assert {schema.__module__ for schema in SCHEMA_REGISTRY.values()} == set(RESULT_SCHEMA_MODULES)


def test_command_capability_taxonomy_is_closed_and_serialisable() -> None:
    expected_capabilities = {
        "state-free",
        "registry",
        "profile-custody",
        "encrypted-facts",
        "network",
        "browser",
        "google",
        "calculation",
        "filing",
        "crypto",
    }

    assert set(get_args(CommandCapability)) == expected_capabilities
    assert set(get_args(CommandSideEffectClass)) == {"none", "local-state", "network", "browser", "google"}
    assert set(get_args(CommandPerformanceClass)) == {
        "metadata",
        "local-io",
        "compute",
        "external-io",
        "interactive",
    }


def test_command_capability_taxonomy_import_stays_metadata_only() -> None:
    module_path = Path(_command_schema.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    eager_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            eager_imports.add(node.module or "")
        elif isinstance(node, ast.Import):
            eager_imports.update(alias.name for alias in node.names)
    forbidden_suffixes = ("pydantic", "application.operator_surface", "core.json_contract", "schema_surface")
    assert not {name for name in eager_imports if name.endswith(forbidden_suffixes)}

    probe = """
import json
import sys
import cadrumo.entrypoints.cli
before = set(sys.modules)
from cadrumo.entrypoints.cli._command_schema import CommandCapabilityClass
loaded = set(sys.modules) - before
print(json.dumps({
    'operator_surface': 'cadrumo.application.operator_surface' in loaded,
}))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and in-tree constant probe
        [sys.executable, "-I", "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "operator_surface": False,
    }


def test_command_capability_class_expands_only_owned_authorities() -> None:
    classification = CommandCapabilityClass(
        capabilities=frozenset({"encrypted-facts", "google", "calculation", "filing"}),
        side_effects=frozenset({"google"}),
        performance="external-io",
    )

    state_free_compute = CommandCapabilityClass(
        capabilities=frozenset({"state-free"}),
        side_effects=frozenset({"none"}),
        performance="compute",
    )
    assert state_free_compute.expanded_capabilities == frozenset({"state-free"})

    assert classification.expanded_capabilities == frozenset(
        {
            "profile-custody",
            "encrypted-facts",
            "network",
            "google",
            "registry",
            "calculation",
            "filing",
        }
    )

    crypto_only = CommandCapabilityClass(
        capabilities=frozenset({"crypto"}),
        side_effects=frozenset({"none"}),
        performance="local-io",
    )
    assert crypto_only.expanded_capabilities == frozenset({"crypto"})


@pytest.mark.parametrize(
    ("capabilities", "side_effects", "performance", "message"),
    [
        (frozenset(), frozenset({"none"}), "metadata", "explicitly declare"),
        (frozenset({"state-free", "registry"}), frozenset({"none"}), "metadata", "cannot be combined"),
        (frozenset({"state-free"}), frozenset({"local-state"}), "compute", "effect-free"),
        (frozenset({"registry"}), frozenset({"network"}), "external-io", "requires the network"),
        (frozenset({"unknown"}), frozenset({"none"}), "metadata", "unknown command capabilities"),
        (frozenset({"registry"}), frozenset({"unknown"}), "metadata", "unknown command side effects"),
        (frozenset({"registry"}), frozenset({"none"}), "unknown", "unknown command performance"),
        (frozenset({"registry"}), frozenset(), "metadata", "explicitly declare"),
        (frozenset({"registry"}), frozenset({"none", "local-state"}), "metadata", "cannot be combined"),
    ],
)
def test_command_capability_class_rejects_contradictory_declarations(
    capabilities: frozenset[str],
    side_effects: frozenset[str],
    performance: str,
    message: str,
) -> None:
    """Anti-tautology: planted invalid metadata must make the contract bite."""
    with pytest.raises(ValueError, match=message):
        CommandCapabilityClass(
            capabilities=cast("frozenset[CommandCapability]", capabilities),
            side_effects=cast("frozenset[CommandSideEffectClass]", side_effects),
            performance=cast("CommandPerformanceClass", performance),
        )
