from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from decimal import Decimal

from .....core.resources import resources
from .. import CasillaId, validated_casilla_id, validated_casilla_id_map
from .._bindings import CasillaObservation, RegistryModeloObservation
from .._errors import NoRevisionForPeriodError
from .._relations import RegistryFoldRequirement
from .._schema import ModeloRevision

_M202_CUOTA_BASE_CASILLA: CasillaId = validated_casilla_id("01", surface="_M202_CUOTA_BASE_CASILLA")
_M200_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_M200_CUOTA_DIFERENCIAL_CASILLA",
)


def _casilla_inputs(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="cross-dependency calculation input casillas")


def _observations_from_requirements(
    requirements: Iterable[RegistryFoldRequirement],
    value_for: Callable[[RegistryFoldRequirement, int], Decimal],
    *,
    target_modelo: str | None = None,
    fallback_revision: ModeloRevision | None = None,
) -> tuple[RegistryModeloObservation, ...]:
    observed: dict[tuple[str, int, str], dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        for period_index, period in enumerate(requirement.periods):
            key = (requirement.source_modelo, requirement.filing_year, period)
            casilla_values = observed.setdefault(key, {})
            casilla_values[requirement.source_casilla_ids[0]] = value_for(requirement, period_index)
    return tuple(
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=_grounded_observations(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                casilla_values=casilla_values,
                target_modelo=target_modelo,
                fallback_revision=fallback_revision,
            ),
        )
        for (modelo, filing_year, period), casilla_values in sorted(observed.items())
    )


def _grounded_observations(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    target_modelo: str | None = None,
    fallback_revision: ModeloRevision | None = None,
) -> tuple[CasillaObservation, ...]:
    source = f"{modelo}/{filing_year}/{period}"
    try:
        snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
        source = f"{modelo}/{snapshot.revision.id}/{filing_year}/{period}"
        casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    except NoRevisionForPeriodError:
        if target_modelo != modelo or fallback_revision is None:
            raise
        source = f"{modelo}/{fallback_revision.id}/{filing_year}/{period} self-relation fallback"
        casillas_by_id = {casilla.id: casilla for casilla in fallback_revision.casillas}
    observations: list[CasillaObservation] = []
    for casilla_id, value in casilla_values.items():
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None:
            raise AssertionError(
                f"cross-dependency fixture observed casilla {casilla_id!r} is absent from registry snapshot {source}",
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=casilla.legal_refs,
                source_refs=casilla.source_refs,
            ),
        )
    return tuple(observations)
