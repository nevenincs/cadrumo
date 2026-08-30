"""End-to-end CLI regression for the catalogue-invoice create -> link flow.

The documented ``invoice add`` -> ``link --invoice-id`` chain was once
unreachable: two invoice stores existed, and ``invoice add`` wrote the one
without ``linked_transaction_ids`` while ``link --invoice-id`` resolved the
other. That split is gone -- there is now a single
:class:`~cadrumo.domain.invoices.Invoice` in the
:class:`~cadrumo.domain.invoices.InvoiceCatalogue`, so ``add`` mints a
rich *linkable* invoice: ``aeat app ledger invoice add``.

These tests assert the now-working flow at the CLI boundary:

* ``catalogue create`` -> ``link --invoice-id <rich id>`` succeeds and the link
  is bidirectional (the invoice cites the transaction and the transaction cites
  the invoice), same active bucket; and
* an invoice stamped to a *different* bucket is still refused by the cross-bucket
  link guard (the guard is preserved, not weakened).

Real behaviour only: a real encrypted bucket session, the live Typer tree, and
the real repositories. No mocks, stubs, or monkeypatch.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage import INVOICE_CATALOGUE_NAMESPACE, Envelope, SecureObjectRepository
from ....application.invoices import build_catalogue_invoice
from ....core import IntracomOperationType
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....tests.cli_runner import invoke_cached_cli
from ._cli_text_output_support import _line_value
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["active_profile_isolated_backend"]

# A valid Spanish CIF for the received-invoice counterparty; the rich Invoice
# aggregate validates the tax-id control digit, so an arbitrary token would be
# refused at construction.
_RECEIVED_COUNTERPARTY_CIF = "A58818501"


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
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", "2026-0142",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
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


def test_link_refuses_cross_bucket_catalogue_invoice() -> None:
    """An invoice stamped to a foreign bucket is refused by the link guard.

    The catalogue ``create`` verb stamps the active bucket, but the cross-bucket
    guard in ``link`` must still refuse an invoice whose ``bucket_id`` names a
    different profile. Here a rich invoice carrying a foreign bucket id is
    planted directly, then ``link`` is attempted; the guard must refuse it rather
    than persist a cross-bucket link.

    The row is planted (and read back) through the secure-object substrate's
    own writer, not through :class:`InvoiceCatalogueRepository`:
    ``InvoiceCatalogueRepository`` binds to one bucket's store and refuses a
    catalogue naming a foreign bucket on both save and load (see
    ``test_invoices_bucket_binding.py``), so it cannot be used to construct
    this scenario. The planted row is still genuinely valid at every layer
    beneath that guard, which is what the ``link`` verb's own cross-bucket
    guard -- a different, still-live check -- has to catch.
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
    _write_raw_catalogue(InvoiceCatalogue.from_invoices([foreign_invoice]))

    linked = invoke_cached_cli(
        ["app", "ledger", "link", transaction_id, "--invoice-id", foreign_invoice.invoice_id],
    )
    assert linked.exit_code != 0, linked.output
    # The guard refused before writing: the invoice must not cite the transaction.
    reloaded = _load_raw_catalogue().get(foreign_invoice.invoice_id)
    assert reloaded is not None
    assert reloaded.linked_transaction_ids == (), reloaded.linked_transaction_ids


def _write_raw_catalogue(catalogue: InvoiceCatalogue) -> None:
    """Persist ``catalogue`` straight through the secure-object substrate.

    Bypasses ``InvoiceCatalogueRepository``'s bucket-attribution guard so a
    foreign-bucket row can be planted for a guard-refusal test.
    """
    envelope = Envelope[InvoiceCatalogue](
        schema_version=INVOICE_CATALOGUE_NAMESPACE.schema_version,
        written_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        classification=INVOICE_CATALOGUE_NAMESPACE.sensitivity,
        payload=catalogue,
    )
    SecureObjectRepository().save(
        namespace=INVOICE_CATALOGUE_NAMESPACE.namespace,
        object_key=INVOICE_CATALOGUE_NAMESPACE.require_default_object_key(),
        classification=INVOICE_CATALOGUE_NAMESPACE.sensitivity,
        schema_version=INVOICE_CATALOGUE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def _load_raw_catalogue() -> InvoiceCatalogue:
    """Load the persisted catalogue straight through the secure-object substrate.

    Bypasses ``InvoiceCatalogueRepository``'s bucket-attribution guard so a
    catalogue holding a foreign-bucket row can still be read back to confirm
    it was left unmodified.
    """
    record = SecureObjectRepository().load(
        INVOICE_CATALOGUE_NAMESPACE.namespace,
        INVOICE_CATALOGUE_NAMESPACE.require_default_object_key(),
        expected_class=INVOICE_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=INVOICE_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None, "expected the foreign catalogue row to be present"
    envelope = Envelope[InvoiceCatalogue].model_validate_json(record.payload.decode("utf-8"))
    return envelope.payload


def test_catalogue_create_stamps_intra_community_category() -> None:
    """``--operation-type E`` stamps the iva_category the M349 calculation reads.

    Without it the catalogue invoice defaults to a domestic operation and never
    reaches Modelo 349. The supported goods/triangular codes (E/A/T) map onto an
    intra-community category; this is the CLI counterpart of the resolver test
    that proves the category drives the M349 aggregate.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
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
    """A service clave now stamps a service category, where it once stamped none.

    This test previously asserted ``iva_category is None`` -- pinning the gap
    rather than the behaviour. The enum had no member for an intra-community
    SERVICE, so ``--operation-type S`` produced a record with a clave and no
    IVA treatment at all, which left it ungrounded to every consumer that reads
    the category.

    The category is the service one, not the goods one: a B2B service is NO
    SUJETA in Spain because LIVA art. 69.Uno.1.º locates it where the recipient
    is established, whereas an entrega de bienes is EXEMPT under art. 25.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
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
    assert stored.iva_category is IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY
