"""Closure contract for IVA tables not migrated as rate facts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ANALYSIS_PATH = Path("dev/registry/analysis/facts_iva_retirement.toml")
_DISPOSITIONS = {
    "needs_typed_schema_and_fact_migration": "retain_until_lossless_replacement",
    "technical_non_legal_canonical_vocabulary": "retain",
}


def _census_disagreements(ledger_rows: list[dict[str, Any]], bundled_iva: Path) -> list[str]:
    """Name every way the ledger's table census differs from the bundled IVA tables."""
    disagreements: list[str] = []
    declared = {Path(row["data_path"]).name: row for row in ledger_rows}
    live = {path.name for path in bundled_iva.glob("*.toml")}
    disagreements.extend(f"unclassified table {name}" for name in sorted(live - declared.keys()))
    disagreements.extend(f"classified table {name} is absent" for name in sorted(declared.keys() - live))
    for name in sorted(live & declared.keys()):
        row = declared[name]
        payload = parse_toml((bundled_iva / name).read_text(encoding="utf-8"))
        if len(payload) != 1:
            disagreements.append(f"{name} holds {sorted(payload)} rather than one table")
            continue
        (source_rows,) = payload.values()
        if not isinstance(source_rows, list) or len(source_rows) != row["row_count"]:
            disagreements.append(f"{name} row count disagrees with the ledger")
        if _DISPOSITIONS.get(row["classification"]) != row["decision"]:
            disagreements.append(f"{name} carries decision {row['decision']!r} for {row['classification']!r}")
        if not str(row["safe_next_scope"]).strip():
            disagreements.append(f"{name} names no safe next scope")
    return disagreements


def _ledger_rows() -> list[dict[str, Any]]:
    return parse_toml(_ANALYSIS_PATH.read_text(encoding="utf-8"))["remaining_structured_tables"]


def test_every_remaining_iva_table_has_a_safe_disposition() -> None:
    rows = _ledger_rows()

    assert rows, "the ledger classifies no table, so the census below compares nothing"
    assert _census_disagreements(rows, bundled_path("registry", "aeat", "iva")) == []


def test_the_census_rejects_a_ledger_that_misstates_a_table() -> None:
    rows = deepcopy(_ledger_rows())
    rows[0]["row_count"] += 1
    rows.pop()

    disagreements = _census_disagreements(rows, bundled_path("registry", "aeat", "iva"))

    assert any("row count disagrees" in item for item in disagreements)
    assert any(item.startswith("unclassified table") for item in disagreements)
