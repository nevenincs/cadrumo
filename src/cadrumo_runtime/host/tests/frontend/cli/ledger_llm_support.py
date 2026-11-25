"""Shared real-CLI harness for the LLM-assisted ledger review suites."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.cli_envelope import unwrap_cli_result

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts

PROFILE_FACTS = {
    **native_general_iva_facts(),
    "identity.name": "Native",
    "identity.surnames": "Ledger Review",
    "activities.description": "design",
    "censo.activity_start_date": date(filing_year_envelope().floor, 1, 2).isoformat(),
}


@pytest.fixture
def ledger_llm_profile(tmp_path: Path, authority_operation: object) -> Iterator[NativeCliProfileFixture]:
    """Register one encrypted profile and own its real native runtime for this case."""
    del authority_operation
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-llm-review", facts=PROFILE_FACTS)
        yield profile


def import_one_transaction(
    tmp_path: Path,
    *,
    invoke_cli: Callable[[Sequence[str]], Result],
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
        f"{date(filing_year_envelope().horizon, 4, 1).isoformat()},{payee},{reference},{amount},EUR,{marker}\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8", newline="\n")
    result = invoke_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = invoke_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = unwrap_cli_result(listed)["rows"]
    assert rows, listed.output
    raw_id = rows[0].get("transaction_id")
    assert isinstance(raw_id, str), listed.output
    return raw_id
