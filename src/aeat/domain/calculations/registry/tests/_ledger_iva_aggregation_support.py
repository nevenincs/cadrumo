"""Shared helpers for ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

from .....application.calculations import resolve_iva_compensation_annual_partition_binding_values
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import resources
from ....iva import IvaCategory, IvaFlowDirection, IvaRateKind
from .. import (
    CasillaId,
    DataBindingDefinition,
    IvaLedgerObservation,
    ModeloRevision,
    RegistryCalculationResult,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_bound_inputs_by_casilla_id,
    resolve_ledger_iva_aggregation_binding_values,
    validated_casilla_id,
)
from .._binding_selector_utils import selector_as_dict
from .._relations import resolve_relation_values_from_observations


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"ledger IVA aggregation fixture casilla key {value!r} is not a CasillaId") from exc


_M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.interior.devengado",
)
_M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.interior.deducible",
)
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.intracomunitaria.devengado",
)
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.intracomunitaria.deducible",
)
_M303_SOPORTADO_IMPORTACIONES_CASILLA: CasillaId = _casilla_id("iva.soportado.importaciones")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_GENERADA_PERIODO_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.anual.resultado-regimen-general")
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.devengada-303",
)
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.deducible-303",
)
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.resultado-303",
)
_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA: CasillaId = _casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
)
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = _casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
)
_M303_REPERCUTIDO_GENERAL_BASE_CASILLA: CasillaId = _casilla_id("07")
_M303_SOPORTADO_INTERIORES_BASE_CASILLA: CasillaId = _casilla_id("28")
_M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA: CasillaId = _casilla_id("09")
_M303_SOPORTADO_INTERIORES_CUOTA_CASILLA: CasillaId = _casilla_id("29")
_M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA: CasillaId = _casilla_id("01")
_M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA: CasillaId = _casilla_id("04")


@lru_cache(maxsize=1)
def _modelo_303_revision() -> ModeloRevision:
    modelo = resources().modelos.get("303")
    return modelo.revisions["2009-y-siguientes"]


def _binding(binding_id: str = "modelo-303-iva-repercutido-general-cuota") -> DataBindingDefinition:
    return next(item for item in _modelo_303_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**selector_as_dict(binding), **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: BindingAggregationOp) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": BindingAggregation(op=op)})


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    category: IvaCategory = IvaCategory.DOMESTIC_GENERAL_21,
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    base: Decimal = Decimal("1000"),
    iva: Decimal = Decimal("210"),
    recargo: Decimal = Decimal("0"),
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
        recargo_amount=recargo,
    )


def _revision_with_bindings(*bindings: DataBindingDefinition) -> ModeloRevision:
    return _modelo_303_revision().model_copy(update={"bindings": bindings})


def _calculate_303_from_observations(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": observations[-1].transaction_date},
    )


def _calculate_390_from_observations_and_303_filings(
    *,
    filing_year: int,
    observations: tuple[IvaLedgerObservation, ...],
    quarterly_results: dict[str, RegistryCalculationResult],
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("390", filing_year=filing_year, period="0A")
    ledger_binding_values = resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations)
    m303_observations = tuple(
        RegistryModeloObservation(
            modelo="303",
            filing_year=filing_year,
            period=period,
            observations=result.observations,
        )
        for period, result in quarterly_results.items()
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        m303_observations,
        filing_year=filing_year,
        period="0A",
    )
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    annual_partition_values = resolve_iva_compensation_annual_partition_binding_values(
        snapshot.revision,
        m303_observations,
        filing_year=filing_year,
    )
    binding_values = {**ledger_binding_values, **relation_binding_values, **annual_partition_values}
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
