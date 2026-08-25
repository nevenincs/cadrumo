"""Shared real-CLI harness for the LLM-assisted ledger review suites."""

from __future__ import annotations

from pathlib import Path

from ....tests.cli_envelope import unwrap_cli_result
from ....tests.cli_runner import invoke_cached_cli


def _import_one_transaction(
    tmp_path: Path,
    *,
    payee: str,
    reference: str,
    amount: str,
    marker: str,
) -> str:
    """Import one CSV row through the real CLI and return its transaction id.

    ``payee``, ``reference``, ``amount`` and ``marker`` are the caller's own
    scenario data (a distinct ``marker`` per suite avoids collisions and
    keeps a failure's transaction id traceable to its origin), never
    defaulted here.
    """
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        f"2026-04-01,{payee},{reference},{amount},EUR,{marker}\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8", newline="\n")
    result = invoke_cached_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = unwrap_cli_result(listed)["rows"]
    assert rows, listed.output
    raw_id = rows[0].get("transaction_id")
    assert isinstance(raw_id, str), listed.output
    return raw_id
