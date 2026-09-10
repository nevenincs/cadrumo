"""Structural contract for the external-constants retirement census."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _ROOT / "dev/registry/analysis/facts_external_constants_retirement.toml"
pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _production_python_files() -> tuple[Path, ...]:
    source_root = _ROOT / "src/cadrumo"
    return tuple(
        path for path in source_root.rglob("*.py") if "tests" not in path.parts and path.name != "external_constants.py"
    )


def test_external_constants_retirement_census_matches_live_source() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    declarations = ledger["declarations"]
    classifications = ledger["classifications"]

    assert "classification" not in ledger
    assert len(declarations) == ledger["declaration_count"] == 37
    assert len(classifications) == ledger["declaration_count"]
    assert (
        sum(len(item["consumers"]) + len(item.get("transitive_consumers", ())) for item in declarations)
        == ledger["consumer_count"]
        == 53
    )

    declaration_symbols = [item["symbol"] for item in declarations]
    assert {item["symbol"] for item in classifications} == set(declaration_symbols)
    assert len(declaration_symbols) == len(set(declaration_symbols))

    source = _ROOT / ledger["source_path"]
    tree = ast.parse(source.read_text(encoding="utf-8"))
    top_level_constants = [
        node.target.id for node in tree.body if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]
    statutory_start = top_level_constants.index("M347_THRESHOLD_EUR")
    assert top_level_constants[statutory_start:] == declaration_symbols


def test_retirement_classifications_and_consumers_are_machine_resolvable() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    declarations = {item["symbol"]: item for item in ledger["declarations"]}
    classifications = {item["symbol"]: item for item in ledger["classifications"]}

    for symbol, classification in classifications.items():
        assert classification["kind"] in {
            "governed_fact",
            "extraction_rule",
            "implementation_coverage",
        }
        assert classification["authority"]
        assert classification["dependencies"]
        assert classification["disposition"]
        assert classification["closure"]
        if classification["kind"] == "governed_fact":
            assert classification["destination_id"]
            assert classification["destination_family"] in {"scalar", "mapping"}
        else:
            assert classification["destination_id"] == ""
            assert classification["destination_family"] == ""

        for consumer in (
            *declarations[symbol]["consumers"],
            *declarations[symbol].get("transitive_consumers", ()),
        ):
            path = _ROOT / consumer["path"]
            text = path.read_text(encoding="utf-8")
            assert consumer["symbol"].split(".")[-1] in text


def test_every_direct_production_import_is_in_the_retirement_census() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    declarations = {item["symbol"]: item for item in ledger["declarations"]}
    actual: dict[str, set[str]] = {symbol: set() for symbol in declarations}

    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "external_constants import" not in text:
            continue
        tree = ast.parse(text)
        relative_path = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module is None or not node.module.endswith("external_constants"):
                continue
            for imported in node.names:
                if imported.name in actual:
                    actual[imported.name].add(relative_path)

    expected = {symbol: {consumer["path"] for consumer in item["consumers"]} for symbol, item in declarations.items()}
    assert actual == expected


def test_retained_facades_and_technical_configuration_boundary_match_source() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    boundary = ledger["preservation_boundary"]
    source = _ROOT / boundary["technical_configuration_source"]
    tree = ast.parse(source.read_text(encoding="utf-8"))

    top_level_constants = [
        node.target.id for node in tree.body if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]
    constants = top_level_constants[: top_level_constants.index("M347_THRESHOLD_EUR")]
    types = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    assert constants == boundary["technical_constants"]
    assert types == boundary["technical_types"]
    assert boundary["technical_functions"] == ["load_external_constants"]
    assert (_ROOT / boundary["technical_configuration_data"]).is_file()

    statutory = {item["symbol"] for item in ledger["declarations"]}
    admitted_imports = (
        statutory
        | set(boundary["technical_constants"])
        | set(boundary["technical_types"])
        | {
            "load_external_constants",
        }
    )
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "external_constants import" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("external_constants"):
                assert {item.name for item in node.names} <= admitted_imports

    for facade in boundary["domain_facades"]:
        facade_tree = ast.parse((_ROOT / facade["path"]).read_text(encoding="utf-8"))
        definitions = {
            node.name
            for node in facade_tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert set(facade["symbols"]) <= definitions
        assert facade["rationale"]
        assert facade["condition"]
