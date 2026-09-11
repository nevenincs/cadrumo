"""Structural contract for the external-constants retirement boundary."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _ROOT / "dev/registry/analysis/facts_external_constants_retirement.toml"
pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _production_python_files() -> tuple[Path, ...]:
    return tuple(
        path
        for source_root in (_ROOT / "src/cadrumo", _ROOT / "src/cadrumo_harness")
        for path in source_root.rglob("*.py")
        if "tests" not in path.parts and path != _ROOT / "src/cadrumo/core/external_constants.py"
    )


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


def test_retired_symbols_have_no_production_import_path() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    retired = set(ledger["retired_statutory_symbols"]) | set(ledger["retired_routing_symbols"])
    actual: dict[str, set[str]] = {}
    for path in _production_python_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("external_constants"):
                for imported in node.names:
                    if imported.name in retired:
                        actual.setdefault(imported.name, set()).add(path.relative_to(_ROOT).as_posix())
    assert actual == {}


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
