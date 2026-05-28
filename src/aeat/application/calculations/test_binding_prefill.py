"""Application tests for previous-filing binding prefill."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...core.errors import ERROR_REGISTRY, build_error_envelope
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
from ...tests.secure_sql import isolated_runtime_profile
from ..aggregation import CalculationSourceContext
from ._binding_prefill import (
    _selector_periods,
    _selector_year_delta,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from ._errors import BindingPrefillTypeError
from ._iva_compensation_history import IvaCompensationHistoryRepository, IvaCompensationPeriodState
from ._multi_year import PreviousFilingSourceResolver
from ._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


def test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
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
        repository = CalculationObservationRepository()
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
                bucket_id="operator",
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
        assert prefill.prefilled
        assert {item.source_kind for item in prefill.prefilled} == {"app_filing"}
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


def test_modelo_303_local_iva_recurrence_preserves_filed_history_source_kind(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        iva_history_repository = IvaCompensationHistoryRepository()
        iva_history_repository.save_period(
            IvaCompensationPeriodState(
                taxpayer_nif="12345678Z",
                filing_year=2025,
                period="4T",
                expediente_id="30320254T0000000000",
                status="presentada",
                presented_at=datetime(2026, 1, 20, 10, 0, tzinfo=UTC),
                prior_pending_amount=Decimal("100.00"),
                applied_amount=Decimal("25.00"),
                pending_for_later_amount=Decimal("75.00"),
                period_result_amount=Decimal("0.00"),
                final_result_amount=Decimal("0.00"),
                generated_amount=Decimal("0.00"),
                available_end_amount=Decimal("75.00"),
                source_observation_key="303:2025:4T:history-source",
            )
        )
        snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")

        recurrence, report = extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=CalculationObservationRepository(),
            iva_history_repository=iva_history_repository,
            captured_at=datetime(2026, 4, 1, 8, 0, tzinfo=UTC),
        )

    assert recurrence is not None
    assert recurrence.amount == Decimal("75.00")
    assert recurrence.source_kind == "aeat_sede_iva_compensation_history"
    assert recurrence.source_modelo == "303"
    assert recurrence.source_filing_year == 2025
    assert recurrence.source_periods == ("4T",)
    assert report.prefilled
    assert {item.source_kind for item in report.prefilled} == {"aeat_sede_iva_compensation_history"}


def test_binding_prefill_type_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_BINDING_PREFILL_TYPE" in ERROR_REGISTRY


def test_binding_prefill_type_error_round_trips_through_build_error_envelope() -> None:
    exc = BindingPrefillTypeError(
        "binding selector 'filing_year_delta' must be int|str, got list"
    )
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_BINDING_PREFILL_TYPE"
    assert envelope.retryable is False


def test_selector_year_delta_raises_binding_prefill_type_error_for_invalid_type() -> None:
    with pytest.raises(BindingPrefillTypeError, match="filing_year_delta"):
        _selector_year_delta([])


def test_selector_periods_raises_binding_prefill_type_error_for_invalid_type() -> None:
    with pytest.raises(BindingPrefillTypeError, match="source_periods"):
        _selector_periods(42)
