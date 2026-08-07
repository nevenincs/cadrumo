"""Invoice catalogue source-mesh resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

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
from .._source_resolver import _OWNED_SOURCES, _intracommunity_clave

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
    bucket_id: str | None,
    kind: InvoiceKind = InvoiceKind.ISSUED,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str,
    base_total: Decimal,
    iva_category: IvaCategory,
    counterparty_name: str = "EU Customer GmbH",
    counterparty_country: str = "DE",
    linked_transaction_ids: tuple[str, ...] = ("1" * 64,),
    currency: str = "EUR",
    fx_rate: Decimal | None = None,
    fx_rate_date: date | None = None,
) -> Invoice:
    from ....domain.invoices import derive_invoice_id

    invoice_id = derive_invoice_id(
        kind=kind,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency=currency,
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
        currency=currency,
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
        fx_rate=fx_rate,
        fx_rate_date=fx_rate_date,
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


def test_converted_foreign_invoice_projects_its_euro_value_not_its_face_value(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A GBP invoice contributes euro, so the declared importe is the converted amount.

    ECB EXR.D.GBP.EUR.SP00.A on 2026-01-15 is stubbed here as the stored
    GBP->EUR multiplier; 1000.00 GBP at that rate is 1187.89 EUR. Declaring the
    face value 1000.00 would over- or under-state the modelo by the FX spread.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    gbp_rate = Decimal("1") / Decimal("0.84183")
    converted = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-010",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        currency="GBP",
        fx_rate=gbp_rate,
        fx_rate_date=date(2026, 1, 15),
    )
    repository.save(InvoiceCatalogue.from_invoices((converted,)))
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

    expected_eur = (Decimal("1000.00") * gbp_rate).quantize(Decimal("0.01"))
    assert expected_eur == Decimal("1187.89")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == expected_eur
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] != Decimal("1000.00")


def test_unconverted_foreign_invoice_is_withheld_from_projection(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A foreign invoice with no resolved rate must not reach the modelo at all.

    Its euro value is unknown, so the only safe outcomes are exclusion or
    refusal -- never declaring the foreign face value as euro. This mirrors the
    ledger's ``is_non_eur_without_conversion`` gate.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    unconverted = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-011",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        currency="GBP",
    )
    repository.save(InvoiceCatalogue.from_invoices((unconverted,)))
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

    # No operator counted, and no importe declared from the foreign face value.
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] != Decimal("1000.00")


@pytest.mark.unit
def test_a_service_category_alone_resolves_its_m349_clave() -> None:
    """A record carrying the service category but NO operation_type still files.

    The operation-type branch short-circuits ahead of the category branches, so
    an invoice created through the CLI reaches its clave via ``operation_type``
    and never exercises these lines. A record carrying only the IVA category --
    which the creation service permits, the two fields being independent --
    would otherwise resolve to no clave at all and drop out of the
    recapitulativa silently.

    Asserted on both directions and against the goods claves, because filing a
    service as E or A would report it as an entrega/adquisición de bienes.
    """
    issued = _clave_probe_invoice(InvoiceKind.ISSUED, IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY)
    received = _clave_probe_invoice(
        InvoiceKind.RECEIVED,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    )

    assert issued.operation_type is None
    assert received.operation_type is None
    assert _intracommunity_clave(issued) == "S"
    assert _intracommunity_clave(received) == "I"


@pytest.mark.unit
def test_a_service_category_on_its_impossible_side_resolves_no_clave() -> None:
    """The directional half of the same branch.

    A supply category on a received invoice, or an acquisition category on an
    issued one, describes an operation that does not arise. Resolving a clave
    for it would file a fabricated row, so the branch must decline.
    """
    wrong_way_supply = _clave_probe_invoice(
        InvoiceKind.RECEIVED,
        IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
    )
    wrong_way_acquisition = _clave_probe_invoice(
        InvoiceKind.ISSUED,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    )

    assert _intracommunity_clave(wrong_way_supply) is None
    assert _intracommunity_clave(wrong_way_acquisition) is None


def _clave_probe_invoice(kind: InvoiceKind, category: IvaCategory) -> Invoice:
    """Build a minimal exempt-shaped invoice carrying a category and no operation_type."""
    base = Decimal("1000.00")
    line = InvoiceLine(
        description="Servicio intracomunitario",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.EXEMPT,
        iva_amount=Decimal("0.00"),
    )
    # invoice_id is omitted deliberately: a before-validator on the model derives
    # it from the identity-bearing fields, so supplying one here would test a
    # different construction path than production uses.
    return Invoice(  # ty: ignore[missing-argument]
        kind=kind,
        invoice_number="CLAVE/1",
        issued_at=date(2026, 2, 1),
        counterparty_name="Contraparte UE",
        counterparty_tax_id="FR12345678901",
        counterparty_country="FR",
        base_total=base,
        iva_total=Decimal("0.00"),
        grand_total=base,
        currency="EUR",
        lines=(line,),
        payment_status=PaymentStatus.PAID,
        iva_category=category,
    )


# ---------------------------------------------------------------------------
# Declarable-coverage proof
#
# Folding the slim store into the canonical structure retires a live M347/M349
# source. What has to survive that retirement is not the slim store's OUTPUT
# but the set of declarable FACTS it contributes, so these tests assert
# fact-level reachability on the canonical path.
#
# They deliberately do NOT assert equality against a resolver wired to both
# stores. That union double-counts an invoice held in both, so a union-equality
# assertion would demand the canonical path reproduce the double-count -- it is
# either unsatisfiable or it pins the very defect this campaign removes. Instead
# each store is projected ALONE and both are asserted against one explicit
# contract, so the contract is the thing conserved.
# ---------------------------------------------------------------------------

_DECLARABLE_FACTS: frozenset[str] = frozenset(
    {
        "party_tax_id",
        "country_code",
        "transaction_date",
        "base_amount",
        "invoice_total_amount",
        "intracommunity_clave",
        "party_legal_name",
    },
)


def _declarable_facts(observation: object) -> dict[str, Any]:
    """Project an observation onto the declarable-fact contract.

    Reads through the fact set rather than listing attributes inline, so a fact
    dropped from the contract fails the enumeration guard below instead of
    silently shrinking what these proofs cover.
    """
    return {name: getattr(observation, name) for name in sorted(_DECLARABLE_FACTS)}


def test_declarable_fact_contract_covers_every_observation_fact_the_stores_contribute() -> None:
    """Anti-tautology guard on the contract itself.

    Every proof below compares fact dicts built from the same fact set. If a
    fact were quietly removed from that set the comparisons would still pass
    while covering less, so the set is pinned against the observation model's
    own declarable surface. Identity and rectification axes are excluded by
    name, which forces a newly-added declarable field to fail here rather than
    slip past the coverage proofs unnoticed.
    """
    from ....domain.calculations.registry import InvoiceObservation

    non_declarable = {
        "invoice_id",
        "source_kind",
        "iva_regime",
        "is_rectification",
        "rectified_year",
        "rectified_period",
        "rectified_base_previous",
    }
    assert set(InvoiceObservation.model_fields) - non_declarable == _DECLARABLE_FACTS


def test_m349_declarable_facts_are_reachable_on_the_canonical_path(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Every M349 fact the slim store contributes must be reachable canonically.

    The counterparty carries BOTH a domestic-format NIF and an EU VAT ID, which
    is the case that separates the two paths. The slim record has no coupling
    between its tax id and its country, so it needs a second identity field and
    a prefix-derivation fallback to decide who is being declared. The canonical
    record reaches the same declared party by a stronger route: a non-ES country
    forces the tax id to BE that country's NIF-IVA, so there is only ever one
    party identity on the aggregate. Same facts, fewer authorities.
    """
    from .._source_resolver import _business_invoice_observation, _invoice_observation

    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="349",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=resources().modelos.authority.snapshot("349", filing_year=2026, period="1T").revision,
    )

    slim = (
        PayableInvoiceService(settings=secure_profile.settings)
        .add(
            bucket_id=secure_profile.bucket_id,
            counterparty_nif="B12345674",
            counterparty_name="Servizi SRL",
            invoice_number="IT-SERV-2026-001",
            invoice_date="2026-03-10",
            taxable_base=Decimal("3000.00"),
            iva_rate=Decimal("0"),
            total_amount=Decimal("3000.00"),
            country_code=None,
            eu_iva_id="DE345678901",
            operation_type=IntracomOperationType.ADQUISICION_SERVICIOS,
        )
        .record
    )
    slim_facts = _declarable_facts(_business_invoice_observation(slim, context=context))

    canonical = _invoice(
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.RECEIVED,
        invoice_number="IT-SERV-2026-001",
        issued_at=date(2026, 3, 10),
        counterparty_tax_id="DE345678901",
        counterparty_name="Servizi SRL",
        counterparty_country="DE",
        base_total=Decimal("3000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    )
    canonical_facts = _declarable_facts(_invoice_observation(canonical, context=context))

    assert canonical_facts == slim_facts


def test_canonical_invoice_refuses_the_tax_id_country_mismatch_slim_permits(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The mechanism by which canonical conserves M349 party identity.

    This is the other half of the proof above, and it is why the canonical
    aggregate needs no second EU-VAT-ID field. The slim record accepts a
    Spanish-format NIF alongside a German country because nothing couples the
    two, which is exactly what forces it to carry a separate identity field and
    prefer it at projection time. The canonical record refuses that shape: a
    non-ES country validates the tax id against that country's published
    NIF-IVA pattern, so the only representable party identity is already the
    one M349 must declare.

    Adding an EU-VAT-ID field to the canonical aggregate would therefore
    install a SECOND party-identity authority on the record -- two fields that
    can disagree about who was invoiced -- on the axis where a disagreement is
    a mis-declared intra-community operator.
    """
    from pydantic import ValidationError

    # Matched on the message, not merely on the exception type: the point is
    # that the COUNTRY/TAX-ID coupling fired, not that some validator did.
    with pytest.raises(ValidationError, match="DE"):
        _invoice(
            bucket_id=secure_profile.bucket_id,
            kind=InvoiceKind.RECEIVED,
            invoice_number="IT-SERV-2026-002",
            issued_at=date(2026, 3, 11),
            counterparty_tax_id="B12345674",
            counterparty_name="Servizi SRL",
            counterparty_country="DE",
            base_total=Decimal("3000.00"),
            iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        )


def test_m347_declarable_facts_are_reachable_on_the_canonical_path(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Every M347 fact the slim store contributes must be reachable canonically.

    The gross total is kept distinct from the taxable base here on purpose:
    M347's declaration floor is the gross total, so a proof whose base and total
    coincide would not detect the two being confused.
    """
    from ....domain.invoices import derive_invoice_id
    from .._source_resolver import _business_invoice_observation, _invoice_observation

    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision=_modelo_revision("347", "2008-y-siguientes"),
    )

    slim = (
        CollectibleInvoiceService(settings=secure_profile.settings)
        .add(
            bucket_id=secure_profile.bucket_id,
            counterparty_nif="B12345674",
            counterparty_name="Cliente M347 SL",
            invoice_number="M347-C-2025-001",
            invoice_date="2025-02-10",
            taxable_base=Decimal("1500.00"),
            iva_amount=Decimal("315.00"),
            total_amount=Decimal("1815.00"),
            country_code="ES",
        )
        .record
    )
    slim_facts = _declarable_facts(_business_invoice_observation(slim, context=context))

    canonical = Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.ISSUED,
            invoice_number="M347-C-2025-001",
            issued_at=date(2025, 2, 10),
            counterparty_tax_id="B12345674",
            currency="EUR",
            grand_total=Decimal("1815.00"),
        ),
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-C-2025-001",
        issued_at=date(2025, 2, 10),
        counterparty_name="Cliente M347 SL",
        counterparty_tax_id="B12345674",
        counterparty_country="ES",
        base_total=Decimal("1500.00"),
        iva_total=Decimal("315.00"),
        grand_total=Decimal("1815.00"),
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Servicio",
                quantity=Decimal("1"),
                unit_price=Decimal("1500.00"),
                subtotal=Decimal("1500.00"),
                iva_rate=IvaRate.RATE_21,
                iva_amount=Decimal("315.00"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
    )
    canonical_facts = _declarable_facts(_invoice_observation(canonical, context=context))

    assert canonical_facts == slim_facts


def test_an_unattributed_invoice_in_the_bucket_store_is_still_declared(
    secure_profile: TestRuntimeProfile,
) -> None:
    """An invoice carrying no bucket must not vanish from the informativas.

    The repository is opened against one bucket and refuses a foreign row on
    read, so an invoice loaded here came from THIS bucket's encrypted store.
    An unattributed one therefore belongs to this bucket; it simply never had
    the redundant field stamped.

    Comparing on the bucket id alone treats that as a mismatch and drops the
    record from M347 and M349 with no defect, no advisory and no refusal --
    and nothing downstream can distinguish "this taxpayer had no such
    operations" from "the filter discarded them". The persistence guard
    already treats an unattributed record as belonging rather than foreign, so
    before this the two layers disagreed about the same record.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    unattributed = _invoice(
        bucket_id=None,
        invoice_number="F-2026-UNATTRIBUTED",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    repository.save(InvoiceCatalogue.from_invoices((unattributed,)))
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
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")


def test_an_invoice_naming_another_bucket_is_still_excluded(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Positive control: the attribution filter is narrowed, not removed.

    Admitting unattributed invoices must not admit invoices that positively
    name a DIFFERENT bucket. Without this control the change above would read
    as correct while having disabled cross-bucket isolation, which is a
    confidentiality failure rather than a declaration one -- one taxpayer's
    invoice surfacing in another's return.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    foreign = _invoice(
        bucket_id=_OTHER_BUCKET_ID,
        invoice_number="F-2026-FOREIGN",
        issued_at=date(2026, 1, 16),
        counterparty_tax_id="DE987654321",
        base_total=Decimal("500.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    repository.save(InvoiceCatalogue.from_invoices((foreign,)))
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

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolution.provenance == ()


# ---------------------------------------------------------------------------
# Capability-parity proof (invoice-canonical-structure P01.S31)
#
# One bucket exercising the capabilities that reach a declaration, projected
# through the canonical path, asserted at MODELO-OUTPUT level rather than at
# fact level (which P01.S01 already covers).
#
# The Step's criterion also named M303 and M390. Measured at HEAD, neither
# modelo declares a single invoice-sourced binding -- only M347 (one fragment)
# and M349 (three) do. An equality assertion on those two modelos would
# therefore compare zero against zero and pass by construction, proving
# nothing: the vacuous-green shape this plan was rewritten to remove.
#
# So the M303/M390 half is written as the assertion that actually has content:
# that the invoice stores contribute NOTHING there. That is true today, it is
# what makes the parity proof's scope correct, and it fails loudly if anyone
# later adds an invoice-sourced binding to either modelo without extending this
# proof -- which is precisely the change that would silently widen the fold's
# blast radius past what was verified.
# ---------------------------------------------------------------------------


def _capability_bucket_invoices(bucket_id: str) -> tuple[Invoice, ...]:
    """Invoices covering every capability that reaches M347 or M349."""
    return (
        # Domestic, over the M347 declaration floor, carrying a recargo and a
        # retencion: both must ride through without disturbing the declared
        # figures, since neither is an M347 concept.
        _invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.ISSUED,
            invoice_number="CAP-ES-001",
            issued_at=date(2026, 2, 3),
            counterparty_tax_id="B12345674",
            counterparty_name="Cliente Domestico SL",
            counterparty_country="ES",
            base_total=Decimal("4000.00"),
            iva_category=IvaCategory.DOMESTIC_ZERO,
        ),
        # Intra-community supply of goods -> M349 clave E.
        _invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.ISSUED,
            invoice_number="CAP-DE-001",
            issued_at=date(2026, 2, 10),
            counterparty_tax_id="DE345678901",
            counterparty_name="Kunde GmbH",
            counterparty_country="DE",
            base_total=Decimal("1500.00"),
            iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        ),
        # Intra-community acquisition of SERVICES -> M349 clave I. This is the
        # class the resolver docstring once claimed no IVA category could
        # express, so its presence here is deliberate.
        _invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.RECEIVED,
            invoice_number="CAP-IT-001",
            issued_at=date(2026, 3, 5),
            counterparty_tax_id="IT12345678901",
            counterparty_name="Servizi SRL",
            counterparty_country="IT",
            base_total=Decimal("800.00"),
            iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        ),
    )


def test_capability_parity_m349_declares_every_intracommunity_capability(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Both M349 directions and both claves survive the canonical path together.

    Run as one bucket rather than as separate single-invoice cases: the
    declarante summaries aggregate across records, so an error that only shows
    up when a supply and an acquisition are counted together -- a mis-signed
    fold, a direction collapsed onto one clave -- is invisible to per-invoice
    tests and is exactly what a parity proof exists to catch.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(InvoiceCatalogue.from_invoices(_capability_bucket_invoices(_BUCKET_ID)))
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

    from ....domain.modelos import Modelo349OperadorRow

    rows = [row for row in resolution.detail_rows if isinstance(row, Modelo349OperadorRow)]
    by_clave = {row.clave_operacion: row for row in rows}
    assert set(by_clave) == {"E", "I"}, by_clave
    assert by_clave["E"].nif_comunitario == "DE345678901"
    assert by_clave["E"].codigo_pais == "DE"
    assert by_clave["E"].importe == Decimal("1500.00")
    assert by_clave["I"].nif_comunitario == "IT12345678901"
    assert by_clave["I"].codigo_pais == "IT"
    assert by_clave["I"].importe == Decimal("800.00")
    # The domestic invoice is not an intra-community operation and must not
    # appear, so the proof also pins that the bucket is not over-declared.
    assert len(rows) == 2


def test_capability_parity_m347_declares_only_the_domestic_party(
    secure_profile: TestRuntimeProfile,
) -> None:
    """M347 counts the domestic party and excludes the intra-community ones.

    The same bucket as the M349 proof, asserted from the other modelo, because
    the two projections share one resolver and a filter error would move a
    record between them rather than losing it -- a shape that a single-modelo
    proof reads as correct.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(InvoiceCatalogue.from_invoices(_capability_bucket_invoices(_BUCKET_ID)))

    resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="347",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            revision=_modelo_revision("347", "2008-y-siguientes"),
        ),
    )

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4000.00")


@pytest.mark.parametrize(("modelo_id", "period"), [("303", "1T"), ("390", "0A")])
def test_the_invoice_stores_contribute_nothing_to_m303_or_m390(modelo_id: str, period: str) -> None:
    """Scope guard, and the honest form of this Step's M303/M390 criterion.

    Neither modelo declares a single invoice-sourced binding, so an equality
    assertion on their outputs would compare zero against zero and pass by
    construction. The assertion with content is the scope itself: the invoice
    stores feed M347 and M349 and nothing else.

    This fails the moment an invoice-sourced binding is added to either modelo,
    which is the change that would silently widen the fold's blast radius past
    what the parity proof above verifies.
    """
    revision = resources().modelos.authority.snapshot(modelo_id, filing_year=2026, period=period).revision
    invoice_sourced = [binding for binding in revision.bindings if binding.source in _OWNED_SOURCES]

    assert invoice_sourced == [], (
        f"modelo {modelo_id} now declares invoice-sourced bindings; "
        "extend the capability-parity proof before relying on it"
    )


def test_an_explicit_operation_type_resolves_a_clave_without_any_iva_category() -> None:
    """The measured ground for M349 absence being non-disqualifying.

    This is the executable form of the justification in
    ``_m349_incoherent_verdict``. An absent IVA category does not mean the
    operation was inexpressible; it usually means the clave came from the
    explicitly declared operation type, which is consulted first and returns
    without ever reading the category.

    Treating absence as disqualifying would therefore drop exactly the records
    whose clave the operator stated most directly. If this ever fails, that
    justification is void and the guard must be re-decided rather than
    re-explained.
    """
    invoice = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="EXPLICIT-CLAVE-001",
        issued_at=date(2026, 2, 1),
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        base_total=Decimal("100.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    ).model_copy(update={"iva_category": None, "operation_type": IntracomOperationType.E})

    assert invoice.iva_category is None
    assert _intracommunity_clave(invoice) == "E"


def test_the_intra_community_service_categories_exist_and_map_to_their_claves() -> None:
    """Pins the premise that refuted the previous justification.

    The retired reasoning asserted that intra-community services mapped to no
    IVA category member at all. Both members exist and both resolve to their
    own clave -- kept distinct from the goods claves, because a service
    declared as an entrega would be filed as an entrega de bienes.
    """
    supply = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="SERV-S-001",
        issued_at=date(2026, 2, 1),
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        base_total=Decimal("100.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
    )
    acquisition = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="SERV-I-001",
        issued_at=date(2026, 2, 1),
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        base_total=Decimal("100.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    )

    assert _intracommunity_clave(supply) == "S"
    assert _intracommunity_clave(acquisition) == "I"


# ---------------------------------------------------------------------------
# Decomposition parity across the fold (invoice-canonical-structure P01.S33)
#
# The decomposition contract is calc-facing and has only ever seen natively
# rich records. The fold routes a new population into it, so what happens to a
# record carrying the economic facts a slim record could hold -- and nothing
# more -- has to be stated rather than discovered later.
#
# The one axis that actually diverges is the IVA category: the slim model
# cannot hold one at all. Everything else the slim record lacks (recargo,
# suplido, retencion, the line set) is read through a zero default by the
# contract, so a record lacking those decomposes cleanly and a test asserting
# divergence there would be GREEN FOR THE WRONG REASON.
# ---------------------------------------------------------------------------


def _same_facts_invoice(*, with_category: bool):
    """One economic record, expressed with and without an IVA category."""
    from ....domain.invoices import derive_invoice_id

    kind = InvoiceKind.ISSUED
    number = "PARITY-2026-001"
    issued = date(2026, 4, 2)
    tax_id = "B12345674"
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued,
            counterparty_tax_id=tax_id,
            currency="EUR",
            grand_total=Decimal("4840.00"),
        ),
        bucket_id=_BUCKET_ID,
        kind=kind,
        invoice_number=number,
        issued_at=issued,
        counterparty_name="Cliente Paridad SL",
        counterparty_tax_id=tax_id,
        counterparty_country="ES",
        base_total=Decimal("4000.00"),
        iva_total=Decimal("840.00"),
        grand_total=Decimal("4840.00"),
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Servicio",
                quantity=Decimal("1"),
                unit_price=Decimal("4000.00"),
                subtotal=Decimal("4000.00"),
                iva_rate=IvaRate.RATE_21,
                iva_amount=Decimal("840.00"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=IvaCategory.DOMESTIC_GENERAL_21 if with_category else None,
    )


def test_the_only_decomposition_divergence_across_the_fold_is_the_iva_category() -> None:
    """Identical economic facts diverge on exactly one axis, and it is named.

    The record lacking an IVA category is the shape a slim record could hold,
    since the slim model has no category field at all. Its rich twin carries
    the same base, cuota, total and line, and differs only in that declaration.

    The divergence is real and it is reported as a NAMED defect rather than as
    a silent exclusion, which is what makes it actionable: the operator is told
    to declare the treatment, not left with a record that quietly contributes
    nothing.
    """
    from ....domain.invoices import InvoiceDecompositionDefect, decompose_invoice

    grounded = decompose_invoice(_same_facts_invoice(with_category=True))
    ungrounded = decompose_invoice(_same_facts_invoice(with_category=False))

    assert grounded.is_grounded
    assert not ungrounded.is_grounded
    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED in ungrounded.defects


def test_the_informativas_are_unaffected_by_that_divergence(
    secure_profile: TestRuntimeProfile,
) -> None:
    """M347 declares the ex-slim record identically. This is the important half.

    The campaign record warns that a test asserting an ex-slim record is
    DROPPED from M347 or M349 by decomposition would be red for a defect that
    does not exist: M347 is deliberately unchecked by the contract, and M349
    excludes absence deliberately. So the proof aims where a loss could really
    occur, and pins that no loss occurs here.

    Asserted as an equality between the two records' declared figures rather
    than as a bare non-zero, so a projection that silently degraded the
    uncategorised record would fail rather than pass.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(InvoiceCatalogue.from_invoices((_same_facts_invoice(with_category=False),)))
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2008-y-siguientes"),
    )

    resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(context)

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4840.00")


def test_the_renta_lane_is_where_the_divergence_actually_bites() -> None:
    """The income lane refuses the uncategorised record, and does so visibly.

    This is the lane that loses capability, and the loss is bounded: the
    refusal carries the typed defect naming what is missing, and the
    remediation text tells the operator to declare the treatment. A record that
    cannot be grounded is withheld from the income calculation rather than
    contributing an unclassified figure to it -- which is the correct
    behaviour, since an untagged operation cannot be told apart from an exempt
    one.
    """
    from ....domain.invoices import InvoiceDecompositionDefect, decompose_invoice

    verdict = decompose_invoice(_same_facts_invoice(with_category=False))

    assert not verdict.is_grounded
    assert not verdict.components
    # Named, not anonymous: the operator fix for an absent category differs
    # from the fix for a contradictory one, so the two must stay separable.
    assert verdict.defects == (InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED,)
