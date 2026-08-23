"""Harness gates for graph-derived CLI result-schema authority."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from cadrumo.entrypoints.cli import (
    command_schema_refs,
    command_schema_type,
    command_schema_types,
    is_exposable_command,
)

from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_harness_has_no_core_schema_registry_dependency_or_fallback() -> None:
    mcp_root = Path(__file__).parents[1]
    retired_name = "SCHEMA" + "_REGISTRY"
    violations: list[str] = []
    for path in sorted(mcp_root.rglob("*.py")):
        if path == Path(__file__):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                alias.name == retired_name for alias in node.names
            ):
                violations.append(f"{path}:{node.lineno}: import")
            if isinstance(node, ast.Name) and node.id == retired_name:
                violations.append(f"{path}:{node.lineno}: name")
    assert violations == []


def test_graph_schema_types_are_the_exact_descriptor_authority() -> None:
    refs = command_schema_refs()
    graph_types = command_schema_types()
    assert set(graph_types) == {ref.command for ref in refs}
    descriptors = build_tool_descriptors()
    exposable = cast(Callable[[str], bool], is_exposable_command)
    expected_exposable = {ref.command for ref in refs if exposable(ref.command)}
    assert {descriptor.command_key for descriptor in descriptors} == expected_exposable
    for descriptor in descriptors:
        assert command_schema_type(descriptor.command_key) is graph_types[descriptor.command_key]
