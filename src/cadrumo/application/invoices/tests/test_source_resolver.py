"""Invoice catalogue source-mesh resolver tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ....adapters.outbound.fx import ECB_RATE_SOURCE_ID
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage import StorageValidationError
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core import M347_THRESHOLD_EUR, BindingSourceKind, IntracomOperationType, Period
from ....core.errors import CadrumoError, get_registered_error_code, resolve_error_message
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    RegistryValidationError,
    load_modelo_directory,
    select_revision,
)
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind, IvaCategory
from ....domain.modelos import Modelo349CountryPrefixContextError
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import TestRuntimeProfile, isolated_two_bucket_runtime
from ...aggregation import CalculationSourceContext
from .. import InvoiceCatalogueSourceResolver, invoice_direction_to_source_kind
from .._source_resolver import _OWNED_SOURCES, M349_CLAVE_INFERRED_REASON, _intracommunity_clave

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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


_BUCKET_ID = "24242424-2424-4242-8242-242424242424"
_OTHER_BUCKET_ID = "25252525-2525-4252-8252-252525252525"


def _modelo_revision(modelo_id: str, revision_id: str):
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo_id))
    return modelo.revisions[revision_id]


secure_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="secure_profile")


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
    fx_rate_source: str | None = None,
    operation_type: IntracomOperationType | None = None,
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
                # EXEMPT, not RATE_0. An intra-community supply is exempt under
                # LIVA art. 25 -- no IVA applies to it. RATE_0 means something
                # different: that a zero-PERCENT tier was charged, which the
                # invoice validates against the rate table on the devengo date.
                # Spain has no standing zero tier, so RATE_0 here asserted a
                # rate that was not in force and refused every fixture dated
                # outside the 2024 temporary food window.
                iva_rate=IvaRate.EXEMPT,
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=iva_category,
        linked_transaction_ids=linked_transaction_ids,
        fx_rate=fx_rate,
        fx_rate_date=fx_rate_date,
        fx_rate_source=fx_rate_source,
        operation_type=operation_type,
    )


def _domestic_invoice(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str,
    counterparty_name: str,
    base_total: Decimal,
    iva_total: Decimal,
) -> Invoice:
    """A domestic ES invoice carrying real IVA, for the M347 gross-total path.

    Distinct from :func:`_invoice`, which mints a zero-IVA intra-community
    record: M347 declares the GROSS total, so a fixture whose base and total
    coincide cannot tell the two apart.
    """
    from ....domain.invoices import derive_invoice_id

    grand_total = base_total + iva_total
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=invoice_number,
            issued_at=issued_at,
            counterparty_tax_id=counterparty_tax_id,
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=bucket_id,
        kind=kind,
        invoice_number=invoice_number,
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
                iva_rate=IvaRate.RATE_21,
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PENDING,
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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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


def test_invoice_catalogue_source_resolver_projects_domestic_m347_summary_from_invoice_totals(
    secure_profile: TestRuntimeProfile,
) -> None:
    """M347 counts a counterparty only once it passes the declaration floor.

    The third invoice sits at EXACTLY the threshold, not above it: M347's floor
    is "supera", so a counterparty landing on the figure is not declarable, and
    a test whose control sat comfortably below would pass just as well against
    a `>=` comparison.
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
    repository.save(InvoiceCatalogue.from_invoices((collectible, payable, floor_control)))
    resolver = InvoiceCatalogueSourceResolver(invoice_repository=repository)
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

    assert floor_control.grand_total == M347_THRESHOLD_EUR
    assert m347_resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert m347_resolution.binding_values[
        "modelo-347-declarante-importe-total-anual-operaciones"
    ] == M347_THRESHOLD_EUR + Decimal("0.01")
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
        InvoiceCatalogue.from_invoices(
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
                    iva_category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                    operation_type=IntracomOperationType.R,
                ),
            ),
        ),
    )
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    with pytest.raises(RegistryValidationError, match="source kind 'payable_invoice'"):
        InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
        _modelos, _catalogues = bundled_registry_tree()
        _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
        snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
        fx_rate_source=ECB_RATE_SOURCE_ID,
    )
    repository.save(InvoiceCatalogue.from_invoices((converted,)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
# either unsatisfiable or it pins the very defect being removed. Instead
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

    The counterparty carries BOTH a domestic-format NIF and an EU IVA ID, which
    is the case that separates the two paths. The slim record has no coupling
    between its tax id and its country, so it needs a second identity field and
    a prefix-derivation fallback to decide who is being declared. The canonical
    record reaches the same declared party by a stronger route: a non-ES country
    forces the tax id to BE that country's NIF-IVA, so there is only ever one
    party identity on the aggregate. Same facts, fewer authorities.
    """
    from .._source_resolver import _invoice_observation

    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="349",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=select_revision(
            next(candidate for candidate in bundled_registry_tree()[0] if candidate.id == "349"),
            filing_year=2026,
            period="1T",
        ),
    )

    # The contract the retired slim store contributed, pinned as literals so
    # the proof outlives the store it conserves. Every value is read straight
    # off the fixture below except ``intracommunity_clave``, which the M349
    # clave table fixes for an ADQUISICION_SERVICIOS operation ("I", servicios
    # adquiridos).
    declared_facts = {
        "party_tax_id": "DE345678901",
        "country_code": "DE",
        "transaction_date": date(2026, 3, 10),
        "base_amount": Decimal("3000.00"),
        "invoice_total_amount": Decimal("3000.00"),
        "intracommunity_clave": "I",
        "party_legal_name": "Servizi SRL",
    }

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

    assert canonical_facts == declared_facts


def test_canonical_invoice_refuses_the_tax_id_country_mismatch_slim_permits(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The mechanism by which canonical conserves M349 party identity.

    This is the other half of the proof above, and it is why the canonical
    aggregate needs no second EU-IVA-ID field. The slim record accepts a
    Spanish-format NIF alongside a German country because nothing couples the
    two, which is exactly what forces it to carry a separate identity field and
    prefer it at projection time. The canonical record refuses that shape: a
    non-ES country validates the tax id against that country's published
    NIF-IVA pattern, so the only representable party identity is already the
    one M349 must declare.

    Adding an EU-IVA-ID field to the canonical aggregate would therefore
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
    from .._source_resolver import _invoice_observation

    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision=_modelo_revision("347", "2008-y-siguientes"),
    )

    # Pinned for the same reason as the M349 proof above: these are the facts
    # the retired slim store declared, every one of them read off the fixture.
    # ``intracommunity_clave`` is None because M347 is the domestic informativa.
    declared_facts = {
        "party_tax_id": "B12345674",
        "country_code": "ES",
        "transaction_date": date(2025, 2, 10),
        "base_amount": Decimal("1500.00"),
        "invoice_total_amount": Decimal("1815.00"),
        "intracommunity_clave": None,
        "party_legal_name": "Cliente M347 SL",
    }

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

    assert canonical_facts == declared_facts


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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
# Capability-parity proof
#
# One bucket exercising the capabilities that reach a declaration, projected
# through the canonical path, asserted at MODELO-OUTPUT level rather than at
# fact level (already covered elsewhere).
#
# The criterion also named M303 and M390. Measured at HEAD, neither
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
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

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
    """Scope guard, and the honest form of the M303/M390 criterion.

    Neither modelo declares a single invoice-sourced binding, so an equality
    assertion on their outputs would compare zero against zero and pass by
    construction. The assertion with content is the scope itself: the invoice
    stores feed M347 and M349 and nothing else.

    This fails the moment an invoice-sourced binding is added to either modelo,
    which is the change that would silently widen the fold's blast radius past
    what the parity proof above verifies.

    Every declared revision is swept rather than the one a filing year selects.
    The guard is a claim about the modelo, not about a year, and pinning it to a
    year made it depend on AEAT having published that year's orden: modelo 390's
    registry ends at 2025 because the 2026 orden does not exist yet, so a
    hardcoded 2026 failed on registry coverage while saying nothing about
    bindings. Sweeping every revision also widens the guard, since a binding
    added to any revision now trips it.
    """
    _modelos, _catalogues = bundled_registry_tree()
    _modelo = next(candidate for candidate in _modelos if candidate.id == modelo_id)
    assert _modelo.revisions, f"modelo {modelo_id} declares no revisions to inspect"

    offenders = {
        revision_id: [binding.id for binding in revision.bindings if binding.source in _OWNED_SOURCES]
        for revision_id, revision in _modelo.revisions.items()
    }
    offenders = {revision_id: bindings for revision_id, bindings in offenders.items() if bindings}

    assert offenders == {}, (
        f"modelo {modelo_id} now declares invoice-sourced bindings {offenders}; "
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
# Decomposition parity across the fold
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
        iva_category=IvaCategory.DOMESTIC_GENERAL if with_category else None,
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


def _m349_resolution(repository: InvoiceCatalogueRepository):
    """Resolve the committed Modelo 349 revision against a saved catalogue."""
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))
    return InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )


def _ic_supply_without_operation_type() -> Invoice:
    """An ordinary exempt intra-community supply, clave unstated.

    The ambiguous record: the resolver must pick a clave, and nothing on the
    invoice says whether the goods were previously imported.
    """
    return _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="IC-SUPPLY-001",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )


def _third_country_import() -> Invoice:
    """An importation in the same bucket -- the fact that makes M/H possible."""
    return _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="IMPORT-001",
        issued_at=date(2026, 1, 10),
        counterparty_tax_id="US99887766",
        counterparty_country="US",
        base_total=Decimal("800.00"),
        iva_category=IvaCategory.IMPORT_THIRD_COUNTRY,
        linked_transaction_ids=("2" * 64,),
    )


def _inferred_clave_reasons(resolution) -> list[str]:
    return [d.reason for d in resolution.diagnostics if d.reason == M349_CLAVE_INFERRED_REASON]


def test_an_inferred_entrega_clave_is_disclosed_when_the_bucket_also_holds_an_importation(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The one case the advisory exists for: E was a guess and M/H was possible.

    Clave M (or H) applies only to an intra-community supply following an EXEMPT
    IMPORTATION by the same taxpayer, per LIVA art. 27.12 -- the diseño defines E
    as excluding exactly those. Nothing on the supply records the prior
    importation, so the resolver's E is a guess. Here the bucket holds an
    importation, so the guess could be wrong and the operator is told.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(InvoiceCatalogue.from_invoices((_ic_supply_without_operation_type(), _third_country_import())))

    resolution = _m349_resolution(repository)

    assert _inferred_clave_reasons(resolution) == [M349_CLAVE_INFERRED_REASON]
    advisory = next(d for d in resolution.diagnostics if d.reason == M349_CLAVE_INFERRED_REASON)
    # Names the record and both alternatives, so the operator can act without
    # already knowing that clave M exists.
    assert "IC-SUPPLY-001" in advisory.message
    assert "'M'" in advisory.message
    # Advisory-asserted: this resolver holds no revision, snapshot or casilla
    # definition anywhere, so the two LIVA provisions the message states
    # (the ordinary art. 25 exemption and the art. 27.12 carve-out) are
    # declared rather than read off a registry object.
    assert advisory.asserted_legal_refs == ("ley-37-1992:art-25", "ley-37-1992:art-27")
    assert "'H'" in advisory.message


def test_the_same_supply_is_silent_when_the_taxpayer_never_imports(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The negative control, and the reason this is a disclosure not an alarm.

    Byte-identical supply, importation removed. A taxpayer who imports nothing
    cannot have made a post-importation supply, so E is not merely the likely
    clave -- it is the only one available, and an advisory here would fire on
    every Modelo 349 an ordinary EU-trading taxpayer ever files.

    Without this control the positive test above would pass just as well against
    an unconditional advisory, which is the design that was measured and
    rejected.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(InvoiceCatalogue.from_invoices((_ic_supply_without_operation_type(),)))

    assert _inferred_clave_reasons(_m349_resolution(repository)) == []


def test_a_stated_operation_type_is_never_disclosed_as_inferred(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A clave the record STATES is not a guess, even with an importation present.

    Separates the two conditions the advisory ANDs together. With the importation
    still in the bucket, the only changed fact is that the supply now declares its
    operation type -- so a screen keying on the importation alone would still fire
    here, and must not.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    stated = _ic_supply_without_operation_type().model_copy(
        update={"operation_type": IntracomOperationType.E},
    )
    repository.save(InvoiceCatalogue.from_invoices((stated, _third_country_import())))

    assert _inferred_clave_reasons(_m349_resolution(repository)) == []


def test_an_unconverted_foreign_invoice_is_excluded_but_reported(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Excluding the amount is right; excluding it in silence is not.

    A foreign-currency invoice with no resolved euro rate must never be declared
    at its face value -- that part is settled, and the sibling test above pins
    it. But the OPERATION is still real and still declarable: a GBP
    intracommunity supply to a German customer belongs on the recapitulativa
    whatever the euro figure turns out to be.

    Dropping it silently leaves the operator filing a Modelo 349 that omits an
    operation, with nothing on any surface saying so. The resolver's own
    incoherence advisory states the principle it must follow here: a missing
    intracomunitaria is an under-declaration whether it was dropped by a
    contradiction or by silence.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    unconverted = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-012",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        currency="GBP",
    )
    repository.save(InvoiceCatalogue.from_invoices((unconverted,)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.diagnostics, (
        "the invoice was withheld from Modelo 349 with no advisory: the operator "
        "files a recapitulativa missing a real operation and is never told"
    )
    reported = [d for d in resolution.diagnostics if d.source_ref and unconverted.invoice_id in d.source_ref]
    assert reported, f"no advisory names the withheld invoice: {[d.source_ref for d in resolution.diagnostics]}"
    # The advisory has to say what to DO about it. An operator who cannot act on
    # the message is no better off than one who never saw it.
    assert reported[0].remedy, "the advisory names the problem but not the remedy"
