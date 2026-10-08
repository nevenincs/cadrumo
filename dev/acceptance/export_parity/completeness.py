"""Gate a seeded export-parity store against the scenario before any lane reads it.

Every check reads the store through the public ``aeat`` CLI (a fresh process per
command, passphrase on stdin) and compares what the product holds with the
scenario oracle for each seeded year: invoices and their totals, the link from
every invoice to its bank transaction, purchase evidence on every received
purchase, RETA quotas, the asset register and its amortization claims, and the
modelo lifecycle the seed receipt says completed. A product refusal the seed
recorded is reported as the reason a check fails, never counted as a pass.

Usage:
    python -m dev.acceptance.export_parity.completeness --cli .venv/bin/aeat \
        --authority-root .authority --run-dir <seeded run dir> [--years 2025]
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .scenario import ASSETS, QUARTERS, YEARS, YearScenario, build_year

REPORT_SCHEMA: Final = "export-parity.completeness/v1"
_PERIODIC: Final = ("303", "130", "111", "115")
_ANNUAL: Final = ("390", "190", "180", "100")
_RETA_CATEGORY: Final = "cuotas_autonomos_ss"


def _public_year_ledger_rows(reader: _StoreReader, prefix: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Public year ledger rows."""
    invoices = [
        row
        for row in reader.rows("app", "ledger", "invoice", "list")
        if str(row.get("issued_at", "")).startswith(prefix)
    ]
    transactions = [row for row in reader.rows("app", "ledger", "list") if str(row.get("date", "")).startswith(prefix)]
    return invoices, transactions


def _linked_invoice_count(invoices: list[dict[str, Any]]) -> int:
    """Count invoices whose public readback exposes a reciprocal transaction link."""
    return sum(1 for row in invoices if row.get("linked_transaction_ids"))


def _ledger_total_checks(
    year: int,
    scenario: YearScenario,
    invoices: list[dict[str, Any]],
    issued: list[dict[str, Any]],
    received: list[dict[str, Any]],
    reta: list[dict[str, Any]],
    evidenced: set[Any],
) -> list[GateCheck]:
    """Ledger total checks."""
    return [
        _check(year, "issued invoices", len(scenario.issued), len(issued)),
        _check(
            year,
            "issued base total",
            sum((item.base for item in scenario.issued), Decimal("0")),
            _total([row.get("base_total") for row in issued]),
        ),
        _check(year, "received invoices", len(scenario.received), len(received)),
        _check(
            year,
            "received base total",
            sum((item.base for item in scenario.received), Decimal("0")),
            _total([row.get("base_total") for row in received]),
        ),
        _check(
            year,
            "invoices linked to a transaction",
            len(invoices),
            _linked_invoice_count(invoices),
        ),
        _check(
            year,
            "received invoices with purchase evidence",
            len(received),
            sum(1 for row in received if row.get("invoice_id") in evidenced),
        ),
        _check(year, "RETA quotas", len(scenario.reta_months), len(reta)),
        _check(
            year,
            "withholding recorded on received invoices",
            sum((item.withholding for item in scenario.received), Decimal("0")),
            _total([row.get("retention_amount") for row in received]),
        ),
    ]


@dataclass(frozen=True, slots=True)
class GateCheck:
    """One comparison between the store and the scenario oracle."""

    year: int
    check: str
    expected: str
    observed: str
    passed: bool
    reason: str = ""


class _StoreReader:
    def __init__(self, cli: InstalledCli) -> None:
        self._cli = cli
        self._cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def result(self, *args: str) -> dict[str, Any]:
        if args not in self._cache:
            document = self._cli.run(args, allow_error=True)
            result = document.get("result")
            if document.get("status") == "error" or not isinstance(result, dict):
                error = document.get("error") or {}
                code = error.get("code") if isinstance(error, dict) else "unknown"
                raise InstalledCliError(f"{' '.join(args[:4])} refused {code}")
            self._cache[args] = result
        return self._cache[args]

    def rows(self, *args: str) -> list[dict[str, Any]]:
        rows = self.result(*args).get("rows")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _total(values: Sequence[object]) -> Decimal:
    return sum((Decimal(str(value)) for value in values if value not in (None, "")), Decimal("0"))


def _check(year: int, name: str, expected: object, observed: object, reason: str = "") -> GateCheck:
    return GateCheck(year, name, str(expected), str(observed), expected == observed, reason)


def _ledger_checks(reader: _StoreReader, year: int) -> list[GateCheck]:
    scenario = build_year(year)
    prefix = f"{year}-"
    invoices, transactions = _public_year_ledger_rows(reader, prefix)
    issued = [row for row in invoices if row.get("kind") == "issued"]
    received = [row for row in invoices if row.get("kind") == "received"]
    reta = [row for row in transactions if row.get("category_id") == _RETA_CATEGORY]
    evidenced = {row.get("invoice_id") for row in transactions if row.get("purchase_invoice_evidence_id")}
    return _ledger_total_checks(year, scenario, invoices, issued, received, reta, evidenced)


def _asset_checks(reader: _StoreReader, year: int, receipt: dict[str, Any]) -> list[GateCheck]:
    identifiers = receipt.get("identifiers", {})
    blocked = receipt.get("blocked", {})
    checks: list[GateCheck] = []
    for asset in ASSETS:
        if asset.in_service.year > year:
            continue
        registered = f"done:register-{asset.asset_id}" in identifiers
        checks.append(_check(year, f"asset {asset.asset_id} registered", True, registered))
        claimed = f"done:claim-{asset.asset_id}-{year}" in identifiers
        reason = next(
            (value for key, value in blocked.items() if key.startswith(f"amortization:{year}.{asset.asset_id}")), ""
        )
        checks.append(_check(year, f"asset {asset.asset_id} amortization claimed", True, claimed, reason))
    return checks


def _modelo_checks(year: int, receipt: dict[str, Any]) -> list[GateCheck]:
    completed = set(receipt.get("completed_stages", ()))
    blocked = receipt.get("blocked", {})
    checks: list[GateCheck] = []
    coordinates = [(modelo, period) for period in QUARTERS for modelo in _PERIODIC] + [
        (modelo, "0A") for modelo in _ANNUAL
    ]
    for modelo, period in coordinates:
        stage = f"modelo:{modelo}:{year}:{period}"
        reason = next((value for key, value in blocked.items() if key.startswith(f"{stage}.")), "")
        checks.append(_check(year, f"modelo {modelo} {period} filed locally", True, stage in completed, reason))
    return checks


def run_gate(cli: InstalledCli, *, run_dir: Path, years: Sequence[int]) -> tuple[GateCheck, ...]:
    """Compare the store in ``run_dir`` with the scenario for ``years``."""
    receipt = json.loads((run_dir / "seed-receipt.json").read_text(encoding="utf-8"))
    reader = _StoreReader(cli)
    checks: list[GateCheck] = []
    for year in years:
        checks.extend(_ledger_checks(reader, year))
        checks.extend(_asset_checks(reader, year, receipt))
        checks.extend(_modelo_checks(year, receipt))
    return tuple(checks)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the gate, write ``completeness.json`` beside the store, and exit 1 on any failed check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--years", type=int, nargs="+", default=list(YEARS))
    args = parser.parse_args(argv)
    run_dir = args.run_dir.resolve()
    passphrase = (run_dir / "passphrase").read_text(encoding="utf-8").strip()
    cli = InstalledCli(
        args.cli.resolve(),
        storage_root=run_dir / "store",
        authority_root=args.authority_root.resolve(),
        passphrase=passphrase,
    )
    checks = run_gate(cli, run_dir=run_dir, years=args.years)
    report = {
        "schema": REPORT_SCHEMA,
        "passed": all(check.passed for check in checks),
        "checks": [asdict(c) for c in checks],
    }
    target = run_dir / "completeness.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.chmod(target, 0o600)
    for check in checks:
        mark = "ok  " if check.passed else "FAIL"
        suffix = f"  <- {check.reason[:140]}" if check.reason and not check.passed else ""
        print(f"{mark} {check.year} {check.check}: expected {check.expected}, observed {check.observed}{suffix}")
    print(f"{sum(c.passed for c in checks)}/{len(checks)} checks passed")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
