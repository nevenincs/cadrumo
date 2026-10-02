"""Shared real-CLI harness for the LLM-assisted ledger review suites."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_envelope import unwrap_cli_result
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Ledger Review",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


@pytest.fixture
def ledger_llm_profile(tmp_path: Path, authority_operation: object) -> Iterator[NativeCliProfileFixture]:
    """Register one encrypted profile and own its real native runtime for this case."""
    del authority_operation
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-llm-review", facts=_PROFILE_FACTS)
        yield profile


def _import_one_transaction(
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
        f"2026-04-01,{payee},{reference},{amount},EUR,{marker}\n"
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
