"""Dormant ledger resolvers fold REAL seeded data through to a casilla.

An earlier change enrolled three previously-dormant ledger source resolvers in the live
merge_source_resolutions mesh and proved each *claims its source kind* with EMPTY
data (the resolver appears in owned_sources, no unhandled_binding_source advisory
names it). Those tests are necessary but not sufficient: an enrolled resolver that
reads nothing still produces no casilla value.

This module closes that gap end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`): for
each resolver we SEED real source substrate with DISTINCT non-equal known amounts,
calculate live over the real encrypted-SQLite bucket, and assert the bound casilla
equals the AGGREGATION (sum) of the seeds. A silent blank, a single-seed copy, or a
cross-source contamination would red the assertion.

Chains:

* M130 actividad-económica income (``ledger_renta_income_aggregation``,
  :class:`LedgerRentaIncomeAggregationSourceResolver`): seed real INCOMING
  business EUR transactions, calculate M130/1T live, assert casilla ``01``
  (Ingresos, bound to ``modelo-130-actividad-economica-ingresos-cumulative``,
  ``gross_income_sum``) equals the seeded income sum. PROVEN LIVE.

* M349 intracomunitaria operations (``collectible_invoice``,
  :class:`InvoiceCatalogueSourceResolver`): seed real ISSUED
  INTRA_COMMUNITY_SUPPLY invoices (clave E), calculate M349/1T live, assert
  casilla ``decl.importe-operaciones`` (bound to
  ``iva-349-declarante-importe-operaciones``, ``base_sum``) equals the seeded
  base-total sum and ``decl.numero-operadores`` equals the distinct operator
  count. PROVEN LIVE.

* M369 OSS/IOSS (``ledger_oss_aggregation``, :class:`OssIossLedgerSourceResolver`):
  STOPGAP. The resolver folds real ``OssIossLedgerCandidate`` substrate correctly
  (proven here at the resolver-mesh boundary), but the live calculate path
  hard-wires ``OssIossLedgerSourceResolver(candidates=())`` — there is NO
  ledger/transaction -> OSS-candidate projection anywhere in the codebase
  (``OssIossLedgerCandidate`` is only constructed in tests and the Sheets
  calc-sync caller). The projection is INFEASIBLE from any current live source:
  neither the :class:`~aeat.domain.invoices.Invoice` / ``InvoiceLine`` model nor
  the :class:`~aeat.domain.transactions.Transaction` model carries the OSS
  ``regime`` axis (union / import / exterior) or the goods-vs-services
  ``transaction_kind`` axis (``oss_union_services`` vs
  ``oss_union_goods_distance_sale`` / ``oss_union_goods_interface_facilitated``)
  the binding selectors require, and ``IvaCategory`` has no OSS member at all (its
  ``INTRA_COMMUNITY_SUPPLY`` is the B2B clave-E M349 path, a different regime).
  Rather than let every OSS cuota resolve to a SILENT claimed-zero, the resolver
  now surfaces a non-blocking ``oss_no_live_source`` advisory per declared OSS
  binding (W04.P12.S33) so an operator with OSS sales is told the cuotas are not
  auto-computed and must be supplied manually. The advisory proof and the proven
  resolver fold are both pinned below.

Anti-tautological + real-adapter (no-tautological-calculation-tests,
aeat-quality-gates): every seed set uses DISTINCT non-equal known values; each
assertion is ``casilla == sum(distinct seeds)``, a fold-WIRING invariant — no
registry formula is re-evaluated. Real encrypted-SQLite via
``isolated_runtime_profile`` -> :class:`SecureObjectRepository` +
:class:`EphemeralMasterKeyProvider`, real catalogue repositories, real registry
authority, real calculation engine, real source mesh. No mocks/stubs/skips/xfail.

Also pins the five deferred detalle source kinds: each emits the standing
``unhandled_binding_source`` advisory rather than a silent blank. withholding /
atribucion_member / foreign_asset are covered in
``test_source_boundary_and_enrollment``; related_party_operation (M232) and
refund_operation (M360) are pinned here so all five are covered.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, ModeloRevision, RegistryModeloObservation
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
    IvaCategory,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
)
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    CalculationSourceContext,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
)
from ...calculations._observations_repository import CalculationObservationRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)


def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_def = next(item for item in resources().modelos.all() if item.id == modelo)
    return modelo_def.revisions[revision_id]


# ---------------------------------------------------------------------------
# Chain 1 — M130 income (ledger_renta_income_aggregation): PROVEN LIVE
# ---------------------------------------------------------------------------

_M130_BUCKET = "bucket-m130-income-fold"
_M130_REVISION = "2019-y-siguientes"
_M130_YEAR = 2026
_M130_INGRESOS_CASILLA = "01"
_M130_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"

# Three DISTINCT non-equal income receipts inside the M130 1T cumulative window
# (Jan 1 - Mar 31). Distinct values make the fold unmistakable: a single-receipt
# copy or a coincidental sum cannot satisfy the casilla-01 == sum assertion.
_M130_INCOME_BY_ID: dict[str, tuple[date, Decimal]] = {
    "m130-jan": (date(2026, 1, 20), Decimal("1200.00")),
    "m130-feb": (date(2026, 2, 14), Decimal("850.50")),
    "m130-mar": (date(2026, 3, 31), Decimal("433.25")),
}
_M130_EXPECTED_INGRESOS = Decimal("1200.00") + Decimal("850.50") + Decimal("433.25")  # 2483.75

# casilla 13 (minoración) reads binding ``irpf.previous_year_economic_activity_net_income``
# (source = previous_filing, M100 prior-year net income). On a fresh bucket the
# engine RAISES if that prior-year value is absent, so we seed a real prior-year
# (2025) M100 observation; the enrolled PreviousFilingSourceResolver carries it.
# This is upstream substrate, NOT the casilla under test — €8000 only steers the
# minoración band; it does not contribute to casilla 01.
_M130_PRIOR_YEAR = 2025
_M130_PRIOR_YEAR_NET_INCOME = Decimal("8000")

# Manual casillas the M130 engine consumes downstream of casilla 01 (Gastos and
# the various retención / deducción slots). Supplied as zero through the caller
# channel — they are manual_input (not source-owned), so the override is allowed.
# Gastos = 0 leaves rendimiento neto == ingresos so a wrong fold would surface.
_M130_MANUAL_INPUTS: dict[str, Decimal] = {
    "02": Decimal("0"),
    "05": Decimal("0"),
    "06": Decimal("0"),
    "08": Decimal("0"),
    "10": Decimal("0"),
    "16": Decimal("0"),
    "18": Decimal("0"),
}


@pytest.fixture
def m130_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M130_BUCKET) as profile:
        yield profile.repository


def _income_transaction(provider_id: str, *, value_date: date, amount: Decimal) -> Transaction:
    """Build one ACTIVE, INCOMING, BUSINESS, EUR actividad-económica receipt."""
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id=provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"income {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def test_m130_casilla_01_folds_seeded_ledger_income_on_live_calculate(
    m130_objects: SecureObjectRepository,
) -> None:
    """E2E: real seeded income transactions fold into M130 casilla 01 on the live path.

    Seeds three DISTINCT INCOMING business EUR receipts in the 1T cumulative
    window and a real prior-year M100 net income (so the minoración binding
    resolves), then runs the live bucket-aggregation calculate. Casilla 01 must
    equal the summed seeded income — proving the enrolled
    LedgerRentaIncomeAggregationSourceResolver folds real ledger substrate
    through to the bound casilla, not merely claims its source kind.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=m130_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m130_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M130_BUCKET, objects=m130_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m130_objects)

    transactions = tuple(
        _income_transaction(pid, value_date=value_date, amount=amount)
        for pid, (value_date, amount) in _M130_INCOME_BY_ID.items()
    )
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))

    # Real prior-year M100 net-income observation (upstream minoración substrate).
    obs_repo = CalculationObservationRepository(objects=m130_objects)
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo="100",
            filing_year=_M130_PRIOR_YEAR,
            period="0A",
            observations=(
                CasillaObservation(casilla_id="0224", value=_M130_PRIOR_YEAR_NET_INCOME),
                CasillaObservation(casilla_id="1479", value=Decimal("0")),
                CasillaObservation(casilla_id="1553", value=Decimal("0")),
                CasillaObservation(casilla_id="1577", value=Decimal("0")),
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )

    # Non-vacuity: casilla 01 binds the income aggregation source under test, and
    # the seeds are distinct (so a copy/contamination cannot satisfy the sum).
    revision = _revision("130", _M130_REVISION)
    casilla_01 = next(c for c in revision.casillas if c.id == _M130_INGRESOS_CASILLA)
    assert casilla_01.binding == _M130_INGRESOS_BINDING
    assert any(
        str(b.source) == "ledger_renta_income_aggregation" and b.id == _M130_INGRESOS_BINDING for b in revision.bindings
    )
    assert len({amount for _, amount in _M130_INCOME_BY_ID.values()}) == 3

    work_unit = create_work_unit(
        bucket_id=_M130_BUCKET,
        modelo="130",
        filing_year=_M130_YEAR,
        period="1T",
        revision_id=_M130_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        casilla_inputs=_M130_MANUAL_INPUTS,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    folded = Decimal(result.revision.casilla_values[_M130_INGRESOS_CASILLA])
    assert folded == _M130_EXPECTED_INGRESOS, (
        f"M130 casilla 01 must fold the three seeded income receipts (sum {_M130_EXPECTED_INGRESOS}); got {folded}"
    )
    # The income source is CLAIMED (resolver enrolled): no unhandled advisory.
    assert not any(
        diag.source_kind == "ledger_renta_income_aggregation" and diag.reason == "unhandled_binding_source"
        for diag in result.source_diagnostics
    )
    # The seeded transactions are recorded as contributing evidence on the revision.
    assert set(result.revision.source_transaction_ids) >= {tx.transaction_id for tx in transactions}


# ---------------------------------------------------------------------------
# Chain 3 — M349 invoices (collectible_invoice): PROVEN LIVE
# ---------------------------------------------------------------------------

_M349_BUCKET = "bucket-m349-invoice-fold"
_M349_REVISION = "2020-y-siguientes"
_M349_YEAR = 2026
_M349_IMPORTE_CASILLA = "decl.importe-operaciones"
_M349_IMPORTE_BINDING = "iva-349-declarante-importe-operaciones"
_M349_OPERADORES_CASILLA = "decl.numero-operadores"

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
        period="1T",
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
# Chain 2 — M369 OSS/IOSS (ledger_oss_aggregation): STOPGAP advisory (no live source)
# ---------------------------------------------------------------------------

_M369_BUCKET = "bucket-m369-oss-fold"
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
_M369_CUOTA_TOTAL_CASILLA = "iva.union.cuota-total"
# Casilla bound to the DE-services OSS binding (used by the carve-out test).
_M369_DE_SERVICES_BINDING_CASILLA = "iva.union.de.services-cuota"


@pytest.fixture
def m369_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M369_BUCKET) as profile:
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
            period="1T",
            revision=revision,
        )
    )
    assert resolution.binding_values[_M369_DE_SERVICES_BINDING] == Decimal("19.00")
    assert resolution.binding_values[_M369_FR_SERVICES_BINDING] == Decimal("40.00")
    assert resolution.binding_values[_M369_DE_GOODS_BINDING] == Decimal("57.00")
    # Cross-check the registry aggregation wrapper agrees with the resolver.
    assert aggregate_oss_ioss_bindings(revision, candidates) == dict(resolution.binding_values)
    # The source is claimed; the resolver raises nothing and emits no diagnostics.
    assert resolution.diagnostics == ()
    assert "ledger_oss_aggregation" in resolution.owned_sources


def test_m369_live_path_surfaces_oss_no_live_source_advisory_not_silent_zero(
    m369_objects: SecureObjectRepository,
) -> None:
    """STOPGAP: a live M369 calculate surfaces the OSS no-live-source advisory.

    ``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` hard-wires
    ``OssIossLedgerSourceResolver(candidates=())`` because no bucket substrate can
    be projected into an ``OssIossLedgerCandidate`` (neither the invoice nor the
    transaction model carries the OSS ``regime`` or goods/services
    ``transaction_kind`` axis the selectors require; ``IvaCategory`` has no OSS
    member). The OSS cuotas therefore still resolve to zero on the live path — but
    the resolver now surfaces a non-blocking ``oss_no_live_source`` advisory per
    declared OSS binding so the zero is NOT silent: an operator with OSS sales is
    told the cuotas are not auto-computed and must be supplied manually
    (no-silent-under-declaration; parity with the deferred-detalle-kinds advisory).

    This is the stopgap pending an invoice/transaction-model OSS axis that would
    make the substrate projection feasible. The resolver fold itself is already
    sound (companion test above) — only the live-path candidate source is absent.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)

    work_unit = create_work_unit(
        bucket_id=_M369_BUCKET,
        modelo="369",
        filing_year=_M369_YEAR,
        period="1T",
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
    # The OSS cuotas are still zero on the live path — nothing folds because no
    # candidate projection exists. The STOPGAP makes that zero non-silent.
    assert Decimal(result.revision.casilla_values[_M369_DE_SERVICES_BINDING_CASILLA]) == Decimal("0")
    assert Decimal(result.revision.casilla_values[_M369_CUOTA_TOTAL_CASILLA]) == Decimal("0")

    # The stopgap advisory fires: one oss_no_live_source diagnostic per declared
    # OSS binding (the three esquema-union bindings), each naming its binding id.
    oss_advisories = [
        diag
        for diag in result.source_diagnostics
        if diag.source_kind == "ledger_oss_aggregation" and diag.reason == "oss_no_live_source"
    ]
    advised_bindings = {diag.binding_id for diag in oss_advisories}
    assert advised_bindings == {
        _M369_DE_SERVICES_BINDING,
        _M369_FR_SERVICES_BINDING,
        _M369_DE_GOODS_BINDING,
    }, f"expected an oss_no_live_source advisory per OSS binding; got {advised_bindings}"
    assert all(diag.message for diag in oss_advisories)
    # The source is OWNED (resolver enrolled) — the silent-zero failure mode would
    # be the unhandled_binding_source advisory NOT firing AND no oss_no_live_source
    # advisory either; assert the boundary advisory is not the one that fired.
    assert not any(
        diag.source_kind == "ledger_oss_aggregation" and diag.reason == "unhandled_binding_source"
        for diag in result.source_diagnostics
    )


# ---------------------------------------------------------------------------
# Deferred detalle kinds — related_party_operation (M232) + refund_operation (M360)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("modelo", "revision_id", "deferred_kind"),
    [
        ("232", "2018-y-siguientes", "related_party_operation"),
        ("360", "2010-y-siguientes", "refund_operation"),
    ],
)
def test_deferred_detalle_kinds_emit_unhandled_advisory_not_silent_blank(
    modelo: str,
    revision_id: str,
    deferred_kind: str,
) -> None:
    """The remaining two deferred detalle kinds surface the unhandled-source advisory.

    related_party_operation (M232 operaciones vinculadas) and refund_operation
    (M360 IVA refund operations) are Sheets-pull-only row-producer source kinds
    with no live resolver; both must emit an ``unhandled_binding_source`` advisory
    rather than a silent blank, and must NOT sit on the manual_sources allowlist.

    Asserted via the ``collect_unhandled_source_diagnostics`` boundary (mirroring
    ``test_s27_withholding_deferred_advisory_fires``): these revisions carry
    row-producer relation operands and the full calculate path is orthogonal to
    the advisory contract under test. With withholding / atribucion_member /
    foreign_asset pinned in test_source_boundary_and_enrollment, this covers the
    full set of five DEFERRED_SOURCE_KINDS.
    """
    from ...aggregation import DEFERRED_SOURCE_KINDS, collect_unhandled_source_diagnostics

    revision = _revision(modelo, revision_id)
    assert any(str(b.source) == deferred_kind for b in revision.bindings), (
        f"M{modelo} {revision_id} must declare {deferred_kind} bindings for this test to be non-vacuous"
    )
    handled = frozenset({"relation_prefill", "profile", "borrador", "iva_wallet_decision"})
    unhandled = collect_unhandled_source_diagnostics(
        revision, handled_sources=handled, manual_sources=frozenset({"manual_input"})
    )
    advisories = [d for d in unhandled if d.source_kind == deferred_kind and d.reason == "unhandled_binding_source"]
    assert advisories, (
        f"expected 'unhandled_binding_source' advisory for deferred kind {deferred_kind!r} on M{modelo}; "
        f"got none. unhandled={unhandled}"
    )
    assert all(d.binding_id for d in advisories)
    assert deferred_kind not in frozenset({"manual_input"})
    assert deferred_kind in DEFERRED_SOURCE_KINDS
