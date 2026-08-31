from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._isolated_profile_storage_fixtures import live_fx_isolated_backend
from ._ledger_corpus_support import (
    _import_corpus,
    _invoke,
    _list_payload,
    _list_rows,
    _match,
    _oracle_rules,
    _set_group,
)

__all__ = ["live_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_batch_transform_recategorize_relabel_reallocate_at_scale(tmp_path: Path) -> None:
    _import_corpus()
    rows = _list_rows()
    rules = _oracle_rules()

    lines = ["transaction_id,classification,category_id"]
    targeted: dict[str, str] = {}
    for row in rows:
        tx_id = row["transaction_id"]
        assert isinstance(tx_id, str)
        rule = _match(row["description"], rules)
        if rule is None or rule["classification"] != "BUSINESS":
            continue
        cat_raw = rule.get("category_id")
        cat = cat_raw if isinstance(cat_raw, str) else ""
        lines.append(f"{tx_id},BUSINESS,{cat}")
        targeted[tx_id] = cat
    assert len(targeted) >= 100, f"corpus must yield a hundreds-scale batch, got {len(targeted)}"

    recat_csv = tmp_path / "recategorize.csv"
    recat_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = _invoke(["--format", "json", "app", "ledger", "classify", "--file", str(recat_csv)])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)["result"]
    assert payload["applied"] == len(targeted), payload
    by_id = {row["transaction_id"]: row for row in _list_rows()}
    for tx_id in targeted:
        assert by_id[tx_id]["business_classification"] == "BUSINESS"

    slice_ids = list(targeted)[:60]
    for tx_id in slice_ids:
        _set_group(tx_id, "Cierre 2025")
    grouped = _list_payload("--group", "Cierre 2025")
    assert {row["transaction_id"] for row in grouped["rows"]} == set(slice_ids)

    mixed_ids = slice_ids[:20]
    realloc = ["transaction_id,classification,business_pct"]
    realloc += [f"{tx_id},MIXED,0.60" for tx_id in mixed_ids]
    realloc_csv = tmp_path / "reallocate.csv"
    realloc_csv.write_text("\n".join(realloc) + "\n", encoding="utf-8")
    res2 = _invoke(["--format", "json", "app", "ledger", "classify", "--file", str(realloc_csv)])
    assert res2.exit_code == 0, res2.output
    payload2 = json.loads(res2.output)["result"]
    assert payload2["applied"] == len(mixed_ids), payload2
    final = {row["transaction_id"]: row for row in _list_rows()}
    for tx_id in mixed_ids:
        assert final[tx_id]["business_classification"] == "MIXED"
        assert final[tx_id]["group_label"] == "Cierre 2025"
