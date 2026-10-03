"""Inward tests for the invoice source-mesh resolver.

The profile-persistence adapter suite owns encrypted catalogue integration.
These tests exercise application projections through the required reader port
with in-memory catalogues, so storage cannot become part of the application
test seam.
"""

from __future__ import annotations

from collections.abc import Mapping
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
from ....domain.modelos.row_models import Modelo349OperadorRow
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


def _domestic_invoice(
    *,
    kind: InvoiceKind,
    number: str,
    issued_at: date,
    counterparty_tax_id: str,
    counterparty_name: str,
    base_total: Decimal,
    iva_total: Decimal,
) -> Invoice:
    """A domestic invoice carrying real IVA, so the gross total differs from the base."""
    grand_total = base_total + iva_total
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued_at,
            counterparty_tax_id=counterparty_tax_id,
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=_BUCKET_ID,
        kind=kind,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country="ES",
        base_total=base_total,
        iva_total=iva_total,
        grand_total=grand_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PAID,
    )


def _m347_context(filing_year: int) -> CalculationSourceContext:
    _modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in _modelos if candidate.id == "347")
    return CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="347",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        revision=select_revision(modelo, filing_year=filing_year, period="0A"),
    )


def _rows_by_index(row_binding_values: Mapping[tuple[str, int], object]) -> list[dict[str, object]]:
    """Group ``(binding, row)`` values into one mapping per row, keyed by the binding's field suffix."""
    rows: dict[int, dict[str, object]] = {}
    for (binding_id, row_index), value in row_binding_values.items():
        rows.setdefault(row_index, {})[binding_id.removeprefix("modelo-347-contraparte-row-")] = value
    return [rows[index] for index in sorted(rows)]


def test_m347_resolution_returns_one_declarado_row_per_declarable_counterparty_and_clave() -> None:
    """The live 347 path carries the type 2 declarado records on the row-binding channel.

    Each record is (counterparty, clave) with the gross annual amount and its
    quarterly split (RD 1065/2007 art. 33.1 "se suministrará desglosada
    trimestralmente"); the supplier below the 3.005,06 floor yields no record.
    """
    supplier_q1 = _domestic_invoice(
        kind=InvoiceKind.RECEIVED,
        number="P-001",
        issued_at=date(2025, 2, 10),
        counterparty_tax_id="B12345674",
        counterparty_name="PROVEEDOR GRANDE SL",
        base_total=Decimal("2500.00"),
        iva_total=Decimal("525.00"),
    )
    supplier_q3 = _domestic_invoice(
        kind=InvoiceKind.RECEIVED,
        number="P-002",
        issued_at=date(2025, 8, 10),
        counterparty_tax_id="B12345674",
        counterparty_name="PROVEEDOR GRANDE SL",
        base_total=Decimal("2500.00"),
        iva_total=Decimal("525.00"),
    )
    customer_q4 = _domestic_invoice(
        kind=InvoiceKind.ISSUED,
        number="V-001",
        issued_at=date(2025, 11, 20),
        counterparty_tax_id="B87654323",
        counterparty_name="CLIENTE GRANDE SL",
        base_total=Decimal("6611.57"),
        iva_total=Decimal("1388.43"),
    )
    small_supplier = _domestic_invoice(
        kind=InvoiceKind.RECEIVED,
        number="P-003",
        issued_at=date(2025, 5, 5),
        counterparty_tax_id="A58818501",
        counterparty_name="PROVEEDOR PEQUENO SA",
        base_total=Decimal("826.45"),
        iva_total=Decimal("173.55"),
    )

    resolution = _resolver(
        build_invoice_catalogue([supplier_q1, supplier_q3, customer_q4, small_supplier]),
    ).resolve(_m347_context(2025))

    rows = sorted(_rows_by_index(resolution.row_binding_values), key=lambda row: str(row["nif"]))
    assert rows == [
        {
            "nif": "B12345674",
            "nombre": "PROVEEDOR GRANDE SL",
            "clave": "A",
            "pais-codigo": "ES",
            "importe": supplier_q1.grand_total + supplier_q3.grand_total,
            "importe-q1": supplier_q1.grand_total,
            "importe-q2": Decimal("0"),
            "importe-q3": supplier_q3.grand_total,
            "importe-q4": Decimal("0"),
        },
        {
            "nif": "B87654323",
            "nombre": "CLIENTE GRANDE SL",
            "clave": "B",
            "pais-codigo": "ES",
            "importe": customer_q4.grand_total,
            "importe-q1": Decimal("0"),
            "importe-q2": Decimal("0"),
            "importe-q3": Decimal("0"),
            "importe-q4": customer_q4.grand_total,
        },
    ]
    assert resolution.detail_rows == ()
    # The type 1 count is the number of declarado records the same resolution emits.
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal(len(rows))


def test_m347_resolution_with_no_declarable_counterparty_returns_no_rows() -> None:
    """A counterparty below the floor produces no record rather than a zero-amount one."""
    small_supplier = _domestic_invoice(
        kind=InvoiceKind.RECEIVED,
        number="P-004",
        issued_at=date(2025, 5, 5),
        counterparty_tax_id="A58818501",
        counterparty_name="PROVEEDOR PEQUENO SA",
        base_total=Decimal("826.45"),
        iva_total=Decimal("173.55"),
    )

    resolution = _resolver(build_invoice_catalogue([small_supplier])).resolve(_m347_context(2025))

    assert dict(resolution.row_binding_values) == {}
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("0")


def test_m349_operador_rows_travel_once_as_typed_detail_rows() -> None:
    """349 keeps its operador rows on the typed detail-row channel and does not repeat them as row bindings."""
    invoice = _invoice(
        kind=InvoiceKind.ISSUED,
        number="F-2026-002",
        category=IvaCategory("intra_community_supply"),
    )
    _modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in _modelos if candidate.id == "349")

    resolution = _resolver(build_invoice_catalogue([invoice])).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=select_revision(modelo, filing_year=2026, period="1T"),
        ),
    )

    assert [type(row) for row in resolution.detail_rows] == [Modelo349OperadorRow]
    operador = resolution.detail_rows[0]
    assert isinstance(operador, Modelo349OperadorRow)
    assert (operador.nif_comunitario, operador.clave_operacion, operador.importe) == (
        "DE123456789",
        "E",
        Decimal("1000.00"),
    )
    assert dict(resolution.row_binding_values) == {}
