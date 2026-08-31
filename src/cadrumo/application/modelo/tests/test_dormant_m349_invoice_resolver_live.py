"""Live M349 invoice resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....tests.secure_sql import isolated_runtime_profile
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ..work_lifecycle import create_work_unit
from ._dormant_resolver_live_support import _T0, _T1, _revision, _seed_ready_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Chain 3 — M349 invoices (collectible_invoice): PROVEN LIVE
# ---------------------------------------------------------------------------

_M349_BUCKET = "34900000-0000-4000-8000-000000000013"
_M349_REVISION = "2020-y-siguientes"
_M349_YEAR = 2026
_M349_IMPORTE_CASILLA: CasillaId = validated_casilla_id("decl.importe-operaciones")
_M349_IMPORTE_BINDING = "iva-349-declarante-importe-operaciones"
_M349_OPERADORES_CASILLA: CasillaId = validated_casilla_id("decl.numero-operadores")

# Three DISTINCT non-equal ISSUED intra-community supply bases (clave E) to three
# distinct EU operators, all issued inside 1T (Jan-Mar). decl.importe-operaciones
# (base_sum) must fold the three bases; decl.numero-operadores (count_distinct)
# must count the three distinct operators.
_M349_INVOICES: tuple[tuple[str, str, str, date, Decimal], ...] = (
    # (invoice_number, counterparty_country, counterparty_tax_id, issued_at, base_total)
    ("F-2026-001", "DE", "DE123456789", date(2026, 1, 15), Decimal("1000.00")),
    ("F-2026-002", "FR", "FR12345678901", date(2026, 2, 10), Decimal("2500.50")),
    ("F-2026-003", "IT", "IT12345678901", date(2026, 3, 5), Decimal("740.25")),
)
_M349_EXPECTED_IMPORTE = Decimal("1000.00") + Decimal("2500.50") + Decimal("740.25")  # 4240.75
_M349_EXPECTED_OPERADORES = Decimal("3")


@pytest.fixture
def m349_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M349_BUCKET) as profile:
        _seed_ready_profile(profile.repository, bucket_id=_M349_BUCKET)
        yield profile.repository


def _intra_community_invoice(
    *,
    invoice_number: str,
    counterparty_country: str,
    counterparty_tax_id: str,
    issued_at: date,
    base_total: Decimal,
) -> Invoice:
    """Build one ISSUED INTRA_COMMUNITY_SUPPLY invoice (clave E) with a zero-rate line."""
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
        bucket_id=_M349_BUCKET,
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
                description="Intra-community supply",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.RATE_0,
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )


def test_m349_importe_operaciones_folds_seeded_invoices_on_live_calculate(
    m349_objects: SecureObjectRepository,
) -> None:
    """E2E: real seeded intra-community invoices fold into M349 on the live path.

    Seeds three DISTINCT ISSUED INTRA_COMMUNITY_SUPPLY invoices (clave E) in 1T,
    then runs the live bucket-aggregation calculate. casilla
    decl.importe-operaciones must equal the summed bases and
    decl.numero-operadores must count the three distinct operators — proving the
    enrolled InvoiceCatalogueSourceResolver folds the real encrypted invoice
    catalogue through to the bound casillas.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=m349_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m349_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M349_BUCKET, objects=m349_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m349_objects)

    invoices = tuple(
        _intra_community_invoice(
            invoice_number=number,
            counterparty_country=country,
            counterparty_tax_id=tax_id,
            issued_at=issued_at,
            base_total=base_total,
        )
        for number, country, tax_id, issued_at, base_total in _M349_INVOICES
    )
    invoice_repo.save(InvoiceCatalogue.from_invoices(invoices))

    # Non-vacuity: the casilla under test binds the invoice source, and the seeded
    # bases are distinct so a copy/contamination cannot satisfy the sum.
    revision = _revision("349", _M349_REVISION)
    importe_casilla = next(c for c in revision.casillas if c.id == _M349_IMPORTE_CASILLA)
    assert importe_casilla.binding == _M349_IMPORTE_BINDING
    assert any(str(b.source) == "collectible_invoice" and b.id == _M349_IMPORTE_BINDING for b in revision.bindings)
    assert len({base for *_, base in _M349_INVOICES}) == 3

    work_unit = create_work_unit(
        bucket_id=_M349_BUCKET,
        modelo="349",
        filing_year=_M349_YEAR,
        period=Period.from_year_and_code(_M349_YEAR, "1T"),
        revision_id=_M349_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    folded_importe = Decimal(result.revision.casilla_values[_M349_IMPORTE_CASILLA])
    assert folded_importe == _M349_EXPECTED_IMPORTE, (
        f"M349 {_M349_IMPORTE_CASILLA} must fold the three seeded invoice bases "
        f"(sum {_M349_EXPECTED_IMPORTE}); got {folded_importe}"
    )
    folded_operadores = Decimal(result.revision.casilla_values[_M349_OPERADORES_CASILLA])
    assert folded_operadores == _M349_EXPECTED_OPERADORES, (
        f"M349 {_M349_OPERADORES_CASILLA} must count the three distinct operators; got {folded_operadores}"
    )
    # The invoice source is CLAIMED (resolver enrolled): no unhandled advisory.
    assert not any(
        diag.source_kind in {"collectible_invoice", "payable_invoice"} and diag.reason == "unhandled_binding_source"
        for diag in result.source_diagnostics
    )


# ---------------------------------------------------------------------------
