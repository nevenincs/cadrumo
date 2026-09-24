"""Inward tests for the invoice source-mesh resolver.

The profile-persistence adapter suite owns encrypted catalogue integration.
These tests exercise application projections through the required reader port
with in-memory catalogues, so storage cannot become part of the application
test seam.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingSourceKind, IntracomOperationType
from ....core.period import Period
from ....domain.calculations.registry.temporal import select_revision
from ....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ...aggregation.source_mesh import CalculationSourceContext
from ..source_resolver import (
    InvoiceCatalogueSourceResolver,
    _intracommunity_clave,
    _invoice_sources_for_revision,
)
from ..source_resolver_ports import InvoiceSourcePersistenceError, InvoiceSourceResolverPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "24242424-2424-4242-8242-242424242424"


class _InMemoryCatalogueReader:
    """Minimal inward fake for the application-owned catalogue reader port."""

    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


def _resolver(catalogue: InvoiceCatalogue) -> InvoiceCatalogueSourceResolver:
    return InvoiceCatalogueSourceResolver(
        ports=InvoiceSourceResolverPorts(catalogue_reader=_InMemoryCatalogueReader(catalogue)),
    )


def _invoice(
    *,
    kind: InvoiceKind,
    number: str,
    category: IvaCategory,
    country: str = "DE",
    operation_type: IntracomOperationType | None = None,
) -> Invoice:
    total = Decimal("1000.00")
    issued_at = date(2026, 1, 15)
    invoice_id = derive_invoice_id(
        kind=kind,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_tax_id="DE123456789",
        currency="EUR",
        grand_total=total,
    )
    return Invoice(
        invoice_id=invoice_id,
        bucket_id=_BUCKET_ID,
        kind=kind,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_name="EU Counterparty GmbH",
        counterparty_tax_id="DE123456789",
        counterparty_country=country,
        base_total=total,
        iva_total=Decimal("0"),
        grand_total=total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Intra-community service",
                quantity=Decimal("1"),
                unit_price=total,
                subtotal=total,
                iva_rate=IvaRate.from_registry("EXEMPT"),
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=category,
        operation_type=operation_type,
    )


class TestInvoiceDirectionToSourceKind:
    """The application direction-to-settlement mapping is total."""

    def test_issued_maps_to_collectible(self) -> None:
        from ..source_resolver import invoice_direction_to_source_kind

        assert invoice_direction_to_source_kind(InvoiceKind.ISSUED) is BindingSourceKind.COLLECTIBLE_INVOICE

    def test_received_maps_to_payable(self) -> None:
        from ..source_resolver import invoice_direction_to_source_kind

        assert invoice_direction_to_source_kind(InvoiceKind.RECEIVED) is BindingSourceKind.PAYABLE_INVOICE


def test_source_resolver_translates_reader_failure_to_diagnostic() -> None:
    class DegradedReader:
        def load(self) -> InvoiceCatalogue:
            raise InvoiceSourcePersistenceError("invoice_catalogue_load")

    resolver = InvoiceCatalogueSourceResolver(
        ports=InvoiceSourceResolverPorts(catalogue_reader=DegradedReader()),
    )
    _modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in _modelos if candidate.id == "349")
    revision = select_revision(modelo, filing_year=2026, period="1T")

    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="349",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=revision,
    )
    resolution = resolver.resolve(context)

    # One diagnostic per invoice source the selected revision activates.
    active_sources = _invoice_sources_for_revision(context)
    assert active_sources
    assert tuple(d.reason for d in resolution.diagnostics) == ("storage_degraded",) * len(set(active_sources))


def test_source_resolver_projects_an_invoice_through_the_reader_port() -> None:
    invoice = _invoice(
        kind=InvoiceKind.ISSUED,
        number="F-2026-001",
        category=IvaCategory("intra_community_supply"),
    )
    _modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in _modelos if candidate.id == "349")
    revision = select_revision(modelo, filing_year=2026, period="1T")

    resolution = _resolver(build_invoice_catalogue([invoice])).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")
    assert resolution.source_transaction_ids == ()


def test_service_categories_resolve_directional_m349_claves_without_storage() -> None:
    issued = _invoice(
        kind=InvoiceKind.ISSUED,
        number="S-ISSUED",
        category=IvaCategory("intra_community_service_supply"),
    )
    received = _invoice(
        kind=InvoiceKind.RECEIVED,
        number="S-RECEIVED",
        category=IvaCategory("intra_community_service_acquisition_reverse_charge"),
    )

    assert _intracommunity_clave(issued) == "S"
    assert _intracommunity_clave(received) == "I"
