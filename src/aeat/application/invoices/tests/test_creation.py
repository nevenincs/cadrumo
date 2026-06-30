"""Tests for the rich catalogue-invoice creation application service.

:func:`create_catalogue_invoice` mints a linkable
:class:`~aeat.domain.invoices.Invoice` (the only aggregate carrying
``linked_transaction_ids``) so the documented ``invoice catalogue create`` ->
``link --invoice-id`` flow has an operator entry point. These tests exercise the
service against the real encrypted :class:`InvoiceCatalogueRepository` (real
master-key provider, real engine) — no mocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import IntracomOperationType, Period
from ....core.resources import bundled_path
from ....domain.calculations.registry import load_modelo_path
from ....domain.invoices import (
    InvoiceCatalogueRepository,
    InvoiceValidationError,
    PaymentStatus,
)
from ....domain.iva import InvoiceKind, IvaCategory
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .. import (
    InvoiceCatalogueSourceResolver,
    build_catalogue_invoice,
    create_catalogue_invoice,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "19191919-1919-4191-8191-191919191919"


def _modelo_349_revision():
    return load_modelo_path(bundled_path("registry", "aeat", "modelos", "349")).revisions["2020-y-siguientes"]


def test_build_catalogue_invoice_derives_grounded_totals() -> None:
    """A single-line invoice synthesised from base + rate carries grounded totals.

    The cuota is resolved against the registry IVA rate, not a hand-typed
    percentage; the Invoice arithmetic invariants then enforce that the totals
    equal the line sums. The derived ``invoice_id`` is the hex-64 hash that
    ``link --invoice-id`` resolves.
    """
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0142",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    assert len(invoice.invoice_id) == 64
    assert invoice.base_total == Decimal("100.00")
    # IVA total is grounded against the registry rate for the general slot;
    # assert the structural identity (total == base + iva, iva == line sum)
    # rather than re-deriving the registry percentage.
    assert invoice.grand_total == invoice.base_total + invoice.iva_total
    assert invoice.iva_total == sum((line.iva_amount for line in invoice.lines), start=Decimal("0"))
    assert invoice.iva_total > Decimal("0")
    assert invoice.linked_transaction_ids == ()


def test_build_catalogue_invoice_exempt_carries_zero_cuota() -> None:
    """An invoice with no IVA rate is EXEMPT and carries a zero cuota."""
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente SA",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0500",
        issued_at=date(2026, 4, 1),
        taxable_base=Decimal("200.00"),
        iva_rate=None,
        currency="EUR",
    )
    assert invoice.iva_total == Decimal("0")
    assert invoice.grand_total == invoice.base_total


def test_build_catalogue_invoice_refuses_unsupported_rate() -> None:
    """A percentage outside the closed IVA slot taxonomy is refused, with the
    accepted set named — never a bare value-invalid."""
    with pytest.raises(InvoiceValidationError) as exc:
        build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Papeleria Sol SL",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number="2026-0142",
            issued_at=date(2026, 3, 10),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("13"),
            currency="EUR",
    )
    # The accepted-rate set is carried structurally on the error context (the
    # CLI boundary renders it through the locale), so assert the context names
    # the closed slot taxonomy rather than the bare message.
    assert exc.value.context is not None
    accepted = exc.value.context["accepted"]
    assert isinstance(accepted, str)
    assert "21" in accepted, exc.value.context


def test_create_catalogue_invoice_persists_and_refuses_duplicate(tmp_path) -> None:
    """The service persists the rich invoice and refuses a duplicate identity.

    A round-trip through the real encrypted repository confirms the invoice is
    reloadable by its derived id; a second create of the same logical identity
    is refused so an accidental re-create cannot clobber a linked record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = create_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Papeleria Sol SL",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number="2026-0142",
            issued_at=date(2026, 3, 10),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("21"),
            currency="EUR",
            payment_status=PaymentStatus.PENDING,
        )
        reloaded = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load().get(result.invoice.invoice_id)
        assert reloaded == result.invoice

        with pytest.raises(InvoiceValidationError):
            create_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Papeleria Sol SL",
                counterparty_tax_id="A58818501",
                counterparty_country="ES",
                invoice_number="2026-0142",
                issued_at=date(2026, 3, 10),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
            )


def test_build_catalogue_invoice_carries_intra_community_category() -> None:
    """The optional ``iva_category`` stamps the calculation-feeding classification.

    The M349 recapitulative resolver reads ``iva_category`` to derive a
    transaction's clave; without it the catalogue invoice defaults to a
    domestic operation (``None``) that never reaches M349.
    """
    intra = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Kunde GmbH",
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        invoice_number="EU-001",
        issued_at=date(2026, 2, 10),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0"),
        currency="EUR",
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    assert intra.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY

    domestic = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="FAC-001",
        issued_at=date(2026, 2, 10),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    assert domestic.iva_category is None


def test_create_catalogue_invoice_intra_community_feeds_modelo_349(tmp_path) -> None:
    """End-to-end: a stamped intra-community invoice reaches the M349 aggregate.

    This is the anti-tautology proof that ``iva_category`` is not merely stored
    but is read by the live :class:`InvoiceCatalogueSourceResolver`: an issued
    intra-community supply of 2000 must surface as one operator declaring
    2000 of operations for the period it was issued in.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        create_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Kunde GmbH",
            counterparty_tax_id="DE345678901",
            counterparty_country="DE",
            invoice_number="EU-2026-001",
            issued_at=date(2026, 2, 10),
            taxable_base=Decimal("2000.00"),
            iva_rate=Decimal("0"),
            currency="EUR",
            iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            repository=repository,
        )
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("2000.00")


def test_create_catalogue_invoice_service_keys_feed_modelo_349(tmp_path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        issued = create_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Service SARL",
            counterparty_tax_id="FR12345678901",
            counterparty_country="FR",
            invoice_number="SERV-OUT-2026-001",
            issued_at=date(2026, 2, 10),
            taxable_base=Decimal("4000.00"),
            iva_rate=Decimal("0"),
            currency="EUR",
            operation_type=IntracomOperationType.S,
            repository=repository,
        ).invoice
        received = create_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Servizi SRL",
            counterparty_tax_id="IT12345678901",
            counterparty_country="IT",
            invoice_number="SERV-IN-2026-001",
            issued_at=date(2026, 3, 5),
            taxable_base=Decimal("3000.00"),
            iva_rate=Decimal("0"),
            currency="EUR",
            operation_type=IntracomOperationType.ADQUISICION_SERVICIOS,
            repository=repository,
        ).invoice
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert issued.operation_type is IntracomOperationType.S
    assert received.operation_type is IntracomOperationType.ADQUISICION_SERVICIOS
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("2")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("7000.00")
    assert resolution.binding_values["iva-349-declarante-numero-operadores-adquisicion"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones-adquisicion"] == Decimal("3000.00")
    rows = {(row.codigo_pais, row.clave_operacion): row for row in resolution.detail_rows}
    assert rows[("FR", "S")].nif_comunitario == "FR12345678901"
    assert rows[("FR", "S")].importe == Decimal("4000.00")
    assert rows[("IT", "I")].nif_comunitario == "IT12345678901"
    assert rows[("IT", "I")].importe == Decimal("3000.00")
