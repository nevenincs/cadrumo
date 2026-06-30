"""CLI surface tests for the unified ``invoice`` noun-group (--kind issued|received)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(aeat_invoices_dir=tmp_path / "invoices"),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
        )
        yield


def _invoke_invoice(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "ledger", "invoice", *args])


def _full_id_from_add(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("invoice_id\t"):
            return line.split("\t", 1)[1]
    raise AssertionError(f"no invoice_id in output:\n{output}")


def test_invoice_received_add_and_list_round_trip() -> None:
    add_result = _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "21.00",
            "--iva-amount",
            "21.00",
            "--total-amount",
            "121.00",
        ],
    )
    assert add_result.exit_code == 0, add_result.output
    assert "source_kind\tpayable_invoice" in add_result.output

    list_result = _invoke_invoice(["list", "--kind", "received"])
    assert list_result.exit_code == 0, list_result.output
    assert "count\t1" in list_result.output
    assert "INV-001" in list_result.output


def test_invoice_issued_add_reports_collectible() -> None:
    add_result = _invoke_invoice(
        [
            "add",
            "--kind",
            "issued",
            "--counterparty-nif",
            "87654321X",
            "--invoice-number",
            "COL-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    assert add_result.exit_code == 0, add_result.output
    assert "source_kind\tcollectible_invoice" in add_result.output


def test_invoice_view_by_prefix_received() -> None:
    add_result = _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    full_id = _full_id_from_add(add_result.output)
    result = _invoke_invoice(["view", full_id[:4], "--kind", "received"])
    assert result.exit_code == 0, result.output
    assert "invoice_number\tINV-001" in result.output


def test_invoice_update_changes_fields_received() -> None:
    add_result = _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    full_id = _full_id_from_add(add_result.output)
    result = _invoke_invoice(
        ["update", full_id, "--kind", "received", "--counterparty-name", "Acme S.L."],
    )
    assert result.exit_code == 0, result.output
    assert "counterparty_name\tAcme S.L." in result.output


def test_invoice_remove_requires_yes_received() -> None:
    add_result = _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    full_id = _full_id_from_add(add_result.output)
    refused = _invoke_invoice(["remove", full_id, "--kind", "received"])
    assert refused.exit_code != 0
    confirmed = _invoke_invoice(["remove", full_id, "--kind", "received", "--yes"])
    assert confirmed.exit_code == 0, confirmed.output


def test_invoice_kind_is_required_on_add() -> None:
    result = _invoke_invoice(
        [
            "add",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    assert result.exit_code != 0


def test_invoice_kind_rejects_unknown_value() -> None:
    result = _invoke_invoice(
        [
            "add",
            "--kind",
            "owed",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    assert result.exit_code != 0
    # Typer/click renders the accepted Choice set on parse failure.
    assert "issued" in result.output
    assert "received" in result.output


def test_invoice_list_filters_by_kind() -> None:
    _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "PAY-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    _invoke_invoice(
        [
            "add",
            "--kind",
            "issued",
            "--counterparty-nif",
            "87654321X",
            "--invoice-number",
            "COL-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    received_list = _invoke_invoice(["list", "--kind", "received"])
    issued_list = _invoke_invoice(["list", "--kind", "issued"])
    assert "PAY-001" in received_list.output
    assert "COL-001" not in received_list.output
    assert "COL-001" in issued_list.output
    assert "PAY-001" not in issued_list.output


def test_invoice_list_without_kind_returns_both_kinds() -> None:
    # no-silent-under-declaration guard: bare ``invoice list`` must return BOTH
    # kinds so an operator never silently loses half their records.
    _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "PAY-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    _invoke_invoice(
        [
            "add",
            "--kind",
            "issued",
            "--counterparty-nif",
            "87654321X",
            "--invoice-number",
            "COL-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    both = _invoke_invoice(["list"])
    assert both.exit_code == 0, both.output
    assert "count\t2" in both.output
    assert "payable_invoice" in both.output
    assert "collectible_invoice" in both.output
    assert "PAY-001" in both.output
    assert "COL-001" in both.output
