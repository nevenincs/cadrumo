"""Exact production reconciliation for the CLI result-schema projection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import scan_directory
from ....core.json_contract import SCHEMA_REGISTRY
from ...schema_surface import RESULT_SCHEMA_MODULES
from .. import _command_schema

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
