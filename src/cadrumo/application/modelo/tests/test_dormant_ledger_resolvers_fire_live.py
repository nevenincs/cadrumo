"""Live M130 dormant-ledger resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from ..work_lifecycle import create_work_unit
from ._dormant_resolver_live_support import _T0, _T1, _revision, _seed_ready_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Chain 1 — M130 income (ledger_renta_income_aggregation): PROVEN LIVE
# ---------------------------------------------------------------------------

_M130_BUCKET = "13000000-0000-4000-8000-000000000013"
_M130_REVISION = "2019-y-siguientes"
_M130_YEAR = 2026
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_M130_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = validated_casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")

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

# Manual casillas the M130 engine consumes downstream of casilla 01 (the
# various retención / deducción slots). Supplied as zero through the caller
# channel — they are manual_input (not source-owned), so the override is allowed.
# Casilla 02 (Gastos) is now bound to ledger_renta_gastos_pago_fraccionado_aggregation (a locked
# source), so it is NOT supplied here: with no OUTGOING transactions seeded the
# gasto resolver returns 0, leaving rendimiento neto == ingresos so a wrong
# income fold would still surface.
_M130_MANUAL_INPUTS: dict[CasillaId, Decimal] = {
    _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
    _M130_RETENCIONES_CASILLA: Decimal("0"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}


@pytest.fixture
def m130_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M130_BUCKET) as profile:
        _seed_ready_profile(profile.repository, bucket_id=_M130_BUCKET)
        yield profile.repository


def _income_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = None,
) -> Transaction:
    """Build one ACTIVE, INCOMING, BUSINESS, EUR actividad-económica receipt."""
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
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
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
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
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_M130_PRIOR_YEAR,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_M130_PRIOR_YEAR,
                    period="0A",
                    casilla_values={
                        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _M130_PRIOR_YEAR_NET_INCOME,
                        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                    },
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
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
        period=Period.from_year_and_code(_M130_YEAR, "1T"),
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


def test_m130_casilla_06_prefills_from_net_paid_professional_invoice_on_live_calculate(
    m130_objects: SecureObjectRepository,
) -> None:
    """E2E: net-paid professional invoice fills M130 casilla 06 without caller input."""
    wu_repo = WorkUnitCatalogueRepository(objects=m130_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m130_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M130_BUCKET, objects=m130_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m130_objects)

    tx = _income_transaction(
        "m130-net-paid",
        value_date=date(2026, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
        irpf_category="actividad_economica",
    )
    tx_repo.save(TransactionCatalogue.from_transactions((tx,)))

    obs_repo = CalculationObservationRepository(objects=m130_objects)
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_M130_PRIOR_YEAR,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_M130_PRIOR_YEAR,
                    period="0A",
                    casilla_values={
                        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _M130_PRIOR_YEAR_NET_INCOME,
                        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                    },
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )

    revision = _revision("130", _M130_REVISION)
    assert any(
        str(b.source) == "ledger_renta_income_aggregation" and b.id == _M130_RETENCIONES_BINDING
        for b in revision.bindings
    )

    work_unit = create_work_unit(
        bucket_id=_M130_BUCKET,
        modelo="130",
        filing_year=_M130_YEAR,
        period=Period.from_year_and_code(_M130_YEAR, "1T"),
        revision_id=_M130_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    manual_inputs_without_c06 = {
        casilla_id: value
        for casilla_id, value in _M130_MANUAL_INPUTS.items()
        if casilla_id != _M130_RETENCIONES_CASILLA
    }
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        casilla_inputs=manual_inputs_without_c06,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert Decimal(result.revision.casilla_values[_M130_INGRESOS_CASILLA]) == Decimal("2000.00")
    assert Decimal(result.revision.casilla_values[_M130_RETENCIONES_CASILLA]) == Decimal("300.00")
    assert set(result.revision.source_transaction_ids) >= {tx.transaction_id}


# ---------------------------------------------------------------------------
