from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from decimal import Decimal
from functools import cache

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from .....core.period import Period
from .....core.resources.bundled_data import bundled_path
from .registry_tree import bundled_registry_tree
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..errors import NoRevisionForPeriodError
from ..relations import RegistryFoldRequirement
from ..schema import ModeloRevision
from .snapshot_support import build_snapshot

_M202_CUOTA_BASE_CASILLA: CasillaId = validated_casilla_id("01", surface="_M202_CUOTA_BASE_CASILLA")
_M200_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_M200_CUOTA_DIFERENCIAL_CASILLA",
)


def _casilla_inputs(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="cross-dependency calculation input casillas")


def _one_filed_cadence(requirement: RegistryFoldRequirement) -> tuple[tuple[int, str], ...]:
    """Return the indexed periods of the first declared cadence only.

    A source declared over alternative cadences (Modelo 111 quarterly or
    monthly) is filed under exactly one of them, so a fixture that observed
    every declared period would describe a filer no resolver can accept.
    """
    first_kind = Period.from_year_and_code(requirement.filing_year, requirement.periods[0]).kind
    return tuple(
        (index, period)
        for index, period in enumerate(requirement.periods)
        if Period.from_year_and_code(requirement.filing_year, period).kind == first_kind
    )


def _observations_from_requirements(
    requirements: Iterable[RegistryFoldRequirement],
    value_for: Callable[[RegistryFoldRequirement, int], Decimal],
    *,
    target_modelo: str | None = None,
    fallback_revision: ModeloRevision | None = None,
) -> tuple[RegistryModeloObservation, ...]:
    observed: dict[tuple[str, int, str], dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        for period_index, period in _one_filed_cadence(requirement):
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


@cache
def _cross_dependency_registry_tree():
    return bundled_registry_tree()


def _grounded_observations(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    target_modelo: str | None = None,
    fallback_revision: ModeloRevision | None = None,
) -> tuple[CasillaObservation, ...]:
    """Ground observations in the selected snapshot, scoped to ``modelo`` alone.

    Built from the published registry-tree view at calculation grade -- these
    fixtures assert cross-model relation folding, never a filing claim -- so
    only the requested modelo's own revisions are validated.
    """
    source = f"{modelo}/{filing_year}/{period}"
    try:
        modelos, catalogues = _cross_dependency_registry_tree()
        modelo_definition = next(item for item in modelos if item.id == modelo)
        snapshot = build_snapshot(
            modelo_definition,
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year,
            period=period,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
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
