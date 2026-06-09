"""Shared calculation helpers for modelo application actions.

Use of :class:`CalculationRevision`, :class:`CasillaObservation`, :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.i18n import tr
from ...domain.calculations.registry import (
    CasillaDefinition,
    CasillaObservation,
    RegistryCalculationEntry,
    RegistryCalculationResult,
    RegistrySnapshot,
)
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ._action_errors import (
    CalculationRegistryUnavailableError,
    CasillaProvenanceMissingError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ._registry_resources import (
    authority_via_resources as _authority_via_resources,
)
from ._registry_resources import (
    registry_root as _registry_root,
)


def load_work_unit_for_calculation(work_units: WorkUnitCatalogue, *, work_unit_id: str) -> WorkUnit:
    """Load a work unit by id, rejecting missing ids and DISCARDED state."""
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_discarded_cannot_calculate",
            context={"work_unit_id": work_unit_id},
        )
    return work_unit


def resolve_registry_snapshot_for_work_unit(work_unit: WorkUnit) -> RegistrySnapshot:
    """Resolve the registry snapshot for ``(modelo, filing_year, period)``."""
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            tr(
                "application.modelo.errors.calculation_registry_root_missing",
                registry_root=_registry_root(),
            ),
            translated_message="application.modelo.errors.calculation_registry_root_missing",
            context={"registry_root": _registry_root()},
        ) from exc
    try:
        return authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            tr(
                "application.modelo.errors.calculation_registry_snapshot_unresolved",
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period,
            ),
            translated_message="application.modelo.errors.calculation_registry_snapshot_unresolved",
            context={"modelo": work_unit.modelo, "filing_year": work_unit.filing_year, "period": work_unit.period},
        ) from exc


def build_typed_observations(
    *, engine_result: RegistryCalculationResult, snapshot: RegistrySnapshot
) -> tuple[CasillaObservation, ...]:
    """Build a typed ``CasillaObservation`` tuple for every engine-result casilla.

    Use of :class:`RegistrySnapshot` for compliance.
    """
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    entries_by_target = {entry.target: entry for entry in engine_result.entries}
    return tuple(
        casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=entries_by_target.get(casilla_id),
            registry_casilla=casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in engine_result.values.items()
    )


def external_filing_observations(
    *,
    casilla_values: Mapping[str, Decimal],
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build registry-grounded observations for externally imported casilla values.

    Use of :class:`RegistrySnapshot` for compliance.
    """
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    return tuple(
        casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=None,
            registry_casilla=casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in casilla_values.items()
    )


def casilla_observation_for(
    *,
    casilla_id: str,
    value: Decimal,
    entry: RegistryCalculationEntry | None,
    registry_casilla: CasillaDefinition | None,
) -> CasillaObservation:
    """Project one casilla into a ``CasillaObservation`` with full provenance."""
    if entry is not None:
        return CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=entry.formula_id,
            operand_refs=entry.operand_refs,
            operand_values=entry.operand_values,
            legal_refs=entry.legal_refs,
            source_refs=entry.source_refs,
        )
    if registry_casilla is None:
        raise CasillaProvenanceMissingError(
            f"casilla {casilla_id!r} is present in the engine result but absent "
            f"from the registry snapshot revision; it has no legal_refs / "
            f"source_refs definition and cannot be projected to a "
            f"CasillaObservation without erasing legal provenance"
        )
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        formula_id=None,
        operand_refs=(),
        operand_values=(),
        legal_refs=registry_casilla.legal_refs,
        source_refs=registry_casilla.source_refs,
    )


def amendment_observations(
    *,
    corrected_values: Mapping[str, Decimal],
    overrides: Mapping[str, Decimal],
    baseline_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build typed observations for an amendment revision.

    Use of :class:`CalculationRevision`, :class:`RegistrySnapshot` for compliance.
    """
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    baseline_by_id = {obs.casilla_id: obs for obs in baseline_revision.observations}
    observations: list[CasillaObservation] = []
    for casilla_id, value in corrected_values.items():
        if casilla_id not in overrides:
            carried = baseline_by_id.get(casilla_id)
            if carried is not None:
                observations.append(carried)
                continue
        registry_casilla = casillas_by_id.get(casilla_id)
        if registry_casilla is None:
            raise CasillaProvenanceMissingError(
                f"casilla {casilla_id!r} is present in the amendment's corrected "
                f"values but absent from the registry snapshot revision; it has "
                f"no legal_refs / source_refs definition and cannot be projected "
                f"to a CasillaObservation without erasing legal provenance"
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                formula_id=None,
                operand_refs=(),
                operand_values=(),
                legal_refs=registry_casilla.legal_refs,
                source_refs=registry_casilla.source_refs,
            )
        )
    return tuple(observations)


__all__ = [
    "amendment_observations",
    "build_typed_observations",
    "casilla_observation_for",
    "external_filing_observations",
    "load_work_unit_for_calculation",
    "resolve_registry_snapshot_for_work_unit",
]
