"""End-to-end CLI regression for the catalogue-invoice create -> link flow.

Audit M17 found the documented ``invoice add`` -> ``link --invoice-id`` chain
unreachable: ``invoice add`` writes the slim
:class:`~aeat.application.ledger.BusinessOperationInvoice` (no
``linked_transaction_ids``), while ``link --invoice-id`` resolves the rich
:class:`~aeat.domain.invoices.Invoice` in the
:class:`~aeat.domain.invoices.InvoiceCatalogue`. Per the accepted
``2026-06-10-ledger-invoice-unification`` the two stores stay distinct, so
the gap is closed by giving the operator a verb that mints a rich *linkable*
invoice: ``aeat app ledger invoice catalogue create``.

These tests assert the now-working flow at the CLI boundary:

* ``catalogue create`` -> ``link --invoice-id <rich id>`` succeeds and the link
  is bidirectional (the invoice cites the transaction and the transaction cites
  the invoice), same active bucket; and
* an invoice stamped to a *different* bucket is still refused by the cross-bucket
  link guard (the guard the decision record mandates is preserved, not weakened).

Real behaviour only: a real encrypted bucket session, the live Typer tree, and
the real repositories. No mocks, stubs, or monkeypatch.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.invoices import build_catalogue_invoice
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import IntracomOperationType
from ....domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
from ....domain.iva import InvoiceKind, IvaCategory
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# A valid Spanish CIF for the received-invoice counterparty; the rich Invoice
# aggregate validates the tax-id control digit, so an arbitrary token would be
# refused at construction.
_RECEIVED_COUNTERPARTY_CIF = "A58818501"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111"),
        )
        yield


def _line_value(output: str, key: str) -> str:
    for line in output.splitlines():
        head, sep, tail = line.partition("\t")
        if sep and head.strip() == key:
            return tail.strip()
    raise AssertionError(f"no {key!r} line in CLI output:\n{output}")


def _add_outgoing_transaction() -> str:
    result = invoke_cached_cli(
        [
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", f"Supplier {_RECEIVED_COUNTERPARTY_CIF}",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _line_value(result.output, "ID")


def _create_catalogue_invoice() -> str:
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "catalogue", "create",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", "2026-0142",
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")
    # The rich invoice id is the content-addressed hex-64 hash that
    # ``link --invoice-id`` resolves, NOT the short slim ``invoice add`` id.
    assert len(invoice_id) == 64, invoice_id
    return invoice_id


def test_catalogue_create_then_link_succeeds_bidirectionally() -> None:
    """The documented create -> link chain works end to end through the CLI.

    Before this verb existed there was no operator path to mint a linkable
    invoice, so ``link --invoice-id`` was dead for operators. The catalogue
    ``create`` verb closes that gap.
    """
    transaction_id = _add_outgoing_transaction()
    invoice_id = _create_catalogue_invoice()

    linked = invoke_cached_cli(
        ["app", "ledger", "link", transaction_id, "--invoice-id", invoice_id],
    )
    assert linked.exit_code == 0, linked.output
    assert _line_value(linked.output, "invoice_id") == invoice_id

    # The link is persisted and bidirectional: the rich invoice now cites the
    # transaction, and the transaction cites the invoice (no one-sided link).
    catalogue = InvoiceCatalogueRepository().load()
    stored = catalogue.get(invoice_id)
    assert stored is not None, "catalogue invoice missing after link"
    assert stored.linked_transaction_ids == (transaction_id,), stored.linked_transaction_ids

    check = invoke_cached_cli(["app", "ledger", "check"])
    assert check.exit_code == 0, check.output
    # ``check`` reports one-sided invoice/transaction links as issues; a clean
    # bidirectional link must not surface a link inconsistency for this id.
    assert "invoice-only" not in check.output, check.output
    assert "transaction-only" not in check.output, check.output


def test_catalogue_create_id_differs_from_slim_invoice_add_id() -> None:
    """The rich catalogue id and the slim ``invoice add`` id are distinct shapes.

    The slim ``invoice add`` id is a short uuid hex; the catalogue id is the
    hex-64 content hash ``link`` resolves. This pins the documented sharp edge:
    the two stores are addressed by different identifiers.
    """
    slim = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--invoice-number", "2026-0142",
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
            "--iva-amount", "21.00", "--total-amount", "121.00",
        ],
    )  # fmt: skip
    assert slim.exit_code == 0, slim.output
    slim_id = _line_value(slim.output, "invoice_id")

    rich_id = _create_catalogue_invoice()
    assert slim_id != rich_id
    assert len(slim_id) != 64
    assert len(rich_id) == 64


def test_link_refuses_cross_bucket_catalogue_invoice() -> None:
    """An invoice stamped to a foreign bucket is refused by the link guard.

    The catalogue ``create`` verb stamps the active bucket, but the cross-bucket
    guard in ``link`` must still refuse an invoice whose ``bucket_id`` names a
    different profile. Here a rich invoice carrying a foreign bucket id is
    persisted into the active catalogue directly, then ``link`` is attempted; the
    guard must refuse it rather than persist a cross-bucket link.
    """
    transaction_id = _add_outgoing_transaction()

    foreign_invoice = build_catalogue_invoice(
        bucket_id="some-other-bucket",
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Foreign SL",
        counterparty_tax_id=_RECEIVED_COUNTERPARTY_CIF,
        counterparty_country="ES",
        invoice_number="2026-9999",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    repo = InvoiceCatalogueRepository()
    repo.save(InvoiceCatalogue.from_invoices([foreign_invoice]))

    linked = invoke_cached_cli(
        ["app", "ledger", "link", transaction_id, "--invoice-id", foreign_invoice.invoice_id],
    )
    assert linked.exit_code != 0, linked.output
    # The guard refused before writing: the invoice must not cite the transaction.
    reloaded = InvoiceCatalogueRepository().load().get(foreign_invoice.invoice_id)
    assert reloaded is not None
    assert reloaded.linked_transaction_ids == (), reloaded.linked_transaction_ids


def test_catalogue_create_stamps_intra_community_category() -> None:
    """``--operation-type E`` stamps the iva_category the M349 calculation reads.

    Without it the catalogue invoice defaults to a domestic operation and never
    reaches Modelo 349. The supported goods/triangular codes (E/A/T) map onto an
    intra-community category; this is the CLI counterpart of the resolver test
    that proves the category drives the M349 aggregate.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "catalogue", "create",
            "--kind", "issued",
            "--counterparty-nif", "DE345678901",
            "--counterparty-name", "Kunde GmbH",
            "--invoice-number", "EU-2026-001",
            "--invoice-date", "2026-02-10",
            "--taxable-base", "2000.00", "--iva-rate", "0",
            "--country-code", "DE", "--operation-type", "E",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")

    stored = InvoiceCatalogueRepository().load().get(invoice_id)
    assert stored is not None, "catalogue invoice missing after create"
    assert stored.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert stored.operation_type is IntracomOperationType.E


def test_catalogue_create_stamps_service_operation_type() -> None:
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "catalogue", "create",
            "--kind", "issued",
            "--counterparty-nif", "DE345678901",
            "--counterparty-name", "Kunde GmbH",
            "--invoice-number", "EU-2026-002",
            "--invoice-date", "2026-02-10",
            "--taxable-base", "2000.00", "--iva-rate", "0",
            "--country-code", "DE", "--operation-type", "S",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")

    stored = InvoiceCatalogueRepository().load().get(invoice_id)
    assert stored is not None, "catalogue invoice missing after create"
    assert stored.operation_type is IntracomOperationType.S
    assert stored.iva_category is None
