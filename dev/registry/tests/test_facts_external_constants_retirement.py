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
    declarations = ledger["declarations"]
    constants = _top_level_constants(_ROOT / ledger["source_path"])

    assert len(declarations) == len(ledger["classifications"]) == ledger["declaration_count"] == 2
    assert sum(len(item["consumers"]) for item in declarations) == ledger["consumer_count"] == 2
    assert not set(ledger["retired_statutory_symbols"]) & set(constants)
    symbols = [item["symbol"] for item in declarations]
    assert {item["symbol"] for item in ledger["classifications"]} == set(symbols)
    assert constants[constants.index(ledger["remaining_start_symbol"]) :] == symbols


def test_retirement_classifications_and_consumers_are_machine_resolvable() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    declarations = {item["symbol"]: item for item in ledger["declarations"]}
    for classification in ledger["classifications"]:
        assert classification["kind"] in {"extraction_rule", "implementation_coverage"}
        assert not classification["destination_id"] and not classification["destination_family"]
        assert all(classification[key] for key in ("authority", "dependencies", "disposition", "closure"))
        for consumer in declarations[classification["symbol"]]["consumers"]:
            assert consumer["symbol"].split(".")[-1] in (_ROOT / consumer["path"]).read_text(encoding="utf-8")


def test_every_direct_production_import_is_in_the_retirement_census() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    actual = {item["symbol"]: set() for item in ledger["declarations"]}
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "external_constants import" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("external_constants"):
                for imported in node.names:
                    if imported.name in actual:
                        actual[imported.name].add(path.relative_to(_ROOT).as_posix())
    expected = {item["symbol"]: {consumer["path"] for consumer in item["consumers"]} for item in ledger["declarations"]}
    assert actual == expected


def test_technical_configuration_boundary_matches_source() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    boundary = ledger["preservation_boundary"]
    source = _ROOT / boundary["technical_configuration_source"]
    tree = ast.parse(source.read_text(encoding="utf-8"))
    constants = _top_level_constants(source)
    types = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    assert constants[: constants.index(ledger["remaining_start_symbol"])] == boundary["technical_constants"]
    assert types == boundary["technical_types"]
    assert boundary["technical_functions"] == ["load_external_constants"]
    assert (_ROOT / boundary["technical_configuration_data"]).is_file()
