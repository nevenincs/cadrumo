"""Strict roundtrip for every optional monetary field on :class:`Invoice`.

``_normalise_invoice_monetary_fields`` used to treat a field PRESENT as
explicit JSON ``null`` differently from a field ABSENT from the payload: an
absent key was skipped (the model default applies), but a present ``null``
raised ``InvoiceValidationError`` ("could not be parsed as a decimal").
``model_dump_json()`` -- the serialiser this repository's own
``Envelope`` wrapping uses -- writes EVERY field, unset ones included, as
explicit JSON ``null`` rather than omitting them. So any invoice saved with
so much as one unset optional monetary field (``retention_rate``,
``retention_amount``, ``recargo_amount``, ``suplido_amount``, ``fx_rate``)
round-tripped through JSON as a present ``null`` and was then REJECTED on
reload -- an ordinary invoice failing to reload, not a currency edge case.
The existing ``test_invoices_secure_storage_roundtrip.py`` fixture never
caught this because it leaves every one of these fields at its pydantic
default, so it never round-trips a NON-None value through the field this
defect actually lived on for the null case, and (before the fix) it
round-tripped a present ``null`` for every one of them without a single
assertion distinguishing "absent" from "present-null" on reload.

See Also:
    :mod:`~adapters.persistence.profile.tests.test_invoices_secure_storage_roundtrip`
        The general invoice-catalogue encrypted-storage roundtrip and its
        identity-tamper anti-tautology proof, whose real-adapter pattern this
        module reuses.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.storage_taxonomy_locations import storage_path
from .....core.storage_taxonomy import StorageCategory
from .....domain.invoices.enums import IvaRate, PaymentStatus
from .....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from .....domain.iva.classification import InvoiceKind
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..invoices import _INVOICE_NAMESPACE, InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_INVOICE_NUMBER = "F-2025-FX-001"


def _invoice_with_every_optional_monetary_field_populated() -> Invoice:
    """A GBP invoice with every optional monetary field set to a non-default value."""
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": _INVOICE_NUMBER,
            "issued_at": date(2025, 4, 2),
            "counterparty_name": "Foreign Supplier Ltd",
            "counterparty_tax_id": "GB123456789",
            "counterparty_country": "GB",
            "base_total": Decimal("500.00"),
            "iva_total": Decimal("105.00"),
            "grand_total": Decimal("622.54"),
            "currency": "GBP",
            "lines": (
                InvoiceLine(
                    description="Servicio extranjero",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    subtotal=Decimal("500.00"),
                    iva_rate=IvaRate.RATE_21,
                    iva_amount=Decimal("105.00"),
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("75.00"),
            "recargo_amount": Decimal("5.20"),
            "suplido_amount": Decimal("12.34"),
            "fx_rate": Decimal("0.8623"),
            "fx_rate_date": date(2025, 4, 2),
            "fx_rate_source": "ecb_reference",
        },
    )


def test_every_optional_monetary_field_survives_the_encrypted_roundtrip(tmp_path: Path) -> None:
    """The fixed shape: a present, non-null value for every optional monetary field round-trips exactly."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        invoice = _invoice_with_every_optional_monetary_field_populated()
        original = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})

        repo = InvoiceCatalogueRepository()
        repo.save(original)
        loaded = repo.load()

        assert loaded == original
        loaded_invoice = loaded.invoices[invoice.invoice_id]
        assert loaded_invoice.retention_rate == Decimal("0.15")
        assert loaded_invoice.retention_amount == Decimal("75.00")
        assert loaded_invoice.recargo_amount == Decimal("5.20")
        assert loaded_invoice.suplido_amount == Decimal("12.34")
        assert loaded_invoice.fx_rate == Decimal("0.8623")
        assert loaded_invoice.fx_rate_date == date(2025, 4, 2)
        assert loaded_invoice.fx_rate_source == "ecb_reference"


def test_an_unset_optional_monetary_field_survives_the_encrypted_roundtrip_as_none(tmp_path: Path) -> None:
    """The defect this fix closes: a field left UNSET reloads as ``None``, not a refusal.

    ``model_dump_json()`` writes every unset optional field as a present
    JSON ``null`` rather than omitting the key -- this is the shape every
    real save produces, not a contrived one. Before the fix, this reload
    raised ``InvoiceValidationError`` naming ``retention_rate`` (reproduced
    against the pre-fix code with real numbers: both invoices in the general
    roundtrip fixture failed reload with exactly that message). Builds
    directly on ``model_validate`` rather than the encrypted-roundtrip
    fixture builder so the only optional monetary field left unset is
    ``fx_rate`` -- an EUR invoice with no fx conversion is the ordinary case,
    not an edge case.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        line = InvoiceLine(
            description="Servicio nacional",
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00"),
            iva_rate=IvaRate.RATE_21,
            iva_amount=Decimal("105.00"),
        )
        invoice = Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "F-2025-EUR-002",
                "issued_at": date(2025, 4, 2),
                "counterparty_name": "Cliente Nacional",
                "counterparty_tax_id": "12345678Z",
                "counterparty_country": "ES",
                "base_total": Decimal("500.00"),
                "iva_total": Decimal("105.00"),
                "grand_total": Decimal("605.00"),
                "currency": "EUR",
                "lines": (line,),
                "payment_status": PaymentStatus.PAID,
            },
        )
        original = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})

        repo = InvoiceCatalogueRepository()
        repo.save(original)
        loaded = repo.load()

        assert loaded == original
        loaded_invoice = loaded.invoices[invoice.invoice_id]
        assert loaded_invoice.fx_rate is None
        assert loaded_invoice.retention_rate is None
        assert loaded_invoice.recargo_amount is None
        assert loaded_invoice.suplido_amount is None


def test_deleting_a_populated_optional_field_from_disk_surfaces_as_refusal(tmp_path: Path) -> None:
    """Anti-tautology proof: a field silently dropped on disk must NOT reload as if nothing changed.

    Saves an invoice with real, non-default ``fx_rate``/``fx_rate_date``/
    ``fx_rate_source``, then reaches into the persisted envelope and deletes
    the ``fx_rate`` key entirely (not nulls it -- an ABSENT key is exactly
    the shape ``_normalise_invoice_monetary_fields`` treats as "no value",
    by design). Reload must not silently re-default ``fx_rate`` to ``None``
    and report success as if the persisted figure survived.

    The model's OWN "fx_rate, fx_rate_date and fx_rate_source must be set
    together" cross-field guard fires first here (``fx_rate_date`` and
    ``fx_rate_source`` are still on disk, so the trio is now incomplete) --
    a SEPARATE, independent catch of the same dropped field, and the
    cause-unique marker this test asserts on. If this test passed with the
    deleted field silently reappearing as ``None`` and a clean reload, BOTH
    of the roundtrip's independent guards against a dropped field would be
    tautological.
    """
    from sqlalchemy import select

    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _invoice_with_every_optional_monetary_field_populated()
        original = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
        repo = InvoiceCatalogueRepository()
        repo.save(original)

        stmt = select(SecureObjectRow).where(SecureObjectRow.namespace == _INVOICE_NAMESPACE)

        def mutate(envelope):
            invoice_dict = envelope["payload"]["invoices"][invoice.invoice_id]
            assert invoice_dict["fx_rate"] == "0.8623", (
                "fixture must serialise a real fx_rate for this proof test to be meaningful"
            )
            del invoice_dict["fx_rate"]

        mutate_encrypted_secure_object_json(profile.repository._engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(ValidationError, match="fx_rate, fx_rate_date and fx_rate_source must be set together"):
            repo.load()


def test_a_genuinely_unparseable_optional_field_still_refuses(tmp_path: Path) -> None:
    """A present NON-null value that fails to parse must still raise -- the fix narrows, not removes, the guard.

    Mutates the persisted ``fx_rate`` to a non-numeric string (simulating a
    mis-mapped import column, the case
    ``_normalise_invoice_monetary_fields``'s error message was written for).
    Distinguished from the two tests above by asserting on the SAME
    cause-unique message the pre-fix code used for this genuinely-bad-data
    case, so a fix that accidentally stopped raising on real garbage (rather
    than only on ``None``) would be caught here.
    """
    from sqlalchemy import select

    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _invoice_with_every_optional_monetary_field_populated()
        original = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
        repo = InvoiceCatalogueRepository()
        repo.save(original)

        stmt = select(SecureObjectRow).where(SecureObjectRow.namespace == _INVOICE_NAMESPACE)

        def mutate(envelope):
            invoice_dict = envelope["payload"]["invoices"][invoice.invoice_id]
            invoice_dict["fx_rate"] = "not-a-number"

        mutate_encrypted_secure_object_json(profile.repository._engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(ValidationError, match="fx_rate could not be parsed as a decimal"):
            repo.load()


def test_a_saved_catalogue_with_optional_fields_never_reaches_plaintext_storage(tmp_path: Path) -> None:
    """Same dormancy guarantee ``test_invoices_secure_storage_roundtrip.py`` proves, for this fixture's shape."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        invoice = _invoice_with_every_optional_monetary_field_populated()
        original = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
        repo = InvoiceCatalogueRepository()
        repo.save(original)

        assert repo.load() == original
        assert not storage_path(StorageCategory.INVOICES).exists()
