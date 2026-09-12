"""Structural contract for the external-constants retirement boundary."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _ROOT / "dev/registry/analysis/facts_external_constants_retirement.toml"
pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _top_level_constants(source: Path) -> list[str]:
    return _public_module_bindings(ast.parse(source.read_text(encoding="utf-8")))


def _public_module_bindings(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, ast.Assign):
            names.extend(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def test_negative_census_includes_unannotated_module_bindings() -> None:
    tree = ast.parse('STRAY_STATUTORY = "must-not-evade-the-census"')
    assert _public_module_bindings(tree) == ["STRAY_STATUTORY"]


def test_external_constants_retirement_census_matches_live_source() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    constants = _top_level_constants(_ROOT / ledger["source_path"])

    assert ledger["declaration_count"] == ledger["consumer_count"] == 0
    assert "classifications" not in ledger
    assert "declarations" not in ledger
    retired = set(ledger["retired_statutory_symbols"]) | set(ledger["retired_routing_symbols"])
    assert not retired & set(constants)


def test_technical_configuration_boundary_matches_source() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    boundary = ledger["preservation_boundary"]
    source = _ROOT / boundary["technical_configuration_source"]
    tree = ast.parse(source.read_text(encoding="utf-8"))
    constants = _top_level_constants(source)
    types = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    assert constants == boundary["technical_constants"]
    assert types == boundary["technical_types"]
    assert boundary["technical_functions"] == ["load_external_constants"]
    assert (_ROOT / boundary["technical_configuration_data"]).is_file()
