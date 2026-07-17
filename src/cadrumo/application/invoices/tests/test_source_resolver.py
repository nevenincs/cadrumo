"""Invoice catalogue source-mesh resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage import StorageValidationError
from ....application.ledger import (
    BusinessOperationInvoiceDirection,
    BusinessOperationInvoiceRepository,
    CollectibleInvoiceService,
    PayableInvoiceService,
)
from ....core import M347_THRESHOLD_EUR, BindingSourceKind, IntracomOperationType, Period
from ....core.errors import CadrumoError, get_registered_error_code, resolve_error_message
from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import RegistryValidationError, load_modelo_directory
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus
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


_BUCKET_ID = "24242424-2424-4242-8242-242424242424"
_OTHER_BUCKET_ID = "25252525-2525-4252-8252-252525252525"


def _modelo_revision(modelo_id: str, revision_id: str):
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo_id))
    return modelo.revisions[revision_id]


@pytest.fixture
def secure_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


def _invoice(
    *,
    bucket_id: str,
    kind: InvoiceKind = InvoiceKind.ISSUED,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str,
    base_total: Decimal,
    iva_category: IvaCategory,
    counterparty_name: str = "EU Customer GmbH",
    counterparty_country: str = "DE",
    linked_transaction_ids: tuple[str, ...] = ("1" * 64,),
) -> Invoice:
    from ....domain.invoices import derive_invoice_id

    invoice_id = derive_invoice_id(
        kind=kind,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency="EUR",
        grand_total=base_total,
    )
    return Invoice(
        invoice_id=invoice_id,
        bucket_id=bucket_id,
        kind=kind,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name=counterparty_name,
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
        linked_transaction_ids=linked_transaction_ids,
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

    assert resolution.owned_sources == (BindingSourceKind.COLLECTIBLE_INVOICE, BindingSourceKind.PAYABLE_INVOICE)
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")
    assert resolution.source_transaction_ids == ("1" * 64,)
    assert {item.source_kind for item in resolution.provenance} == {"collectible_invoice"}
    assert {item.source_ref for item in resolution.provenance} == {f"collectible_invoice:{declarable.invoice_id}"}
    assert all(item.fingerprint and item.fingerprint.startswith("sha256:") for item in resolution.provenance)


def test_invoice_catalogue_source_resolver_folds_received_acquisition_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    acquisition = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="R-2026-001",
        issued_at=date(2026, 1, 20),
        counterparty_name="EU Supplier GmbH",
        counterparty_tax_id="DE222222222",
        base_total=Decimal("1200.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        linked_transaction_ids=("2" * 64,),
    )
    repository.save(InvoiceCatalogue.from_invoices((acquisition,)))
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

    assert resolution.binding_values["iva-349-declarante-numero-operadores-adquisicion"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones-adquisicion"] == Decimal("1200.00")
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1200.00")
    assert resolution.source_transaction_ids == ("2" * 64,)
    assert {item.source_kind for item in resolution.provenance} == {"payable_invoice"}
    assert {item.source_ref for item in resolution.provenance} == {f"payable_invoice:{acquisition.invoice_id}"}


def test_invoice_catalogue_source_resolver_folds_slim_received_service_acquisition_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    added = PayableInvoiceService(settings=secure_profile.settings).add(
        bucket_id=secure_profile.bucket_id,
        counterparty_nif="IT12345678901",
        counterparty_name="Servizi SRL",
        invoice_number="IT-SERV-2026-001",
        invoice_date="2026-03-10",
        taxable_base=Decimal("3000.00"),
        iva_rate=Decimal("0"),
        country_code="IT",
        operation_type=IntracomOperationType.ADQUISICION_SERVICIOS,
    )
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    resolution = InvoiceCatalogueSourceResolver(
        invoice_repository=InvoiceCatalogueRepository(objects=secure_profile.repository),
        business_invoice_repository=BusinessOperationInvoiceRepository(objects=secure_profile.repository),
    ).resolve(
        CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    from ....domain.modelos import Modelo349OperadorRow

    assert resolution.binding_values["iva-349-declarante-numero-operadores-adquisicion"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones-adquisicion"] == Decimal("3000.00")
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("3000.00")
    assert len(resolution.detail_rows) == 1
    row = resolution.detail_rows[0]
    assert isinstance(row, Modelo349OperadorRow)
    assert row.codigo_pais == "IT"
    assert row.nif_comunitario == "IT12345678901"
    assert row.clave_operacion == "I"
    assert row.importe == Decimal("3000.00")
    assert {item.source_ref for item in resolution.provenance} == {f"payable_invoice:{added.record.invoice_id}"}


def test_invoice_catalogue_source_resolver_projects_domestic_m347_summary_from_invoice_totals(
    secure_profile: TestRuntimeProfile,
) -> None:
    collectible = CollectibleInvoiceService(settings=secure_profile.settings).add(
        bucket_id=secure_profile.bucket_id,
        counterparty_nif="B12345674",
        counterparty_name="Cliente M347 SL",
        invoice_number="M347-C-2025-001",
        invoice_date="2025-02-10",
        taxable_base=Decimal("1500.00"),
        iva_amount=Decimal("315.00"),
        total_amount=Decimal("1815.00"),
    )
    payable = PayableInvoiceService(settings=secure_profile.settings).add(
        bucket_id=secure_profile.bucket_id,
        counterparty_nif="B12345674",
        counterparty_name="Cliente M347 SL",
        invoice_number="M347-P-2025-001",
        invoice_date="2025-03-10",
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("190.07"),
        total_amount=Decimal("1190.07"),
    )
    floor_control = CollectibleInvoiceService(settings=secure_profile.settings).add(
        bucket_id=secure_profile.bucket_id,
        counterparty_nif="B87654321",
        counterparty_name="At Floor SL",
        invoice_number="M347-C-2025-002",
        invoice_date="2025-03-15",
        taxable_base=Decimal("2483.52"),
        iva_amount=Decimal("521.54"),
        total_amount=M347_THRESHOLD_EUR,
    )
    resolver = InvoiceCatalogueSourceResolver(
        invoice_repository=InvoiceCatalogueRepository(objects=secure_profile.repository),
        business_invoice_repository=BusinessOperationInvoiceRepository(objects=secure_profile.repository),
    )
    m347_revision = _modelo_revision("347", "2008-y-siguientes")

    m347_resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="347",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=m347_revision,
        ),
    )

    assert m347_resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert m347_resolution.binding_values[
        "modelo-347-declarante-importe-total-anual-operaciones"
    ] == M347_THRESHOLD_EUR + Decimal("0.01")
    assert m347_resolution.detail_rows == ()
    assert {item.source_ref for item in m347_resolution.provenance} == {
        f"collectible_invoice:{collectible.record.invoice_id}",
        f"payable_invoice:{payable.record.invoice_id}",
        f"collectible_invoice:{floor_control.record.invoice_id}",
    }

    m349_revision = _modelo_revision("349", "2020-y-siguientes")
    m349_resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="349",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            revision=m349_revision,
        ),
    )

    assert m349_resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert m349_resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("0")
    assert m349_resolution.detail_rows == ()
    assert m349_resolution.provenance == ()


def test_invoice_catalogue_source_resolver_folds_slim_consignment_transfer_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    added = CollectibleInvoiceService(settings=secure_profile.settings).add(
        bucket_id=secure_profile.bucket_id,
        counterparty_nif="DE222222222",
        counterparty_name="Consignment Customer GmbH",
        invoice_number="DE-CONSIGN-2026-001",
        invoice_date="2026-03-10",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0"),
        country_code="DE",
        operation_type=IntracomOperationType.R,
    )
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    resolution = InvoiceCatalogueSourceResolver(
        invoice_repository=InvoiceCatalogueRepository(objects=secure_profile.repository),
        business_invoice_repository=BusinessOperationInvoiceRepository(objects=secure_profile.repository),
    ).resolve(
        CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    from ....domain.modelos import Modelo349OperadorRow

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("100.00")
    assert len(resolution.detail_rows) == 1
    row = resolution.detail_rows[0]
    assert isinstance(row, Modelo349OperadorRow)
    assert row.codigo_pais == "DE"
    assert row.nif_comunitario == "DE222222222"
    assert row.clave_operacion == "R"
    assert row.importe == Decimal("100.00")
    assert {item.source_ref for item in resolution.provenance} == {f"collectible_invoice:{added.record.invoice_id}"}


def test_invoice_catalogue_source_resolver_accepts_current_slim_business_invoice_m349_claves(
    secure_profile: TestRuntimeProfile,
) -> None:
    collectible_service = CollectibleInvoiceService(settings=secure_profile.settings)
    payable_service = PayableInvoiceService(settings=secure_profile.settings)
    collectible_cases = (
        (IntracomOperationType.E, "DE100000001", Decimal("100.00")),
        (IntracomOperationType.H, "DE100000002", Decimal("200.00")),
        (IntracomOperationType.M, "DE100000003", Decimal("300.00")),
        (IntracomOperationType.S, "DE100000004", Decimal("400.00")),
        (IntracomOperationType.T, "DE100000005", Decimal("500.00")),
        (IntracomOperationType.R, "DE100000006", Decimal("600.00")),
        (IntracomOperationType.D, "DE100000007", Decimal("700.00")),
        (IntracomOperationType.C, "DE100000008", Decimal("800.00")),
    )
    payable_cases = (
        (IntracomOperationType.A, "DE200000001", Decimal("900.00")),
        (IntracomOperationType.ADQUISICION_SERVICIOS, "DE200000002", Decimal("1000.00")),
        (IntracomOperationType.T, "DE200000003", Decimal("1100.00")),
    )

    for index, (operation_type, nif, amount) in enumerate(collectible_cases, start=1):
        collectible_service.add(
            bucket_id=secure_profile.bucket_id,
            counterparty_nif=nif,
            counterparty_name=f"Collectible {operation_type.value}",
            invoice_number=f"DE-CURRENT-COLLECTIBLE-{index}",
            invoice_date="2026-03-10",
            taxable_base=amount,
            iva_rate=Decimal("0"),
            country_code="DE",
            operation_type=operation_type,
        )
    for index, (operation_type, nif, amount) in enumerate(payable_cases, start=1):
        payable_service.add(
            bucket_id=secure_profile.bucket_id,
            counterparty_nif=nif,
            counterparty_name=f"Payable {operation_type.value}",
            invoice_number=f"DE-CURRENT-PAYABLE-{index}",
            invoice_date="2026-03-10",
            taxable_base=amount,
            iva_rate=Decimal("0"),
            country_code="DE",
            operation_type=operation_type,
        )
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    resolution = InvoiceCatalogueSourceResolver(
        invoice_repository=InvoiceCatalogueRepository(objects=secure_profile.repository),
        business_invoice_repository=BusinessOperationInvoiceRepository(objects=secure_profile.repository),
    ).resolve(
        CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    from ....domain.modelos import Modelo349OperadorRow

    expected_amounts = {
        (nif, operation_type.value): amount for operation_type, nif, amount in (*collectible_cases, *payable_cases)
    }
    # Filter to only Modelo349OperadorRow rows (the expected type for M349 operations)
    operator_rows = [row for row in resolution.detail_rows if isinstance(row, Modelo349OperadorRow)]
    # Verify all expected keys are present in operator_rows
    found_keys = {(row.nif_comunitario, row.clave_operacion) for row in operator_rows}
    expected_keys = set(expected_amounts)
    assert found_keys == expected_keys
    # Verify amounts for each row
    for row in operator_rows:
        row_key: tuple[str, str] = (row.nif_comunitario, str(row.clave_operacion))
        assert row_key in expected_amounts
        assert row.importe == expected_amounts[row_key]
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal(len(expected_amounts))
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == sum(
        expected_amounts.values(),
        Decimal("0"),
    )
    assert resolution.binding_values["iva-349-declarante-numero-operadores-adquisicion"] == Decimal(
        len(payable_cases),
    )
    assert resolution.binding_values["iva-349-declarante-importe-operaciones-adquisicion"] == sum(
        (amount for _, _, amount in payable_cases),
        Decimal("0"),
    )


def test_invoice_catalogue_source_resolver_refuses_payable_consignment_transfer_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    PayableInvoiceService(settings=secure_profile.settings).add(
        bucket_id=secure_profile.bucket_id,
        counterparty_nif="DE222222222",
        counterparty_name="Supplier GmbH",
        invoice_number="DE-RECT-2026-001",
        invoice_date="2026-03-10",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0"),
        country_code="DE",
        operation_type=IntracomOperationType.R,
    )
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    with pytest.raises(RegistryValidationError, match="source kind 'payable_invoice'"):
        InvoiceCatalogueSourceResolver(
            invoice_repository=InvoiceCatalogueRepository(objects=secure_profile.repository),
            business_invoice_repository=BusinessOperationInvoiceRepository(objects=secure_profile.repository),
        ).resolve(
            CalculationSourceContext(
                bucket_id=secure_profile.bucket_id,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=snapshot.revision,
            ),
        )


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

    with pytest.raises(Modelo349CountryPrefixContextError) as exc:
        InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=snapshot.revision,
            ),
        )
    assert isinstance(exc.value, CadrumoError)
    assert get_registered_error_code(exc.value).code == "REFUSED_MODELO_349_COUNTRY_PREFIX_CONTEXT"
    message = resolve_error_message(exc.value)
    assert "post-transition" in message
    assert "AEAT Brexit IVA NIF-IVA" in message


def test_invoice_catalogue_source_resolver_fails_closed_when_context_bucket_is_not_active(
    tmp_path: Path,
) -> None:
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_BUCKET_ID,
        secondary_bucket_id=_OTHER_BUCKET_ID,
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
