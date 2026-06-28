"""Invoice catalogue source-mesh resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage import StorageValidationError
from ....application.ledger import BusinessOperationInvoiceDirection
from ....core import Period
from ....core.resources import resources
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ....domain.iva import InvoiceKind, IvaCategory
from ....domain.modelos import Modelo349CountryPrefixContextError
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, isolated_two_bucket_runtime
from ...aggregation import CalculationSourceContext
from .. import InvoiceCatalogueSourceResolver, invoice_direction_to_source_kind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestInvoiceDirectionToSourceKind:
    """The single contractual direction→settlement mapping consumed by the
    resolver and the unified operator invoice CLI."""

    def test_issued_maps_to_collectible(self) -> None:
        assert (
            invoice_direction_to_source_kind(InvoiceKind.ISSUED)
            is BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE
        )

    def test_received_maps_to_payable(self) -> None:
        assert (
            invoice_direction_to_source_kind(InvoiceKind.RECEIVED) is BusinessOperationInvoiceDirection.PAYABLE_INVOICE
        )

    def test_mapping_is_total_over_invoice_kind(self) -> None:
        # Anti-tautology: the function must resolve every InvoiceKind member to a
        # distinct source kind, never collapse the two directions onto one.
        resolved = {invoice_direction_to_source_kind(kind) for kind in InvoiceKind}
        assert resolved == {
            BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE,
            BusinessOperationInvoiceDirection.PAYABLE_INVOICE,
        }


_BUCKET_ID = "bucket-invoices"
_OTHER_BUCKET_ID = "bucket-other"


@pytest.fixture
def secure_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def _invoice(
    *,
    bucket_id: str,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str,
    base_total: Decimal,
    iva_category: IvaCategory,
    counterparty_country: str = "DE",
) -> Invoice:
    from ....domain.invoices import derive_invoice_id

    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency="EUR",
        grand_total=base_total,
    )
    return Invoice(
        invoice_id=invoice_id,
        bucket_id=bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name="EU Customer GmbH",
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        base_total=base_total,
        iva_total=Decimal("0"),
        grand_total=base_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Intra-community service",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.RATE_0,
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=iva_category,
        linked_transaction_ids=("1" * 64,),
    )


def test_invoice_catalogue_source_resolver_emits_scalar_values_and_provenance(
    secure_profile: TestRuntimeProfile,
) -> None:
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    declarable = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-001",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    other_bucket = _invoice(
        bucket_id=_OTHER_BUCKET_ID,
        invoice_number="F-2026-002",
        issued_at=date(2026, 1, 16),
        counterparty_tax_id="DE987654321",
        base_total=Decimal("500.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    domestic = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-003",
        issued_at=date(2026, 1, 17),
        counterparty_tax_id="DE111111125",
        base_total=Decimal("250.00"),
        iva_category=IvaCategory.DOMESTIC_ZERO,
    )
    repository.save(InvoiceCatalogue.from_invoices((declarable, other_bucket, domestic)))
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.owned_sources == ("collectible_invoice", "payable_invoice")
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")
    assert resolution.source_transaction_ids == ("1" * 64,)
    assert {item.source_kind for item in resolution.provenance} == {"collectible_invoice"}
    assert {item.source_ref for item in resolution.provenance} == {f"collectible_invoice:{declarable.invoice_id}"}
    assert all(item.fingerprint and item.fingerprint.startswith("sha256:") for item in resolution.provenance)


def test_invoice_catalogue_source_resolver_accepts_xi_goods_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    declarable = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-XI-001",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="XI123456789",
        counterparty_country="XI",
        base_total=Decimal("3000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    repository.save(InvoiceCatalogue.from_invoices((declarable,)))
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("3000.00")
    assert {item.source_ref for item in resolution.provenance} == {f"collectible_invoice:{declarable.invoice_id}"}


def test_invoice_catalogue_source_resolver_rejects_gb_ordinary_goods_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    declarable = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-GB-001",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="GB123456789",
        counterparty_country="GB",
        base_total=Decimal("3000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    repository.save(InvoiceCatalogue.from_invoices((declarable,)))
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    with pytest.raises(Modelo349CountryPrefixContextError, match="post-transition"):
        InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=snapshot.revision,
            ),
        )


def test_invoice_catalogue_source_resolver_fails_closed_when_context_bucket_is_not_active(
    tmp_path: Path,
) -> None:
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id="invoice-source-primary",
        secondary_bucket_id="invoice-source-secondary",
    ) as runtime:
        snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

        with pytest.raises(StorageValidationError):
            InvoiceCatalogueSourceResolver().resolve(
                CalculationSourceContext(
                    bucket_id=runtime.secondary.bucket_id,
                    modelo="349",
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "1T"),
                    revision=snapshot.revision,
                ),
            )
