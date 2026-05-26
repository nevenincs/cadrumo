"""Application tests for previous-filing binding prefill."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...core.config import override_settings
from ...core.resources import resources
from ...domain.calculations.registry import (
    CasillaObservation,
    IvaLedgerObservation,
    RegistryCalculationResult,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    resolve_bound_casilla_inputs,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_previous_filing_binding_values,
)
from ...domain.iva import IvaCategory, IvaFlowDirection, IvaRateKind
from ..aggregation import CalculationSourceContext
from ._binding_prefill import resolve_bindings_from_local_store
from ._multi_year import PreviousFilingSourceResolver
from ._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_BUCKET_ID = "operator"
_KEK = b"b" * 32
_DEK = b"p" * 32


@pytest.fixture(autouse=True)
def _isolated_secure_sql(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings:
        dispose_engine(settings)
        with activate_session(_session()):
            try:
                yield
            finally:
                dispose_engine(settings)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _observation(
    *,
    ledger_id: str,
    txn_date: date,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    iva: Decimal,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal("100.00"),
        iva_amount=iva,
    )


def _calculate_303_from_observations(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = resolve_bound_casilla_inputs(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": observations[-1].transaction_date},
    )


def _registry_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period=period,
        observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in result.values.items()),
    )


def test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations() -> None:
    quarterly_observations = {
        "1T": (
            _observation(ledger_id="q1-output", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),
            _observation(
                ledger_id="q1-input",
                txn_date=date(2025, 3, 1),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("42.00"),
            ),
        ),
        "2T": (
            _observation(ledger_id="q2-output", txn_date=date(2025, 5, 10), iva=Decimal("10.00")),
            _observation(
                ledger_id="q2-input",
                txn_date=date(2025, 6, 20),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("30.00"),
            ),
        ),
        "3T": (
            _observation(ledger_id="q3-output", txn_date=date(2025, 8, 12), iva=Decimal("50.00")),
        ),
        "4T": (
            _observation(ledger_id="q4-output", txn_date=date(2025, 11, 4), iva=Decimal("15.00")),
            _observation(
                ledger_id="q4-input",
                txn_date=date(2025, 12, 12),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("45.00"),
            ),
        ),
    }
    quarterly_results = {
        period: _calculate_303_from_observations(
            filing_year=2025,
            period=period,
            observations=observations,
        )
        for period, observations in quarterly_observations.items()
    }
    repository = CalculationObservationRepository(bucket_id=_BUCKET_ID)
    for period, result in quarterly_results.items():
        repository.save_observation(
            _registry_observation(filing_year=2025, period=period, result=result),
            source_kind="app_filing",
        )

    snapshot = resources().modelos.authority.snapshot("390", filing_year=2025, period="0A")
    prefill = resolve_bindings_from_local_store(snapshot, repository=repository)
    source_resolution = PreviousFilingSourceResolver(
        repository=repository,
        registry_snapshot=snapshot,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="390",
            filing_year=2025,
            period="0A",
            revision=snapshot.revision,
        )
    )
    previous_filing_values = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            _registry_observation(filing_year=2025, period=period, result=result)
            for period, result in quarterly_results.items()
        ),
        filing_year=2025,
        period="0A",
    )
    annual_ledger_values = resolve_ledger_iva_aggregation_binding_values(
        snapshot.revision,
        tuple(row for rows in quarterly_observations.values() for row in rows),
    )
    binding_values = {**annual_ledger_values, **prefill.binding_values}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_bound_casilla_inputs(snapshot.revision, binding_values),
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert prefill.binding_values == previous_filing_values
    assert source_resolution.binding_values == prefill.binding_values
    assert source_resolution.owned_sources == ("previous_filing",)
    assert source_resolution.provenance
    assert all(item.source_kind == "previous_filing" for item in source_resolution.provenance)
    assert {item.source_periods for item in prefill.prefilled} >= {
        ("1T", "2T", "3T", "4T"),
        ("4T",),
        ("1T", "2T", "3T"),
    }
    assert result.values["iva.anual.cuota-devengada-total"] == result.values[
        "iva.anual.reconciliacion.devengada-303"
    ]
    assert result.values["iva.anual.cuota-deducible-total"] == result.values[
        "iva.anual.reconciliacion.deducible-303"
    ]
    assert result.values["iva.anual.resultado-regimen-general"] == result.values[
        "iva.anual.reconciliacion.resultado-303"
    ]
