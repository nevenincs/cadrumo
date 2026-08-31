"""A rich invoice catalogue row belongs to the bucket it is stored in.

``InvoiceCatalogueRepository`` resolves a bucket-scoped encrypted store, but
``save`` and ``load`` accepted and returned any ``InvoiceCatalogue``:
``Invoice.bucket_id`` is optional and the catalogue validates only that its
mapping keys match invoice ids. A foreign rich invoice was therefore surfaced as
a local profile's invoice -- the one invoice surface without the bucket check
its purchase-invoice and business-operation siblings carry.

``bucket_id is None`` is UNATTRIBUTED, not foreign: the field is optional and
most invoices carry no bucket. Only a populated, mismatching bucket is refused,
and both directions are checked, since a check on only one leaves the other as
the way in.

Real behaviour throughout: a real isolated bucket runtime and the real encrypted
secure-object backend. The foreign row is planted through the substrate's own
writer at the exact namespace, classification, and schema version the repository
writes at, so it is genuinely valid at every layer beneath the bucket check.
Nothing is mocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....domain.invoices.enums import IvaRate, PaymentStatus
from .....domain.invoices.errors import InvoicePersistenceError
from .....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from .....domain.iva.classification import InvoiceKind
from .....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_A = "60606060-6060-4060-8060-606060606060"
_BUCKET_B = "61616161-6161-4161-8161-616161616161"


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A) as profile:
        yield profile


def _invoice(invoice_number: str, *, bucket_id: str | None) -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "Consultoría",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
        },
    )


def _catalogue(invoice: Invoice) -> InvoiceCatalogue:
    return InvoiceCatalogue(invoices={invoice.invoice_id: invoice})


def test_saving_a_foreign_bucket_invoice_is_refused() -> None:
    """A catalogue naming bucket B cannot be written through bucket A's store.

    DISCRIMINATING: before the fix this wrote B's invoice into A's encrypted
    database, stamping another profile's identity into this one.
    """
    repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_A)

    with pytest.raises(InvoicePersistenceError) as excinfo:
        repo.save(_catalogue(_invoice("INV-FOREIGN", bucket_id=_BUCKET_B)))

    context = excinfo.value.context
    assert context is not None
    assert context["bucket_id"] == _BUCKET_A
    assert context["foreign_bucket_ids"] == _BUCKET_B


def test_the_co_commit_write_path_is_refused_too() -> None:
    """``to_secure_object_write`` is a write, so it carries the same guard.

    Checking only ``save`` would leave the transaction/event co-commit route as
    the remaining way a foreign row enters the store.
    """
    repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_A)

    with pytest.raises(InvoicePersistenceError):
        repo.to_secure_object_write(_catalogue(_invoice("INV-FOREIGN", bucket_id=_BUCKET_B)))


def test_loading_a_foreign_bucket_invoice_is_refused() -> None:
    """A stored catalogue naming bucket B is not surfaced under bucket A.

    The row is planted through the substrate's own writer at the exact
    namespace, classification, and schema version the repository writes at, so
    it is genuinely valid at every layer beneath the bucket check -- which is
    what made it invisible. Written directly rather than through a repository
    bound to B, because binding a second bucket inside one runtime is refused
    by the storage route guard, correctly and for unrelated reasons.

    The read check matters on its own: a row can predate the write guard, or
    arrive through any other writer against the same store.
    """
    from ...storage.envelope._envelope import Envelope
    from ...storage.secure_object_namespaces import INVOICE_CATALOGUE_NAMESPACE
    from ...storage.sql.secure_objects import SecureObjectRepository

    catalogue = _catalogue(_invoice("INV-FOREIGN", bucket_id=_BUCKET_B))
    envelope = Envelope[InvoiceCatalogue](
        schema_version=INVOICE_CATALOGUE_NAMESPACE.schema_version,
        written_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
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

    with pytest.raises(InvoicePersistenceError):
        InvoiceCatalogueRepository(bucket_id=_BUCKET_A).load()


def test_an_unattributed_invoice_still_round_trips() -> None:
    """POSITIVE CONTROL: ``bucket_id is None`` is unattributed, not foreign.

    The field is optional and most invoices carry no bucket at all, so refusing
    absence would break the ordinary catalogue. This is the case that
    distinguishes a correct guard from one that simply rejects rows.
    """
    repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_A)
    catalogue = _catalogue(_invoice("INV-PLAIN", bucket_id=None))
    repo.save(catalogue)

    assert InvoiceCatalogueRepository(bucket_id=_BUCKET_A).load() == catalogue


def test_an_own_bucket_invoice_still_round_trips() -> None:
    """POSITIVE CONTROL: a correctly-attributed invoice is unaffected."""
    repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_A)
    catalogue = _catalogue(_invoice("INV-OWN", bucket_id=_BUCKET_A))
    repo.save(catalogue)

    assert InvoiceCatalogueRepository(bucket_id=_BUCKET_A).load() == catalogue
