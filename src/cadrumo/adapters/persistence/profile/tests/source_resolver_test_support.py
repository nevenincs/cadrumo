"""Shared fixtures and builders for invoice source resolver tests."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.source_resolver import InvoiceCatalogueSourceResolver
from cadrumo.application.invoices.source_resolver_ports import InvoiceSourceCatalogueReader, InvoiceSourceResolverPorts
from cadrumo.core.aggregation import IntracomOperationType, ThirdPartyDeclarationRole
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.modelos.row_models import Modelo349OperadorRow
from cadrumo.domain.user_profile.values import UserProfileFact

from .published_authority_support import published_authority_operation

_BUCKET_ID = "24242424-2424-4242-8242-242424242424"

_OTHER_BUCKET_ID = "25252525-2525-4252-8252-252525252525"


def _modelo_revision(modelo_id: str, revision_id: str):
    return published_authority_operation().revision_with_export_layouts(modelo_id, revision_id)


secure_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="secure_profile")


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Run every test inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


def _resolver(reader: InvoiceSourceCatalogueReader) -> InvoiceCatalogueSourceResolver:
    return InvoiceCatalogueSourceResolver(
        ports=InvoiceSourceResolverPorts(catalogue_reader=reader),
    )


class _InMemoryCatalogueReader:
    """Adapter-test-owned reader fake for public resolver projections."""

    def __init__(self, invoices: Sequence[Invoice]) -> None:
        self._catalogue = build_invoice_catalogue(tuple(invoices))

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


def _public_resolution(
    invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
):
    """Resolve local fixture data through the public application seam."""
    return _resolver(_InMemoryCatalogueReader(invoices)).resolve(context)


def _public_m349_claves(invoices: Sequence[Invoice]) -> tuple[str, ...]:
    """Return M349 claves emitted by the resolver's public detail-row seam."""
    resolution = _public_resolution(
        invoices,
        context=CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=_modelo_revision("349", "2020-y-siguientes"),
        ),
    )
    return tuple(row.clave_operacion for row in resolution.detail_rows if isinstance(row, Modelo349OperadorRow))


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
    from cadrumo.domain.invoices.models import derive_invoice_id

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
                iva_rate=IvaRate.from_registry("EXEMPT"),
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
    from cadrumo.domain.invoices.models import derive_invoice_id

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
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PENDING,
    )


def _public_administration_profile_facts() -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="identity.tax_id", value="Q1234567D"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(
            path="taxpayer_type.declaration_roles",
            value=ThirdPartyDeclarationRole.from_registry("public_administration_entity").value,
        ),
    )


def _statutory_information_duty_profile_facts() -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="identity.tax_id", value="B12345674"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(
            path="taxpayer_type.declaration_roles",
            value=ThirdPartyDeclarationRole.from_registry("statutory_information_duty_entity").value,
        ),
    )


def _clave_probe_invoice(kind: InvoiceKind, category: IvaCategory) -> Invoice:
    """Build a minimal exempt-shaped invoice carrying a category and no operation_type."""
    base = Decimal("1000.00")
    line = InvoiceLine(
        description="Servicio intracomunitario",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("EXEMPT"),
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


def _unsettled_reading_refs(resolution) -> list[str | None]:
    return sorted(
        (item.source_ref for item in resolution.diagnostics if item.reason == "unsettled_legal_reading"),
        key=str,
    )


def _m347_2026_context(bucket_id: str) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
