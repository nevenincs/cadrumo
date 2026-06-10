"""Persist filed AEAT observations into calculation-history repositories.

Use of :class:`CasillaObservation` for compliance.
"""

from __future__ import annotations

from decimal import Decimal

from ...adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionObservation,
    SedeParseError,
    registry_observation_from_filed_declaration,
)
from ...application.calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    iva_compensation_state_from_filed_observation,
    observation_key,
)
from ...core import Modelo
from ...core.resources import resources
from ...domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ...domain.iva_compensation._carry_forward import derive_303_compensation_available
from ._errors import LiveApplicationError, LiveApplicationInputError


def persist_filed_calculation_observation(
    observation: FiledDeclaracionObservation,
    *,
    repository: CalculationObservationRepository | None = None,
) -> str:
    """Promote one AEAT filed-declaration observation into calculation history."""
    registry_observation = registry_observation_from_filed_declaration(observation)
    registry_observation = _with_derived_303_compensation_available(registry_observation)
    repo = repository if repository is not None else CalculationObservationRepository()
    repo.save_observation(
        registry_observation,
        source_kind="aeat_sede_justificante",
        captured_at=observation.presented_at,
    )
    if observation.modelo == Modelo.M303.value:
        IvaCompensationHistoryRepository().save_period(iva_compensation_state_from_filed_observation(observation))
    return observation_key(registry_observation.modelo, registry_observation.filing_year, registry_observation.period)


def persist_latest_filed_calculation_observations(
    observations: tuple[FiledDeclaracionObservation, ...],
) -> tuple[str, ...]:
    """Persist only the latest captured observation per modelo/year/period."""
    latest: dict[tuple[str, int, str], FiledDeclaracionObservation] = {}
    for observation in observations:
        key = (observation.modelo, observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or (observation.presented_at, observation.expediente_id) > (
            current.presented_at,
            current.expediente_id,
        ):
            latest[key] = observation
    return tuple(
        key
        for _key, observation in sorted(latest.items())
        for key in _persist_filed_calculation_observation_if_extractable(observation)
    )


def persist_iva_compensation_history_observations_strict(
    observations: tuple[FiledDeclaracionObservation, ...],
) -> tuple[str, ...]:
    """Persist latest Modelo 303 observations and verify each history row reloads."""
    latest: dict[tuple[int, str], FiledDeclaracionObservation] = {}
    for observation in observations:
        if observation.modelo != Modelo.M303.value:
            raise LiveApplicationInputError(
                translated_message="live.errors.iva_history_modelo_303_only",
                context={"modelo": observation.modelo},
            )
        key = (observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or (observation.presented_at, observation.expediente_id) > (
            current.presented_at,
            current.expediente_id,
        ):
            latest[key] = observation

    keys: list[str] = []
    history_repo = IvaCompensationHistoryRepository()
    for (_year, _period), observation in sorted(latest.items()):
        try:
            key = persist_filed_calculation_observation(observation)
        except SedeParseError as exc:
            raise LiveApplicationError(
                f"filed Modelo 303 {observation.ejercicio}/{observation.period} "
                "could not be promoted into IVA compensation history"
            ) from exc
        if history_repo.load_period(observation.ejercicio, observation.period) is None:
            raise LiveApplicationError(
                f"secure IVA compensation history did not reload after persisting "
                f"Modelo 303 {observation.ejercicio}/{observation.period}"
            )
        keys.append(key)
    return tuple(keys)


def latest_declarations_by_period(declarations: tuple[Declaracion, ...]) -> tuple[Declaracion, ...]:
    """Return the latest :class:`Declaracion` per period from register rows."""
    latest: dict[str, Declaracion] = {}
    for declaration in declarations:
        current = latest.get(declaration.period)
        if current is None:
            latest[declaration.period] = declaration
            continue
        current_rank = (current.estado.upper() == "ALTA", current.presented_at, current.expediente_id)
        candidate_rank = (declaration.estado.upper() == "ALTA", declaration.presented_at, declaration.expediente_id)
        if candidate_rank > current_rank:
            latest[declaration.period] = declaration
    return tuple(latest[key] for key in sorted(latest, key=_history_period_sort_key))


def _history_period_sort_key(period: str) -> tuple[int, str]:
    upper = period.upper()
    if upper.endswith("T") and upper[:-1].isdigit():
        return (int(upper[:-1]), upper)
    if upper.isdigit():
        return (int(upper), upper)
    return (100, upper)


def _persist_filed_calculation_observation_if_extractable(
    observation: FiledDeclaracionObservation,
) -> tuple[str, ...]:
    try:
        return (persist_filed_calculation_observation(observation),)
    except SedeParseError:
        return ()


def _with_derived_303_compensation_available(
    observation: RegistryModeloObservation,
) -> RegistryModeloObservation:
    """Add the internal Modelo 303 carry-forward value from official filed casillas."""
    if observation.modelo != Modelo.M303:
        return observation
    target_id = "iva.compensacion-disponible-fin-periodo"
    if target_id in observation.casilla_values:
        return observation
    posterior = _casilla_decimal(
        observation.casilla_values,
        "87",
        "iva.compensacion-pendiente-periodos-posteriores",
    )
    resultado = _casilla_decimal(observation.casilla_values, "69", "iva.resultado")
    if posterior is None or resultado is None:
        return observation

    available = derive_303_compensation_available(posterior=posterior, resultado=resultado)
    snapshot = resources().modelos.authority.snapshot(
        Modelo.M303.value,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    casilla = next(item for item in snapshot.revision.casillas if item.id == target_id)
    formula = next(item for item in snapshot.revision.formulas if item.target == target_id)
    derived = CasillaObservation(
        casilla_id=target_id,
        value=available,
        formula_id=formula.id,
        operand_refs=("87", "69"),
        operand_values=(posterior, resultado),
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
    )
    return observation.model_copy(update={"observations": (*observation.observations, derived)})


def _casilla_decimal(values: dict[str, Decimal], *casilla_ids: str) -> Decimal | None:
    for casilla_id in casilla_ids:
        value = values.get(casilla_id)
        if value is not None:
            return value
    return None


__all__ = [
    "latest_declarations_by_period",
    "persist_filed_calculation_observation",
    "persist_iva_compensation_history_observations_strict",
    "persist_latest_filed_calculation_observations",
]
