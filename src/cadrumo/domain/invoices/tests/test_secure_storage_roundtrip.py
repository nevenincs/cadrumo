"""Strict roundtrip across the encrypted InvoiceCatalogue boundary.

:class:`InvoiceCatalogueRepository` persists :class:`InvoiceCatalogue` (a
keyed mapping of typed :class:`Invoice` records) through
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``SensitivityClass.FINANCIAL``.

The sibling adapter-level test
(``adapters/persistence/profile/tests/test_invoices_secure_storage_roundtrip.py``)
already exercises the plain domestic-invoice shape, including a populated
``notes`` and ``linked_transaction_ids``. This test fills the remaining
coverage gap: every optional :class:`Invoice` (and :class:`InvoiceLine`)
field that fixture still leaves at its default (``bucket_id``,
``iva_category``, ``operation_type``, ``oss_ioss_regime``,
``oss_transaction_kind``, ``oss_rate_kind``, ``retention_rate``,
``retention_amount``, ``payment_id``) is populated with a non-default value
here, split across a domestic professional invoice (retention-bearing) and a
cross-border OSS consumer invoice (the union-scheme axis). A save-drops-field
regression on any of these optional fields is invisible unless a roundtrip
fixture actually populates them.
"""

from __future__ import annotations

import json as _json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage import SensitivityClass
from ....core import IntracomOperationType
from ....tests.secure_sql import isolated_runtime_profile
from ...iva import InvoiceKind, IvaCategory, IvaRateKind, OssIossRegime, TransactionKind
from .. import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Mirrors the persistence contract declared in
# ``adapters/persistence/profile/invoices.py`` (namespace, object key, and
# envelope schema version). Duplicated here as plain literals rather than
# imported, since those names are private to their owning adapter module and
# this test lives in a different package.
_INVOICE_NAMESPACE = "cadrumo.domain.invoices"
_INVOICE_OBJECT_KEY = "catalogue"
_INVOICE_CATALOGUE_VERSION = 1

_HEX64_A = "a" * 64
_HEX64_B = "b" * 64
_HEX64_C = "c" * 64


def _domestic_retention_invoice() -> Invoice:
    """Domestic ISSUED invoice populating the retention + identification axis."""

    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-2025-100",
            "issued_at": date(2025, 4, 10),
            "counterparty_name": "Consultora Ibérica SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "bucket_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("210.00"),
            "grand_total": Decimal("1210.00"),
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Servicios de consultoría",
                    quantity=Decimal("10"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("1000.00"),
                    iva_rate=IvaRate.RATE_21,
                    iva_amount=Decimal("210.00"),
                    category_id="consultoria",
                ),
            ),
            "payment_status": PaymentStatus.PARTIALLY_PAID,
            "linked_transaction_ids": (_HEX64_A, _HEX64_B),
            "notes": "Factura con retención IRPF aplicable a profesional.",
            "iva_category": IvaCategory.DOMESTIC_GENERAL_21,
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("150.00"),
            "payment_id": _HEX64_A,
        },
    )


def _oss_union_scheme_invoice() -> Invoice:
    """Cross-border ISSUED invoice populating the OSS union-scheme axis."""

    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-2025-200",
            "issued_at": date(2025, 5, 12),
            "counterparty_name": "Privatkunde DE",
            "counterparty_tax_id": "DE123456789",
            "counterparty_country": "DE",
            "base_total": Decimal("500.00"),
            "iva_total": Decimal("95.00"),
            "grand_total": Decimal("595.00"),
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Servicio digital B2C",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    subtotal=Decimal("500.00"),
                    iva_rate=IvaRate.RATE_21,
                    iva_amount=Decimal("95.00"),
                    category_id="servicio-digital",
                    oss_rate_kind=IvaRateKind.GENERAL,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
            "operation_type": IntracomOperationType.S,
            "oss_ioss_regime": OssIossRegime.UNION_SCHEME,
            "oss_transaction_kind": TransactionKind.OSS_UNION_SERVICES,
            "payment_id": _HEX64_C,
        },
    )


def _populated_catalogue() -> InvoiceCatalogue:
    domestic = _domestic_retention_invoice()
    oss = _oss_union_scheme_invoice()
    return InvoiceCatalogue(invoices={domestic.invoice_id: domestic, oss.invoice_id: oss})


def test_invoice_catalogue_with_retention_and_oss_axes_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """Every optional Invoice field round-trips through encrypted SQL."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"):
        original = _populated_catalogue()
        repo = InvoiceCatalogueRepository()
        repo.save(original)
        loaded = InvoiceCatalogueRepository().load()

    assert loaded == original
    assert len(loaded.invoices) == 2

    domestic = next(v for v in loaded.values() if v.invoice_number == "F-2025-100")
    assert domestic.bucket_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert domestic.iva_category is IvaCategory.DOMESTIC_GENERAL_21
    assert domestic.retention_rate == Decimal("0.15")
    assert domestic.retention_amount == Decimal("150.00")
    assert domestic.payment_id == _HEX64_A
    assert domestic.linked_transaction_ids == (_HEX64_A, _HEX64_B)
    assert domestic.notes == "Factura con retención IRPF aplicable a profesional."
    assert domestic.operation_type is None
    assert domestic.oss_ioss_regime is None
    assert domestic.oss_transaction_kind is None

    oss = next(v for v in loaded.values() if v.invoice_number == "F-2025-200")
    assert oss.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert oss.operation_type is IntracomOperationType.S
    assert oss.oss_ioss_regime is OssIossRegime.UNION_SCHEME
    assert oss.oss_transaction_kind is TransactionKind.OSS_UNION_SERVICES
    assert oss.payment_id == _HEX64_C
    assert oss.counterparty_eu_member_state is not None
    assert len(oss.lines) == 1
    assert oss.lines[0].oss_rate_kind is IvaRateKind.GENERAL


def test_invoice_catalogue_dropped_oss_transaction_kind_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: dropping ``oss_transaction_kind`` on disk must surface.

    :class:`Invoice` enforces that ``oss_ioss_regime`` and
    ``oss_transaction_kind`` are supplied together (the
    ``_validate_oss_ioss_axes`` model validator). Persists an OSS invoice
    carrying both axes, then surgically deletes ``oss_transaction_kind`` from
    the encrypted JSON envelope while leaving ``oss_ioss_regime`` in place.
    A naive load would silently re-default ``oss_transaction_kind`` to
    ``None`` and return a catalogue that compares unequal to the original;
    the model's own cross-field invariant must instead refuse the load
    outright.

    If this test ever passes silently with the field dropped, the OSS/IOSS
    axis invariant is not actually enforced post-persistence and the
    boundary is tautological.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        oss = _oss_union_scheme_invoice()
        catalogue = InvoiceCatalogue(invoices={oss.invoice_id: oss})
        repo = InvoiceCatalogueRepository()
        repo.save(catalogue)

        record = profile.repository.load(
            _INVOICE_NAMESPACE,
            _INVOICE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        invoices = envelope["payload"]["invoices"]
        invoice_dict = invoices[oss.invoice_id]
        assert invoice_dict.get("oss_transaction_kind") == "oss_union_services", (
            "fixture must persist oss_transaction_kind for this proof to be meaningful"
        )
        del invoice_dict["oss_transaction_kind"]
        profile.repository.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError, match="supplied together"):
            InvoiceCatalogueRepository().load()


def _foreign_currency_invoice() -> Invoice:
    """GBP invoice carrying the euro-conversion stamp resolved at ingest."""

    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "GB-2025-300",
            "issued_at": date(2025, 3, 14),
            "counterparty_name": "Acme Ltd",
            "counterparty_tax_id": "GB123456789",
            "counterparty_country": "GB",
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("0.00"),
            "grand_total": Decimal("1000.00"),
            "currency": "GBP",
            "lines": (
                InvoiceLine(
                    description="Cloud services",
                    quantity=Decimal("1"),
                    unit_price=Decimal("1000.00"),
                    subtotal=Decimal("1000.00"),
                    iva_rate=IvaRate.NOT_SUBJECT,
                    iva_amount=Decimal("0.00"),
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            # ECB EXR.D.GBP.EUR.SP00.A 2025-03-14 = 0.84183 (1 EUR = 0.84183 GBP);
            # the stored rate is the inverted GBP->EUR multiplier.
            "fx_rate": Decimal("1") / Decimal("0.84183"),
            "fx_rate_date": date(2025, 3, 14),
        },
    )


def test_foreign_currency_conversion_stamp_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """The fx rate and its date round-trip, and the euro views re-derive from them."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _foreign_currency_invoice()
        repo = InvoiceCatalogueRepository()
        repo.save(InvoiceCatalogue(invoices={original.invoice_id: original}))
        loaded = InvoiceCatalogueRepository().load()

    restored = next(iter(loaded.values()))
    assert restored == original
    assert restored.fx_rate == Decimal("1") / Decimal("0.84183")
    assert restored.fx_rate_date == date(2025, 3, 14)
    # 1000.00 GBP * (1 / 0.84183) = 1187.888... -> 1187.89 EUR
    assert restored.grand_total_eur == Decimal("1187.89")
    assert restored.base_total_eur == Decimal("1187.89")
    # The native totals are untouched: conversion is a derived view, not a rewrite.
    assert restored.grand_total == Decimal("1000.00")


def test_dropped_fx_rate_date_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: deleting ``fx_rate_date`` on disk must refuse the load.

    ``fx_rate`` and ``fx_rate_date`` are an all-or-nothing pair so a stored rate
    is always auditable. Persists a converted GBP invoice, then surgically
    deletes the date from the encrypted envelope while leaving the rate. A naive
    load would re-default the date to ``None`` and return an invoice whose rate
    has no provenance -- and which still converts, so nothing downstream would
    notice. The model's own invariant must refuse the load instead.

    If this ever passes with the field dropped, the conversion stamp's
    coherence is not enforced post-persistence and the boundary is tautological.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _foreign_currency_invoice()
        InvoiceCatalogueRepository().save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))

        record = profile.repository.load(
            _INVOICE_NAMESPACE,
            _INVOICE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        invoice_dict = envelope["payload"]["invoices"][invoice.invoice_id]
        assert invoice_dict.get("fx_rate_date") is not None, (
            "fixture must persist fx_rate_date for this proof to be meaningful"
        )
        del invoice_dict["fx_rate_date"]
        profile.repository.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError, match="set together"):
            InvoiceCatalogueRepository().load()
