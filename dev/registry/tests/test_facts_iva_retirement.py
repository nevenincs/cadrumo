"""Structural contract for the IVA/recargo retirement ledger."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _ROOT / "dev/registry/analysis/facts_iva_retirement.toml"
_PLAN = _ROOT / ".vault/plan/2026-09-09-facts-registry-plan.md"
pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            result.add(node.name)
    return result


def test_every_retirement_lane_names_live_paths_symbols_callers_and_dependencies() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    plan = _PLAN.read_text(encoding="utf-8")
    lanes = ledger["lanes"]

    assert {lane["lane_id"] for lane in lanes} == {
        "iva-rate-table",
        "iva-recargo-rate-table",
        "iva-local-grounding",
        "iva-rate-resource-repository",
    }
    for lane in lanes:
        source = _ROOT / lane["source_path"]
        assert source.is_file()
        symbols = _symbols(source)
        assert set(lane["delete_symbols"]) <= symbols
        if lane["data_path"]:
            assert (_ROOT / lane["data_path"]).is_file()
        for caller in lane["callers"]:
            caller_path, caller_symbol = caller.split(":", maxsplit=1)
            text = (_ROOT / caller_path).read_text(encoding="utf-8")
            assert caller_symbol.split(".")[-1] in text
        for dependency in lane["dependencies"]:
            assert re.search(rf"`{re.escape(dependency)}`", plan)
        assert lane["destination"]
        assert lane["closure"]


def test_loader_lanes_name_the_exact_direct_production_callers() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    by_id = {lane["lane_id"]: lane for lane in ledger["lanes"]}

    assert set(by_id["iva-rate-table"]["callers"]) == {
        "src/cadrumo/domain/iva/lookup.py:lookup_rate",
        "src/cadrumo/domain/iva/lookup.py:rate_table_covers",
        "src/cadrumo/domain/iva/lookup.py:coexisting_tier_rates",
        "src/cadrumo/domain/iva/lookup.py:rate_kinds_for_declared_rate",
        "src/cadrumo/application/ledger/invoice_extraction_authority.py:_overlapping_iva_rate_pcts",
        "src/cadrumo/core/resources/_repos/iva_rate_tables.py:IvaRateTableRepository._load",
    }
    assert set(by_id["iva-recargo-rate-table"]["callers"]) == {
        "src/cadrumo/domain/iva/recargo_equivalencia.py:recargo_rate_for_applied_rate",
        "src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva.py:_recargo_rate_divergence",
    }


def test_public_facades_and_conditional_deletion_boundaries_are_explicit() -> None:
    ledger = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    by_id = {lane["lane_id"]: lane for lane in ledger["lanes"]}

    assert "lookup_rate" in by_id["iva-rate-table"]["retain_symbols"]
    assert "recargo_rate_for_applied_rate" in by_id["iva-recargo-rate-table"]["retain_symbols"]
    assert by_id["iva-local-grounding"]["retain_symbols"] == []
    assert "otherwise retain only a TOML-unaware facade" in by_id["iva-rate-resource-repository"]["destination"]
    assert all(
        "delete old TOML path" in by_id[lane]["data_disposition"]
        for lane in ("iva-rate-table", "iva-recargo-rate-table")
    )
