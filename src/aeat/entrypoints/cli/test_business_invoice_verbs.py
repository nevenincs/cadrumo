"""CLI surface tests for the payable-invoice + collectible-invoice noun-groups."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._ledger import collectible_invoice_app, payable_invoice_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'invoices-verbs.db').as_posix()}")
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_payable_invoice_add_and_list_round_trip(cli_runner: CliRunner) -> None:
    add_result = cli_runner.invoke(
        payable_invoice_app,
        [
            "add",
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

    list_result = cli_runner.invoke(payable_invoice_app, ["list"])
    assert list_result.exit_code == 0, list_result.output
    assert "count\t1" in list_result.output
    assert "INV-001" in list_result.output


def test_payable_invoice_view_by_prefix(cli_runner: CliRunner) -> None:
    add_result = cli_runner.invoke(
        payable_invoice_app,
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
    full_id = ""
    for line in add_result.output.splitlines():
        if line.startswith("invoice_id\t"):
            full_id = line.split("\t", 1)[1]
            break
    assert full_id
    result = cli_runner.invoke(payable_invoice_app, ["view", full_id[:4]])
    assert result.exit_code == 0, result.output
    assert "invoice_number\tINV-001" in result.output


def test_payable_invoice_update_changes_fields(cli_runner: CliRunner) -> None:
    cli_runner.invoke(
        payable_invoice_app,
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
    list_result = cli_runner.invoke(payable_invoice_app, ["list"])
    full_id = next(
        line.split("\t")[0]
        for line in list_result.output.splitlines()
        if line and not line.startswith(("bucket", "count"))
    )
    result = cli_runner.invoke(
        payable_invoice_app,
        ["update", full_id, "--counterparty-name", "Acme S.L."],
    )
    assert result.exit_code == 0, result.output
    assert "counterparty_name\tAcme S.L." in result.output


def test_payable_invoice_remove_requires_yes(cli_runner: CliRunner) -> None:
    cli_runner.invoke(
        payable_invoice_app,
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
    list_result = cli_runner.invoke(payable_invoice_app, ["list"])
    full_id = next(
        line.split("\t")[0]
        for line in list_result.output.splitlines()
        if line and not line.startswith(("bucket", "count"))
    )
    refused = cli_runner.invoke(payable_invoice_app, ["remove", full_id])
    assert refused.exit_code != 0
    confirmed = cli_runner.invoke(payable_invoice_app, ["remove", full_id, "--yes"])
    assert confirmed.exit_code == 0, confirmed.output


def test_collectible_invoice_keeps_separate_store(cli_runner: CliRunner) -> None:
    cli_runner.invoke(
        payable_invoice_app,
        [
            "add",
            "--counterparty-nif",
            "12345678Z",
            "--invoice-number",
            "PAY-001",
            "--invoice-date",
            "2026-03-15",
        ],
    )
    add_result = cli_runner.invoke(
        collectible_invoice_app,
        [
            "add",
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

    payable_list = cli_runner.invoke(payable_invoice_app, ["list"])
    collectible_list = cli_runner.invoke(collectible_invoice_app, ["list"])
    assert "PAY-001" in payable_list.output
    assert "COL-001" not in payable_list.output
    assert "COL-001" in collectible_list.output
    assert "PAY-001" not in collectible_list.output
