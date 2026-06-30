"""Live M369 OSS/IOSS resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.calculations.registry import CasillaId
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
    derive_invoice_id,
)
from ....domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
)
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    CalculationSourceContext,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
)
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from ._dormant_resolver_live_support import _T0, _T1, _casilla_id, _revision, _seed_ready_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Chain 2 — M369 OSS/IOSS (ledger_oss_aggregation): live invoice projection
# ---------------------------------------------------------------------------

_M369_BUCKET = "36900000-0000-4000-8000-000000000013"
_M369_REVISION = "esquema-union"
_M369_YEAR = 2026

# Three DISTINCT OSS candidates whose persisted IVA matches the destination MS
# published rate (DE general 19%, FR general 20%): the resolver validates each
# against lookup_rate before aggregating, so the iva_amount must equal
# base * rate. Distinct bases -> distinct cuotas (19.00 / 40.00 / 57.00).
_M369_DE_SERVICES = OssIossLedgerCandidate(
    ledger_id="oss-de-services",
    transaction_date=date(2026, 2, 15),
    regime=OssIossRegime.UNION_SCHEME,
    destination_member_state=EUMemberState.DE,
    rate_kind=IvaRateKind.GENERAL,
    invoice_direction=InvoiceKind.ISSUED,
    transaction_kind=TransactionKind.OSS_UNION_SERVICES,
    base_amount=Decimal("100.00"),
    iva_amount=Decimal("19.00"),  # 100 * 19% (DE general)
)
_M369_FR_SERVICES = OssIossLedgerCandidate(
    ledger_id="oss-fr-services",
    transaction_date=date(2026, 2, 16),
    regime=OssIossRegime.UNION_SCHEME,
    destination_member_state=EUMemberState.FR,
    rate_kind=IvaRateKind.GENERAL,
    invoice_direction=InvoiceKind.ISSUED,
    transaction_kind=TransactionKind.OSS_UNION_SERVICES,
    base_amount=Decimal("200.00"),
    iva_amount=Decimal("40.00"),  # 200 * 20% (FR general)
)
_M369_DE_GOODS = OssIossLedgerCandidate(
    ledger_id="oss-de-goods",
    transaction_date=date(2026, 2, 17),
    regime=OssIossRegime.UNION_SCHEME,
    destination_member_state=EUMemberState.DE,
    rate_kind=IvaRateKind.GENERAL,
    invoice_direction=InvoiceKind.ISSUED,
    transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
    base_amount=Decimal("300.00"),
    iva_amount=Decimal("57.00"),  # 300 * 19% (DE general)
)
_M369_DE_SERVICES_BINDING = "modelo-369-union-de-services-21pct"
_M369_FR_SERVICES_BINDING = "modelo-369-union-fr-services-21pct"
_M369_DE_GOODS_BINDING = "modelo-369-union-de-goods-distance-21pct"
_M369_CUOTA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.union.cuota-total")
# Casilla bound to the DE-services OSS binding (used by the carve-out test).
_M369_DE_SERVICES_BINDING_CASILLA: CasillaId = _casilla_id("iva.union.de.services-cuota")
_M369_FR_SERVICES_BINDING_CASILLA: CasillaId = _casilla_id("iva.union.fr.services-cuota")
_M369_DE_GOODS_BINDING_CASILLA: CasillaId = _casilla_id("iva.union.de.goods-distance-cuota")


@pytest.fixture
def m369_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M369_BUCKET) as profile:
        _seed_ready_profile(profile.repository, bucket_id=_M369_BUCKET)
        yield profile.repository


def test_m369_oss_resolver_folds_real_candidates_at_mesh_boundary() -> None:
    """The OSS resolver folds REAL candidates into the bound casilla cuotas.

    This proves the resolver + binding chain is sound: three DISTINCT validated
    OSS candidates fold into their three distinct binding cuotas (DE services 19,
    FR services 40, DE goods 57). The fold is NON-tautological — distinct seeds,
    asserted as the per-binding sum of the validated candidate cuotas, never a
    re-evaluation of a registry formula. The gap proven in the companion test
    below is solely the LIVE-PATH candidate source, not this fold.
    """
    revision = _revision("369", _M369_REVISION)
    candidates = (_M369_DE_SERVICES, _M369_FR_SERVICES, _M369_DE_GOODS)

    # Resolver path (what the live mesh WOULD fold if it had candidates).
    resolution = OssIossLedgerSourceResolver(candidates=candidates).resolve(
        CalculationSourceContext(
            bucket_id=_M369_BUCKET,
            modelo="369",
            filing_year=_M369_YEAR,
            period=Period.from_year_and_code(_M369_YEAR, "1T"),
            revision=revision,
        ),
    )
    assert resolution.binding_values[_M369_DE_SERVICES_BINDING] == Decimal("19.00")
    assert resolution.binding_values[_M369_FR_SERVICES_BINDING] == Decimal("40.00")
    assert resolution.binding_values[_M369_DE_GOODS_BINDING] == Decimal("57.00")
    # Cross-check the registry aggregation wrapper agrees with the resolver.
    assert aggregate_oss_ioss_bindings(revision, candidates) == dict(resolution.binding_values)
    # The source is claimed; the resolver raises nothing and emits no diagnostics.
    assert resolution.diagnostics == ()
    assert "ledger_oss_aggregation" in resolution.owned_sources


def _m369_invoice(
    *,
    invoice_number: str,
    issued_at: date,
    counterparty_name: str,
    counterparty_tax_id: str,
    counterparty_country: str,
    transaction_kind: TransactionKind,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> Invoice:
    line = InvoiceLine(
        description=f"OSS supply {invoice_number}",
        quantity=Decimal("1"),
        unit_price=base_amount,
        subtotal=base_amount,
        iva_rate=IvaRate.RATE_21,
        oss_rate_kind=IvaRateKind.GENERAL,
        iva_amount=iva_amount,
    )
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency="EUR",
        grand_total=base_amount + iva_amount,
    )
    return Invoice(
        invoice_id=invoice_id,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        base_total=base_amount,
        iva_total=iva_amount,
        grand_total=base_amount + iva_amount,
        currency="EUR",
        lines=(line,),
        payment_status=PaymentStatus.PAID,
        oss_ioss_regime=OssIossRegime.UNION_SCHEME,
        oss_transaction_kind=transaction_kind,
    )


def test_m369_live_path_folds_oss_invoices_not_no_live_source_advisory(
    m369_objects: SecureObjectRepository,
) -> None:
    """Live M369 calculate projects real OSS-tagged invoices into cuotas."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        InvoiceCatalogue.from_invoices(
            (
                _m369_invoice(
                    invoice_number="OSS-DE-SERV-001",
                    issued_at=date(2026, 2, 15),
                    counterparty_name="DE Consumer",
                    counterparty_tax_id="DE123456789",
                    counterparty_country="DE",
                    transaction_kind=TransactionKind.OSS_UNION_SERVICES,
                    base_amount=Decimal("100.00"),
                    iva_amount=Decimal("19.00"),
                ),
                _m369_invoice(
                    invoice_number="OSS-FR-SERV-001",
                    issued_at=date(2026, 2, 16),
                    counterparty_name="FR Consumer",
                    counterparty_tax_id="FR12345678901",
                    counterparty_country="FR",
                    transaction_kind=TransactionKind.OSS_UNION_SERVICES,
                    base_amount=Decimal("200.00"),
                    iva_amount=Decimal("40.00"),
                ),
                _m369_invoice(
                    invoice_number="OSS-DE-GOODS-001",
                    issued_at=date(2026, 2, 17),
                    counterparty_name="DE Consumer Goods",
                    counterparty_tax_id="DE987654321",
                    counterparty_country="DE",
                    transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
                    base_amount=Decimal("300.00"),
                    iva_amount=Decimal("57.00"),
                ),
            ),
        ),
    )

    work_unit = create_work_unit(
        bucket_id=_M369_BUCKET,
        modelo="369",
        filing_year=_M369_YEAR,
        period=Period.from_year_and_code(_M369_YEAR, "1T"),
        revision_id=_M369_REVISION,
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
    casilla_values = result.revision.casilla_values
    component_cuotas = (
        Decimal(casilla_values[_M369_DE_SERVICES_BINDING_CASILLA]),
        Decimal(casilla_values[_M369_FR_SERVICES_BINDING_CASILLA]),
        Decimal(casilla_values[_M369_DE_GOODS_BINDING_CASILLA]),
    )
    assert component_cuotas == (Decimal("19.00"), Decimal("40.00"), Decimal("57.00"))
    assert Decimal(casilla_values[_M369_CUOTA_TOTAL_CASILLA]) == sum(component_cuotas, Decimal("0"))
    assert not any(
        diag.source_kind == "ledger_oss_aggregation" and diag.reason == "oss_no_live_source"
        for diag in result.source_diagnostics
    )
    assert not any(
        diag.source_kind == "ledger_oss_aggregation" and diag.reason == "unhandled_binding_source"
        for diag in result.source_diagnostics
    )


# ---------------------------------------------------------------------------
