"""Tests for the rich catalogue-invoice lifecycle application services.

The reconciliation catalogue gained ``create`` and ``list`` verbs but no way
to inspect or delete a single record. :func:`resolve_catalogue_invoice` (and
its repository-loading sibling) resolve a full id or an unambiguous prefix to
one :class:`~aeat.domain.invoices.Invoice`; :func:`remove_catalogue_invoice`
deletes one record, refusing an invoice that still carries
``linked_transaction_ids`` so the bidirectional link recorded on the
transaction side is never silently orphaned. These tests exercise the services
against the real encrypted :class:`InvoiceCatalogueRepository` (real master-key
provider, real engine) — no mocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices import (
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceNotFoundError,
    InvoiceValidationError,
)
from ....domain.iva import InvoiceKind
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    build_catalogue_invoice,
    create_catalogue_invoice,
    remove_catalogue_invoice,
    resolve_catalogue_invoice,
    resolve_catalogue_invoice_from_repository,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_COUNTERPARTY_CIF = "A58818501"


def _build(invoice_number: str, *, linked: tuple[str, ...] = ()) -> object:
    invoice = build_catalogue_invoice(
        bucket_id="operator",
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id=_COUNTERPARTY_CIF,
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    if linked:
        invoice = invoice.model_copy(update={"linked_transaction_ids": linked})
    return invoice


def test_resolve_catalogue_invoice_by_full_id_and_unambiguous_prefix() -> None:
    """An exact id wins, and a prefix matching exactly one invoice resolves."""
    invoice = _build("2026-0142")
    catalogue = InvoiceCatalogue.from_invoices([invoice])

    assert resolve_catalogue_invoice(catalogue, invoice.invoice_id) == invoice
    # A short prefix of a single-record catalogue is unambiguous.
    assert resolve_catalogue_invoice(catalogue, invoice.invoice_id[:8]) == invoice


def test_resolve_catalogue_invoice_blank_id_refused() -> None:
    """A blank id is refused with the typed required-id error, not a miss."""
    catalogue = InvoiceCatalogue.from_invoices([_build("2026-0142")])
    with pytest.raises(InvoiceNotFoundError) as exc:
        resolve_catalogue_invoice(catalogue, "   ")
    assert exc.value.translated_message == "application.invoices.lifecycle.errors.invoice_id_required"


def test_resolve_catalogue_invoice_not_found_names_the_id() -> None:
    """An id matching no invoice raises the localized not-found error with context."""
    catalogue = InvoiceCatalogue.from_invoices([_build("2026-0142")])
    with pytest.raises(InvoiceNotFoundError) as exc:
        resolve_catalogue_invoice(catalogue, "deadbeefdeadbeef")
    assert exc.value.translated_message == "application.invoices.lifecycle.errors.invoice_not_found"
    assert exc.value.context == {"invoice_id": "deadbeefdeadbeef"}


def test_resolve_catalogue_invoice_ambiguous_prefix_names_candidates() -> None:
    """A prefix matching more than one invoice is refused, never resolved to the first.

    Content-addressed ids are independent hashes, so the only prefix guaranteed
    to match more than one is one they happen to share. Generate enough invoices
    that two share a leading hex character (~1/16 per pair), then query that
    shared prefix: the resolver must refuse and name both candidates rather than
    silently pick one.
    """
    shared_char, members = _two_invoices_sharing_a_prefix()
    catalogue = InvoiceCatalogue.from_invoices(members)

    with pytest.raises(InvoiceValidationError) as exc:
        resolve_catalogue_invoice(catalogue, shared_char)
    assert exc.value.translated_message == "application.invoices.lifecycle.errors.ambiguous_invoice_prefix"
    candidates = exc.value.context["candidates"]
    sharing = [invoice for invoice in members if invoice.invoice_id.startswith(shared_char)]
    assert len(sharing) >= 2
    for invoice in sharing:
        assert invoice.invoice_id in candidates


def _two_invoices_sharing_a_prefix() -> tuple[str, list[object]]:
    """Build invoices until at least two ids share a leading hex character."""
    members: list[object] = []
    seen: dict[str, object] = {}
    for index in range(64):
        invoice = _build(f"2026-{index:04d}")
        head = invoice.invoice_id[0]
        members.append(invoice)
        if head in seen:
            return head, members
        seen[head] = invoice
    raise AssertionError("could not generate two invoices sharing a leading hex character")


def test_remove_catalogue_invoice_deletes_unlinked_record(tmp_path) -> None:
    """An unlinked invoice is removed and the updated catalogue persists."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        created = create_catalogue_invoice(
            bucket_id="operator",
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Papeleria Sol SL",
            counterparty_tax_id=_COUNTERPARTY_CIF,
            counterparty_country="ES",
            invoice_number="2026-0142",
            issued_at=date(2026, 3, 10),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("21"),
            currency="EUR",
        )
        invoice_id = created.invoice.invoice_id

        # Resolve through the repository before removal to prove the read path.
        resolved = resolve_catalogue_invoice_from_repository(bucket_id="operator", invoice_id=invoice_id[:8])
        assert resolved.invoice_id == invoice_id

        result = remove_catalogue_invoice(bucket_id="operator", invoice_id=invoice_id[:8])
        assert result.invoice.invoice_id == invoice_id
        assert invoice_id not in result.catalogue

        # The deletion is persisted: a fresh load no longer carries the id.
        reloaded = InvoiceCatalogueRepository(bucket_id="operator").load()
        assert invoice_id not in reloaded


def test_remove_catalogue_invoice_refuses_linked_record(tmp_path) -> None:
    """An invoice still linked to transactions is refused, naming the links.

    Deleting it from the catalogue alone would leave the transaction side
    citing a vanished invoice — a one-sided link the consistency check flags.
    """
    transaction_id = "a" * 64  # transaction ids are 64-char lowercase hex digests
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        linked_invoice = _build("2026-0142", linked=(transaction_id,))
        repository = InvoiceCatalogueRepository(bucket_id="operator")
        repository.save(InvoiceCatalogue.from_invoices([linked_invoice]))

        with pytest.raises(InvoiceValidationError) as exc:
            remove_catalogue_invoice(bucket_id="operator", invoice_id=linked_invoice.invoice_id)
        assert exc.value.translated_message == "application.invoices.lifecycle.errors.remove_linked_invoice"
        assert exc.value.context["invoice_id"] == linked_invoice.invoice_id
        assert transaction_id in exc.value.context["linked_transaction_ids"]

        # The refusal left the record intact — nothing was deleted.
        reloaded = repository.load()
        assert linked_invoice.invoice_id in reloaded
