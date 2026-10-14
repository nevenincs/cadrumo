"""Invoice catalogue source resolver tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.source_resolver import invoice_direction_to_source_kind
from cadrumo.application.invoices.source_resolver_ports import InvoiceSourcePersistenceError
from cadrumo.core.aggregation import BindingSourceKind, IntracomOperationType
from cadrumo.core.errors.error_codes import get_registered_error_code, resolve_error_message
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.m347_threshold import m347_threshold_decimal
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from cadrumo.domain.invoices.models import InvoiceCatalogue
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.modelos.row_models import Modelo349CountryPrefixContextError

from .....domain.calculations.registry.tests.m347_fixture import resolve_m347_counterparty_annual_threshold
from .source_resolver_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    _domestic_invoice,
    _invoice,
    _modelo_revision,
    _resolver,
)
from .source_resolver_test_support import _generation_pinned_authority as _generation_pinned_authority
from .source_resolver_test_support import secure_profile as secure_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class TestInvoiceDirectionToSourceKind:
    """The single contractual direction→settlement mapping consumed by the
    resolver and the unified operator invoice CLI."""

    def test_issued_maps_to_collectible(self) -> None:
        assert invoice_direction_to_source_kind(InvoiceKind.ISSUED) is BindingSourceKind.COLLECTIBLE_INVOICE

    def test_received_maps_to_payable(self) -> None:
        assert invoice_direction_to_source_kind(InvoiceKind.RECEIVED) is BindingSourceKind.PAYABLE_INVOICE

    def test_mapping_is_total_over_invoice_kind(self) -> None:
        # Anti-tautology: the function must resolve every InvoiceKind member to a
        # distinct source kind, never collapse the two directions onto one.
        resolved = {invoice_direction_to_source_kind(kind) for kind in InvoiceKind}
        assert resolved == {
            BindingSourceKind.COLLECTIBLE_INVOICE,
            BindingSourceKind.PAYABLE_INVOICE,
        }


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
        iva_category=IvaCategory("intra_community_supply"),
    )
    other_bucket = _invoice(
        bucket_id=_OTHER_BUCKET_ID,
        invoice_number="F-2026-002",
        issued_at=date(2026, 1, 16),
        counterparty_tax_id="DE987654321",
        base_total=Decimal("500.00"),
        iva_category=IvaCategory("intra_community_supply"),
    )
    domestic = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-003",
        issued_at=date(2026, 1, 17),
        counterparty_tax_id="DE111111125",
        base_total=Decimal("250.00"),
        iva_category=IvaCategory("domestic_zero"),
    )
    repository.save(build_invoice_catalogue((declarable, other_bucket, domestic)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    resolution = _resolver(repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.owned_sources == (
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
        BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
        BindingSourceKind.PAYABLE_INVOICE,
    )
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")
    assert resolution.source_transaction_ids == ("1" * 64,)
    assert {item.contributor_source_kind for item in resolution.provenance} == {"collectible_invoice"}
    assert {item.resolver_id for item in resolution.provenance} == {"invoice_catalogue"}
    assert {item.source_ref for item in resolution.provenance} == {f"collectible_invoice:{declarable.invoice_id}"}
    assert all(item.fingerprint and item.fingerprint.startswith("sha256:") for item in resolution.provenance)


def test_invoice_catalogue_source_resolver_counts_received_acquisition_for_m349(
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
        iva_category=IvaCategory("intra_community_acquisition_reverse_charge"),
        linked_transaction_ids=("2" * 64,),
    )
    repository.save(build_invoice_catalogue((acquisition,)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    resolution = _resolver(repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1200.00")
    assert resolution.source_transaction_ids == ("2" * 64,)
    assert {item.contributor_source_kind for item in resolution.provenance} == {"payable_invoice"}
    assert {item.source_ref for item in resolution.provenance} == {f"payable_invoice:{acquisition.invoice_id}"}


def test_invoice_catalogue_source_resolver_projects_domestic_m347_summary_from_invoice_totals(
    secure_profile: TestRuntimeProfile,
) -> None:
    """M347 counts a counterparty only once one of its threshold buckets passes the floor.

    The first counterparty's sale and purchase together exceed the floor, but
    RD 1065/2007 art. 33.1 computes "de forma separada las entregas y las
    adquisiciones", so each bucket stays below it and nothing is declared. The
    third invoice sits at EXACTLY the threshold, not above it: M347's floor is
    "supera", so a counterparty landing on the figure is not declarable, and a
    test whose control sat comfortably below would pass just as well against a
    `>=` comparison.
    """
    collectible = _domestic_invoice(
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-C-2025-001",
        issued_at=date(2025, 2, 10),
        counterparty_tax_id="B12345674",
        counterparty_name="Cliente M347 SL",
        base_total=Decimal("1500.00"),
        iva_total=Decimal("315.00"),
    )
    payable = _domestic_invoice(
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-P-2025-001",
        issued_at=date(2025, 3, 10),
        counterparty_tax_id="B12345674",
        counterparty_name="Cliente M347 SL",
        base_total=Decimal("983.53"),
        iva_total=Decimal("206.54"),
    )
    floor_control = _domestic_invoice(
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-C-2025-002",
        issued_at=date(2025, 3, 15),
        counterparty_tax_id="A58818501",
        counterparty_name="At Floor SL",
        base_total=Decimal("2483.52"),
        iva_total=Decimal("521.54"),
    )
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue((collectible, payable, floor_control)))
    resolver = _resolver(repository)
    m347_revision = _modelo_revision("347", "2011-2024")

    with bundled_indexed_authority().operation() as operation:
        m347_threshold = m347_threshold_decimal(
            resolve_m347_counterparty_annual_threshold(effective_date=date(2025, 12, 31), authority=operation),
        )
        m347_resolution = resolver.resolve(
            CalculationSourceContext(
                bucket_id=secure_profile.bucket_id,
                modelo="347",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=m347_revision,
            ),
        )

    assert floor_control.grand_total == m347_threshold
    assert collectible.grand_total + payable.grand_total > m347_threshold
    assert collectible.grand_total < m347_threshold
    assert payable.grand_total < m347_threshold
    # Neither the entregas nor the adquisiciones bucket of the first
    # counterparty exceeds the floor, and the second sits exactly on it, so
    # no declarado record exists and the type 1 totals over them are zero.
    assert m347_resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("0")
    assert m347_resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("0")
    assert m347_resolution.detail_rows == ()
    assert {item.source_ref for item in m347_resolution.provenance} == {
        f"collectible_invoice:{collectible.invoice_id}",
        f"payable_invoice:{payable.invoice_id}",
        f"collectible_invoice:{floor_control.invoice_id}",
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


def test_invoice_catalogue_source_resolver_refuses_payable_consignment_transfer_for_m349(
    secure_profile: TestRuntimeProfile,
) -> None:
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(
        build_invoice_catalogue(
            (
                _invoice(
                    bucket_id=secure_profile.bucket_id,
                    kind=InvoiceKind.RECEIVED,
                    invoice_number="DE-RECT-2026-001",
                    issued_at=date(2026, 3, 10),
                    counterparty_tax_id="DE222222222",
                    counterparty_name="Supplier GmbH",
                    counterparty_country="DE",
                    base_total=Decimal("100.00"),
                    iva_category=IvaCategory("intra_community_acquisition_reverse_charge"),
                    operation_type=IntracomOperationType.R,
                ),
            ),
        ),
    )
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    with pytest.raises(RegistryValidationError, match="source kind 'payable_invoice'"):
        _resolver(repository).resolve(
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
        iva_category=IvaCategory("intra_community_supply"),
    )
    repository.save(build_invoice_catalogue((declarable,)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    resolution = _resolver(repository).resolve(
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
        iva_category=IvaCategory("intra_community_supply"),
    )
    repository.save(build_invoice_catalogue((declarable,)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    with pytest.raises(Modelo349CountryPrefixContextError) as exc:
        _resolver(repository).resolve(
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


def test_invoice_catalogue_source_resolver_reports_a_degraded_catalogue_read() -> None:
    class DegradedReader:
        def load(self) -> InvoiceCatalogue:
            raise InvoiceSourcePersistenceError("invoice_catalogue_load")

    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    resolution = _resolver(DegradedReader()).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    reasons = tuple(d.reason for d in resolution.diagnostics)
    assert reasons, "a degraded catalogue read produced no diagnostic at all"
    assert set(reasons) == {"storage_degraded"}
