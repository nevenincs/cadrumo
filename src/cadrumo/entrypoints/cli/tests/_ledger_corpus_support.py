"""Shared helpers for ledger-corpus CLI journey tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from click.testing import Result

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....tests.cli_runner import invoke_cached_cli
from ....tests.ledger_cli import list_ledger_rows_via_cli

_CORPUS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)
_FIN_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "financial"
_list_rows = list_ledger_rows_via_cli


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


_REVISION_CASILLA: CasillaId = validated_casilla_id("01")


def _oracle_rules() -> list[dict[str, object]]:
    manifest = json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    raw_rules = manifest.get("rules")
    assert isinstance(raw_rules, list)
    rules: list[dict[str, object]] = []
    for raw_rule in raw_rules:
        assert isinstance(raw_rule, dict)
        rules.append({str(key): value for key, value in raw_rule.items()})
    return rules


def _match(description: str, rules: list[dict[str, object]]) -> dict[str, object] | None:
    for rule in rules:
        match_val = rule.get("match")
        if isinstance(match_val, str) and match_val in description:
            return rule
    return None


def _import_corpus() -> int:
    total = 0
    for name in _FILES:
        result = _invoke(["app", "ledger", "import", "--file", str(_CORPUS / name), "--provider", "csv"])
        assert result.exit_code == 0, f"{name}: {result.output}"
        total += 1
    return total


def _import_bbva() -> None:
    """Lighter import (single business account) for row-targeted journeys."""
    result = _invoke(
        ["app", "ledger", "import", "--file", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output


def _list_payload(*args: str) -> dict[str, Any]:
    listed = _invoke(["--format", "json", "app", "ledger", "list", *args])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload)


def _find(rows: list[dict[str, Any]], needle: str) -> dict[str, Any]:
    return next(r for r in rows if needle in r["description"])


def _set_group(tx_id: str, label: str) -> None:
    result = _invoke(["app", "ledger", "update", tx_id, "--group", label])
    assert result.exit_code == 0, result.output


def _active_repo() -> Any:
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return TransactionCatalogueRepository(bucket_id=bucket_id)


def _xlsx_mirror_of_csv(csv_path: Path, out: Path) -> None:
    """Write a faithful XLSX mirror of a ';'-delimited bank CSV.

    Every cell is the verbatim CSV string so the XLSX provider (which shares the
    CSV bank-layout catalogue and Spanish ',' decimal parsing) parses each row
    identically to the CSV provider, yielding identical content-addressed ids.
    """
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for line in csv_path.read_text(encoding="utf-8").splitlines():
        sheet.append(line.split(";"))
    workbook.save(out)
