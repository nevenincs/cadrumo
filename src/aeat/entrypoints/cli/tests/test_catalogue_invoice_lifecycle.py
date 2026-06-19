"""CLI regression for the catalogue-invoice ``view`` and ``remove`` verbs.

The reconciliation catalogue gained ``create`` and ``list`` operator verbs but
no single-record read or delete. Without ``view`` an operator cannot confirm
the long content-addressed ``invoice_id`` that ``link --invoice-id`` resolves;
without ``remove`` a mistaken ``create`` is permanent. These tests exercise the
now-working verbs through the live Typer tree against a real encrypted bucket
session — no mocks, stubs, or monkeypatch — and pin the refusals:

* ``view`` resolves a full id and an unambiguous prefix, and refuses an unknown
  id with the localized not-found message;
* ``remove`` requires ``--yes``, deletes an unlinked invoice, and refuses an
  invoice that still carries linked transactions (the bidirectional link must
  never be silently orphaned).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....domain.invoices import InvoiceCatalogueRepository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECEIVED_COUNTERPARTY_CIF = "A58818501"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def _line_value(output: str, key: str) -> str:
    for line in output.splitlines():
        head, sep, tail = line.partition("\t")
        if sep and head.strip() == key:
            return tail.strip()
    raise AssertionError(f"no {key!r} line in CLI output:\n{output}")


def _create_catalogue_invoice(cli_runner: CliRunner, *, invoice_number: str = "2026-0142") -> str:
    result = cli_runner.invoke(
        app,
        [
            "app", "ledger", "invoice", "catalogue", "create",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", invoice_number,
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")
    assert len(invoice_id) == 64, invoice_id
    return invoice_id


def test_catalogue_view_resolves_full_id_and_prefix(cli_runner: CliRunner) -> None:
    """``view`` shows one catalogue invoice by full id and by unambiguous prefix."""
    invoice_id = _create_catalogue_invoice(cli_runner)

    by_full = cli_runner.invoke(app, ["app", "ledger", "invoice", "catalogue", "view", invoice_id])
    assert by_full.exit_code == 0, by_full.output
    assert _line_value(by_full.output, "invoice_id") == invoice_id

    by_prefix = cli_runner.invoke(app, ["app", "ledger", "invoice", "catalogue", "view", invoice_id[:8]])
    assert by_prefix.exit_code == 0, by_prefix.output
    assert _line_value(by_prefix.output, "invoice_id") == invoice_id


def test_catalogue_view_refuses_unknown_id(cli_runner: CliRunner) -> None:
    """An id matching no invoice is refused, naming the id — never a silent miss."""
    _create_catalogue_invoice(cli_runner)
    result = cli_runner.invoke(
        app,
        ["app", "ledger", "invoice", "catalogue", "view", "deadbeefdeadbeef"],
    )
    assert result.exit_code != 0, result.output
    assert "deadbeefdeadbeef" in result.output, result.output


def test_catalogue_remove_requires_confirmation(cli_runner: CliRunner) -> None:
    """``remove`` without ``--yes`` is refused and leaves the record intact."""
    invoice_id = _create_catalogue_invoice(cli_runner)

    result = cli_runner.invoke(app, ["app", "ledger", "invoice", "catalogue", "remove", invoice_id])
    assert result.exit_code != 0, result.output

    # The unconfirmed refusal deleted nothing.
    assert InvoiceCatalogueRepository().load().get(invoice_id) is not None


def test_catalogue_remove_deletes_unlinked_invoice(cli_runner: CliRunner) -> None:
    """``remove --yes`` deletes an unlinked invoice and the deletion persists."""
    invoice_id = _create_catalogue_invoice(cli_runner)

    result = cli_runner.invoke(
        app,
        ["app", "ledger", "invoice", "catalogue", "remove", invoice_id[:8], "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert _line_value(result.output, "invoice_id") == invoice_id

    assert InvoiceCatalogueRepository().load().get(invoice_id) is None


def test_catalogue_remove_refuses_linked_invoice(cli_runner: CliRunner) -> None:
    """``remove`` refuses an invoice still linked to a transaction.

    Deleting it from the catalogue alone would leave the transaction side citing
    a vanished invoice; the verb refuses and the record stays put. The full
    create -> link -> remove chain is exercised through the CLI.
    """
    add = cli_runner.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", f"Supplier {_RECEIVED_COUNTERPARTY_CIF}",
        ],
    )  # fmt: skip
    assert add.exit_code == 0, add.output
    transaction_id = _line_value(add.output, "ID")

    invoice_id = _create_catalogue_invoice(cli_runner)
    linked = cli_runner.invoke(
        app,
        ["app", "ledger", "link", transaction_id, "--invoice-id", invoice_id],
    )
    assert linked.exit_code == 0, linked.output

    removed = cli_runner.invoke(
        app,
        ["app", "ledger", "invoice", "catalogue", "remove", invoice_id, "--yes"],
    )
    assert removed.exit_code != 0, removed.output
    assert transaction_id in removed.output, removed.output

    # The linked invoice was not deleted and still cites the transaction.
    stored = InvoiceCatalogueRepository().load().get(invoice_id)
    assert stored is not None
    assert stored.linked_transaction_ids == (transaction_id,), stored.linked_transaction_ids
