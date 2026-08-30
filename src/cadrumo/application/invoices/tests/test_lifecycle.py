"""Tests for the rich catalogue-invoice lifecycle application services.

The reconciliation catalogue gained ``create`` and ``list`` verbs but no way
to inspect or delete a single record. :func:`resolve_catalogue_invoice` (and
its repository-loading sibling) resolve a full id or an unambiguous prefix to
one :class:`~cadrumo.domain.invoices.Invoice`; :func:`remove_catalogue_invoice`
deletes one record, refusing an invoice that still carries
``linked_transaction_ids`` so the bidirectional link recorded on the
transaction side is never silently orphaned. These tests exercise the services
against the real encrypted :class:`InvoiceCatalogueRepository` (real master-key
provider, real engine) — no mocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.errors import InvoiceNotFoundError, InvoiceValidationError
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva import InvoiceKind
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    CatalogueInvoicePatch,
    build_catalogue_invoice,
    create_catalogue_invoice,
    remove_catalogue_invoice,
    resolve_catalogue_invoice,
    resolve_catalogue_invoice_from_repository,
    update_catalogue_invoice,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "20202020-2020-4202-8202-202020202020"
_COUNTERPARTY_CIF = "A58818501"


def _build(invoice_number: str, *, linked: tuple[str, ...] = ()) -> Invoice:
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
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
    assert exc.value.context is not None
    candidates = exc.value.context["candidates"]
    assert isinstance(candidates, str)
    sharing = [invoice for invoice in members if invoice.invoice_id.startswith(shared_char)]
    assert len(sharing) >= 2
    for invoice in sharing:
        assert invoice.invoice_id in candidates


def _two_invoices_sharing_a_prefix() -> tuple[str, list[Invoice]]:
    """Build invoices until at least two ids share a leading hex character."""
    members: list[Invoice] = []
    seen: dict[str, Invoice] = {}
    for index in range(64):
        invoice = _build(f"2026-{index:04d}")
        head = invoice.invoice_id[0]
        members.append(invoice)
        if head in seen:
            return head, members
        seen[head] = invoice
    raise AssertionError("could not generate two invoices sharing a leading hex character")


def test_remove_catalogue_invoice_deletes_unlinked_record(tmp_path: Path) -> None:
    """An unlinked invoice is removed and the updated catalogue persists."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        created = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Papeleria Sol SL",
                counterparty_tax_id=_COUNTERPARTY_CIF,
                counterparty_country="ES",
                invoice_number="2026-0142",
                issued_at=date(2026, 3, 10),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
            ),
        )
        invoice_id = created.invoice.invoice_id

        # Resolve through the repository before removal to prove the read path.
        resolved = resolve_catalogue_invoice_from_repository(bucket_id=_BUCKET_ID, invoice_id=invoice_id[:8])
        assert resolved.invoice_id == invoice_id

        result = remove_catalogue_invoice(bucket_id=_BUCKET_ID, invoice_id=invoice_id[:8])
        assert result.invoice.invoice_id == invoice_id
        assert invoice_id not in result.catalogue

        # The deletion is persisted: a fresh load no longer carries the id.
        reloaded = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        assert invoice_id not in reloaded


def test_remove_catalogue_invoice_refuses_linked_record(tmp_path: Path) -> None:
    """An invoice still linked to transactions is refused, naming the links.

    Deleting it from the catalogue alone would leave the transaction side
    citing a vanished invoice — a one-sided link the consistency check flags.
    """
    transaction_id = "a" * 64  # transaction ids are 64-char lowercase hex digests
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        linked_invoice = _build("2026-0142", linked=(transaction_id,))
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        repository.save(InvoiceCatalogue.from_invoices([linked_invoice]))

        with pytest.raises(InvoiceValidationError) as exc:
            remove_catalogue_invoice(bucket_id=_BUCKET_ID, invoice_id=linked_invoice.invoice_id)
        assert exc.value.translated_message == "application.invoices.lifecycle.errors.remove_linked_invoice"
        assert exc.value.context is not None
        assert exc.value.context["invoice_id"] == linked_invoice.invoice_id
        linked_transaction_ids = exc.value.context["linked_transaction_ids"]
        assert isinstance(linked_transaction_ids, str)
        assert transaction_id in linked_transaction_ids

        # The refusal left the record intact — nothing was deleted.
        reloaded = repository.load()
        assert linked_invoice.invoice_id in reloaded


def _linked_invoice(bucket_id: str):
    """A persisted invoice already bound to a transaction."""
    from datetime import date as _date

    from ....domain.invoices.models import derive_invoice_id

    kind = InvoiceKind.RECEIVED
    number = "UPD-2026-001"
    issued = _date(2026, 6, 1)
    tax_id = "A58818501"
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued,
            counterparty_tax_id=tax_id,
            currency="EUR",
            grand_total=Decimal("121.00"),
        ),
        bucket_id=bucket_id,
        kind=kind,
        invoice_number=number,
        issued_at=issued,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id=tax_id,
        counterparty_country="ES",
        base_total=Decimal("100.00"),
        iva_total=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Material",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                subtotal=Decimal("100.00"),
                iva_rate=IvaRate.RATE_21,
                iva_amount=Decimal("21.00"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=("e" * 64,),
    )


def test_a_correction_keeps_the_invoice_id_and_its_transaction_links(tmp_path: Path) -> None:
    """The canonical update corrects in place without re-keying the record.

    This is the property the whole verb exists to provide. The canonical
    invoice id is content-addressed, so any operation that changed an identity
    field would mint a different id and strand every transaction already bound
    to the old one. The patch model excludes those fields entirely, so a
    correction cannot re-key the record even by mistake.

    The links are asserted explicitly rather than assumed: they are why this
    aggregate is the reconciliation authority, and an update that dropped them
    would sever a bidirectional binding the operator never asked to break.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        original = _linked_invoice(_BUCKET_ID)
        repo = InvoiceCatalogueRepository(objects=profile.repository)
        repo.save(InvoiceCatalogue.from_invoices((original,)))

        result = update_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            invoice_id=original.invoice_id,
            patch=CatalogueInvoicePatch(
                counterparty_name="Papeleria Sol SLU",
                notes="Razon social corregida.",
            ),
            repository=repo,
        )
        restored = InvoiceCatalogueRepository(objects=profile.repository).load().get(original.invoice_id)

    assert restored is not None
    assert restored.invoice_id == original.invoice_id
    assert restored.counterparty_name == "Papeleria Sol SLU"
    assert restored.notes == "Razon social corregida."
    assert restored.linked_transaction_ids == ("e" * 64,)
    # Untouched fields keep their stored value: a correction never has to
    # restate the whole record.
    assert restored.grand_total == Decimal("121.00")
    # The record-lifecycle stamp records WHEN it was corrected.
    assert restored.updated_at is not None
    assert result.bucket_event_ids != ()


def test_a_correction_that_breaks_an_invariant_refuses(tmp_path: Path) -> None:
    """The corrected record is re-validated in full, not patched blindly.

    A retención cannot exceed the base it is withheld from. Merging a patch
    without re-validating would persist an invoice whose own invariants it
    violates -- and the persistence boundary would then refuse to load it,
    turning a correctable input error into an unreadable record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        original = _linked_invoice(_BUCKET_ID)
        repo = InvoiceCatalogueRepository(objects=profile.repository)
        repo.save(InvoiceCatalogue.from_invoices((original,)))

        with pytest.raises((InvoiceValidationError, ValidationError)):
            update_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                invoice_id=original.invoice_id,
                patch=CatalogueInvoicePatch(retention_amount=Decimal("500.00")),
                repository=repo,
            )


def test_an_empty_correction_refuses(tmp_path: Path) -> None:
    """A patch stating no change is an operator error, not a no-op.

    Accepting it would emit an UPDATED audit event for a record nothing
    changed on, which pollutes the trail the event exists to provide.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        original = _linked_invoice(_BUCKET_ID)
        repo = InvoiceCatalogueRepository(objects=profile.repository)
        repo.save(InvoiceCatalogue.from_invoices((original,)))

        with pytest.raises(InvoiceValidationError) as exc:
            update_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                invoice_id=original.invoice_id,
                patch=CatalogueInvoicePatch(),
                repository=repo,
            )
        assert exc.value.translated_message == "application.invoices.lifecycle.errors.empty_invoice_patch"


def test_the_patch_model_cannot_express_an_identity_change() -> None:
    """Structural, not a runtime refusal: identity fields are absent entirely.

    A runtime check could be bypassed by a future caller building the payload
    another way. Excluding the fields from the patch model means there is no
    code path that can attempt an identity change at all, which is the stronger
    guarantee for the one axis where getting it wrong strands a link.
    """
    identity_fields = {
        "kind",
        "invoice_number",
        "issued_at",
        "counterparty_tax_id",
        "currency",
        "base_total",
        "iva_total",
        "grand_total",
        "recargo_amount",
        "lines",
    }

    assert identity_fields.isdisjoint(set(CatalogueInvoicePatch.model_fields))


def test_no_lifecycle_refusal_carries_an_authored_sentence(tmp_path: Path) -> None:
    """Every refusal this module raises resolves from the catalogue, never from source.

    The sibling tests pin each refusal's key and facts, which stays green even
    if an authored English sentence is passed alongside the key: message
    resolution prefers the key, so the prose hides. It does not stay hidden
    everywhere — ``str(exc)`` prefers the positional message, so an authored
    sentence still reaches tracebacks, logs, and every boundary that renders the
    exception directly, in every locale.

    This drives all five refusals and asserts the absence rather than the
    identity: with no authored message, ``str(exc)`` degrades to the key, and
    the operator-facing text comes from the catalogue. Re-introducing prose at
    any of the five raise sites makes ``str(exc)`` that sentence and fails here.
    """
    from ....core.errors import resolve_error_message

    transaction_id = "b" * 64
    catalogue = InvoiceCatalogue.from_invoices([_build("2026-0142")])
    shared_char, members = _two_invoices_sharing_a_prefix()

    raised: list[InvoiceNotFoundError | InvoiceValidationError] = []
    for query, expected_error in (("   ", InvoiceNotFoundError), ("deadbeefdeadbeef", InvoiceNotFoundError)):
        with pytest.raises(expected_error) as exc:
            resolve_catalogue_invoice(catalogue, query)
        raised.append(exc.value)

    with pytest.raises(InvoiceValidationError) as ambiguous:
        resolve_catalogue_invoice(InvoiceCatalogue.from_invoices(members), shared_char)
    raised.append(ambiguous.value)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        linked_invoice = _build("2026-0143", linked=(transaction_id,))
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        repository.save(InvoiceCatalogue.from_invoices([linked_invoice]))

        with pytest.raises(InvoiceValidationError) as linked:
            remove_catalogue_invoice(bucket_id=_BUCKET_ID, invoice_id=linked_invoice.invoice_id)
        raised.append(linked.value)

        with pytest.raises(InvoiceValidationError) as empty_patch:
            update_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                invoice_id=linked_invoice.invoice_id,
                patch=CatalogueInvoicePatch(),
                repository=repository,
            )
        raised.append(empty_patch.value)

    assert len({error.translated_message for error in raised}) == len(raised)
    for error in raised:
        key = error.translated_message
        assert key is not None
        assert str(error) == key, f"{key} carries an authored sentence: {str(error)!r}"
        rendered = resolve_error_message(error)
        assert rendered and rendered != key, f"{key} does not resolve in the default catalogue"
