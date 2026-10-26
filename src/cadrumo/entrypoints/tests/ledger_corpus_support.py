"""Shared helpers for ledger-corpus CLI journey tests."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from click.testing import Result

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id

if TYPE_CHECKING:
    from cadrumo.domain.transactions.models import TransactionCatalogue

LEDGER_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "financial" / "ledger-corpus"
LEDGER_CORPUS_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)
FINANCIAL_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "financial"


def invoke_corpus_cli(args: Sequence[str], *, invoke_cli: Callable[..., Result]) -> Result:
    return invoke_cli(args)


CORPUS_REVISION_CASILLA_ID: CasillaId = validated_casilla_id("01")


def load_corpus_oracle_rules() -> list[dict[str, object]]:
    manifest = json.loads((LEDGER_CORPUS_ROOT / "ground-truth.manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    raw_rules = manifest.get("rules")
    assert isinstance(raw_rules, list)
    rules: list[dict[str, object]] = []
    for raw_rule in raw_rules:
        assert isinstance(raw_rule, dict)
        rules.append({str(key): value for key, value in raw_rule.items()})
    return rules


def match_corpus_rule(description: str, rules: list[dict[str, object]]) -> dict[str, object] | None:
    for rule in rules:
        match_val = rule.get("match")
        if isinstance(match_val, str) and match_val in description:
            return rule
    return None


def import_ledger_corpus(*, invoke_cli: Callable[..., Result]) -> int:
    total = 0
    for name in LEDGER_CORPUS_FILES:
        result = invoke_corpus_cli(
            ["app", "ledger", "import", "--file", str(LEDGER_CORPUS_ROOT / name), "--provider", "csv"],
            invoke_cli=invoke_cli,
        )
        assert result.exit_code == 0, f"{name}: {result.output}"
        total += 1
    return total


def import_bbva_corpus_account(*, invoke_cli: Callable[..., Result]) -> None:
    """Lighter import (single business account) for row-targeted journeys."""
    result = invoke_corpus_cli(
        ["app", "ledger", "import", "--file", str(LEDGER_CORPUS_ROOT / "bbva-business-eur.csv"), "--provider", "csv"],
        invoke_cli=invoke_cli,
    )
    assert result.exit_code == 0, result.output


def list_corpus_ledger_payload(*args: str, invoke_cli: Callable[..., Result]) -> dict[str, Any]:
    listed = invoke_corpus_cli(["--format", "json", "app", "ledger", "list", *args], invoke_cli=invoke_cli)
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload)


def find_corpus_transaction(rows: list[dict[str, Any]], needle: str) -> dict[str, Any]:
    return next(r for r in rows if needle in r["description"])


def set_corpus_transaction_group(tx_id: str, label: str, *, invoke_cli: Callable[..., Result]) -> None:
    result = invoke_corpus_cli(["app", "ledger", "update", tx_id, "--group", label], invoke_cli=invoke_cli)
    assert result.exit_code == 0, result.output


def load_active_catalogue() -> TransactionCatalogue:
    """Read the active bucket's stored transactions, as a command would.

    Stored rows validate against registry vocabulary, so a test reading them
    back after a CLI call leases the published authority for the read exactly
    as the command boundary does for its own.
    """
    from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with bundled_indexed_authority().operation():
        return TransactionCatalogueRepository(bucket_id=bucket_id).load()


def write_corpus_xlsx_mirror(csv_path: Path, out: Path) -> None:
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
