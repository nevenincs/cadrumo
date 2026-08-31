"""Structural invariants for the Modelo Workspace V1 production surface.

Covers properties that must hold about live production code: every declared
contributor kind is inventoried by the producer contract set, no workspace
module reintroduces a legacy/migrate/upgrade/deprecated identifier, each
canonical assembly/model/producer entry point is defined in exactly one
module, and the two workspace read routes are real importable functions.

Every denominator-shaped proof below (the native-owner surface inventory)
gates on a PROPERTY read from the live registration --
``set(kinds) == set(ModeloWorkspaceContributorKindV1)``, never a literal
count -- so a legitimate new contributor addition changes the set compared
against, never a hardcoded tally someone has to remember to bump.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from types import ModuleType

import pytest

from .. import workspace, workspace_manifest, workspace_models, workspace_producers
from ..workspace_producers import (
    MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1,
    ModeloWorkspaceContributorKindV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORKSPACE_MODULES = (workspace, workspace_models, workspace_producers, workspace_manifest)

_CANONICAL_ENTRY_POINT_NAMES = frozenset(
    {
        "resolve_static_inspection_result",
        "resolve_graded_snapshot_result",
        "ModeloWorkspaceProjectionV1",
        "ModeloWorkspaceRegistryPortV1",
    }
)

_READ_DESTINATIONS = (
    "cadrumo.application.modelo.workspace.resolve_static_inspection_result",
    "cadrumo.application.modelo.workspace.resolve_graded_snapshot_result",
)

_LEGACY_MARKERS = ("legacy", "migrate", "upgrade", "deprecated")


def _assert_no_legacy_identifier(module: ModuleType) -> None:
    """Refuse a legacy/migrate/upgrade/deprecated CODE IDENTIFIER, never prose.

    Walks function/class/argument names and import targets only -- never
    docstrings, comments, or string literals -- so a module's own prose
    describing or ruling out legacy behaviour cannot trip this check the way
    a raw substring scan would.
    """
    source_path = Path(inspect.getfile(module))
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in ast.walk(tree):
        name: str | None = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.arg):
            name = node.arg
        elif isinstance(node, ast.alias):
            name = node.asname or node.name
        if name is None:
            continue
        lowered = name.lower()
        for marker in _LEGACY_MARKERS:
            assert marker not in lowered, f"{module.__name__} declares identifier {name!r} carrying {marker!r}"


def _entry_points_declared_in(module: ModuleType) -> list[str]:
    declaring: list[str] = []
    for path in Path(inspect.getfile(module)).parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name in _CANONICAL_ENTRY_POINT_NAMES
            ):
                declaring.append(f"{node.name}@{path}")
    return declaring


def test_no_legacy_marker_across_the_workspace_module_set() -> None:
    """The V1 contract reads one shape; nothing here upgrades an older one.

    Checks CODE IDENTIFIERS only (names, classes, functions, imports) via
    AST, never raw prose, so a module's own docstring describing or ruling
    out legacy behaviour in other code cannot false-positive this check.
    """
    for module in _WORKSPACE_MODULES:
        _assert_no_legacy_identifier(module)


def test_exactly_one_authority_defines_each_canonical_workspace_entry_point() -> None:
    """A second declaration of a canonical entry point would fork the read/assembly surface."""
    declaring = _entry_points_declared_in(workspace)
    found_names = {entry.split("@", 1)[0] for entry in declaring}
    assert found_names == _CANONICAL_ENTRY_POINT_NAMES
    assert len(declaring) == len(_CANONICAL_ENTRY_POINT_NAMES), declaring


def test_native_owner_surface_inventory_covers_every_declared_contributor_kind() -> None:
    """The inventory proof is real introspection against the live enum, never a hand-picked count."""
    kinds = {contract.contributor_kind for contract in MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts}
    assert kinds == set(ModeloWorkspaceContributorKindV1)


def test_read_destinations_name_real_importable_entry_points() -> None:
    """The two workspace read routes are real functions, not fabricated screens."""
    for qualified_name in _READ_DESTINATIONS:
        module_path, _, function_name = qualified_name.rpartition(".")
        module = importlib.import_module(module_path)
        assert hasattr(module, function_name), qualified_name
