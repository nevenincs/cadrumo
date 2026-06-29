"""Shared calculation helpers for modelo application actions.

The helpers load mutable :class:`~aeat.domain.modelos._work_unit.WorkUnit`
records, resolve their law-determined :class:`RegistrySnapshot`, and project
engine or imported values into :class:`CasillaObservation` provenance rows.
Amendment helpers reuse the baseline :class:`CalculationRevision` where a
corrected casilla was not overridden.

See Also:
    :mod:`aeat.application.modelo._calculation_actions`:
        Uses these helpers before registry-engine execution and persistence.
    :mod:`aeat.application.modelo._amendment_actions`:
        Reuses amendment observation projection for corrected filing records.
    :mod:`aeat.application.modelo._registry_resources`:
        Supplies the packaged registry authority used for snapshot resolution.
    :class:`aeat.domain.calculations.registry.RegistryCalculationResult`:
        Registry-engine result whose values and formula entries are projected
        into typed observations.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.registry import (
    CasillaDefinition,
    CasillaId,
    CasillaObservation,
    RegistryCalculationEntry,
    RegistryCalculationResult,
    RegistrySnapshot,
    casillas_by_id,
)
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ._action_errors import (
    CalculationRegistryUnavailableError,
    CasillaProvenanceMissingError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    WorkUnitRevisionDivergenceError,
)
from ._registry_resources import (
    authority_via_resources as _authority_via_resources,
)
from ._registry_resources import (
    registry_root as _registry_root,
)


def load_work_unit_for_calculation(work_units: WorkUnitCatalogue, *, work_unit_id: str) -> WorkUnit:
    """Load a mutable :class:`WorkUnit` for calculation.

    Missing ids raise :class:`WorkUnitNotFoundError`. Work units already marked
    ``DESCARTADO`` raise :class:`WorkUnitMutationRefusedError`, because the
    calculate path must not create a new revision for a discarded lifecycle
    record.
    """
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
    """Resolve and return the :class:`RegistrySnapshot` for ``(modelo, filing_year, period)``.

    After resolution the snapshot's revision id is asserted equal to the work
    unit's pinned ``revision_id`` (D1 calc-time assertion, per the
    period-revision-resolution ADR ruling 2).  Divergence — possible only when
    the registry's law-mapping was corrected after the work unit was created, or
    for units persisted before the strengthened creation gate — raises
    :exc:`WorkUnitRevisionDivergenceError` directing the operator to re-create
    the work unit.

    The work unit's ``revision_id`` is never passed into the snapshot resolution
    call; it is only compared against the resolver's answer.

    See Also:
        :func:`aeat.application.modelo._work_addressing.resolve_registry_revision_for_work_target`:
            Performs the create-time counterpart of this revision identity
            assertion.
        :class:`aeat.application.modelo._action_errors.WorkUnitRevisionDivergenceError`:
            Refusal raised when the pinned revision no longer matches the
            law-determined snapshot.
    """
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_root_missing",
            context={"registry_root": _registry_root()},
        ) from exc
    try:
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_snapshot_unresolved",
            context={
                "modelo": work_unit.modelo,
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
        ) from exc
    # D1 calc-time assertion: the law-determined revision must equal the
    # revision the work unit was created against.  The work unit's revision_id
    # is an identity claim, not a resolution input.
    if snapshot.revision.id != work_unit.revision_id:
        raise WorkUnitRevisionDivergenceError(
            f"work unit {work_unit.work_unit_id!r} was created against registry revision "
            f"{work_unit.revision_id!r}, but the law-determined revision for "
            f"modelo {work_unit.modelo!r} {work_unit.filing_year} {work_unit.period.registry_token!r} "
            f"is now {snapshot.revision.id!r}. "
            f"The registry's law-mapping was corrected after this work unit was created. "
            f"Re-create the work unit (discard this one and run `aeat app modelo work create`) "
            f"to bind it to the current law-determined revision.",
        )
    return snapshot


def build_typed_observations(
    *,
    engine_result: RegistryCalculationResult,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build a :class:`CasillaObservation` tuple for every engine-result casilla.

    Formula targets carry their :class:`RegistryCalculationEntry` provenance.
    Non-formula values get legal/source references from the
    :class:`RegistrySnapshot` casilla definitions. Any value without either
    source raises :class:`CasillaProvenanceMissingError` through
    :func:`casilla_observation_for` rather than emitting an ungrounded row.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    entries_by_target = {entry.target_casilla_id: entry for entry in engine_result.entries}
    return tuple(
        casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=entries_by_target.get(casilla_id),
            registry_casilla=revision_casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in engine_result.values.items()
    )


def external_filing_observations(
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build :class:`CasillaObservation` records for externally imported casilla values.

    The :class:`RegistrySnapshot` supplies the provenance for imported values that
    have no formula entry in the current process. This keeps imported AEAT
    baselines on the same typed-observation contract as locally calculated
    revisions.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    return tuple(
        casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=None,
            registry_casilla=revision_casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in casilla_values.items()
    )


def casilla_observation_for(
    *,
    casilla_id: CasillaId,
    value: Decimal,
    entry: RegistryCalculationEntry | None,
    registry_casilla: CasillaDefinition | None,
) -> CasillaObservation:
    """Project one casilla into a :class:`CasillaObservation` with full provenance.

    Formula entries contribute formula id, operand lineage, and legal/source
    refs. Non-formula casillas use the registry casilla definition. A missing
    definition is a hard provenance error, because emitting a row without
    ``legal_refs`` and ``source_refs`` would erase legal grounding.
    """
    if entry is not None:
        return CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=entry.formula_id,
            operand_refs=entry.operand_refs,
            operand_casilla_refs=entry.operand_casilla_refs,
            operand_values=entry.operand_values,
            legal_refs=entry.legal_refs,
            source_refs=entry.source_refs,
        )
    if registry_casilla is None:
        raise CasillaProvenanceMissingError(
            f"casilla {casilla_id!r} is present in the engine result but absent "
            f"from the registry snapshot revision; it has no legal_refs / "
            f"source_refs definition and cannot be projected to a "
            f"CasillaObservation without erasing legal provenance",
        )
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        formula_id=None,
        operand_refs=(),
        operand_casilla_refs=(),
        operand_values=(),
        legal_refs=registry_casilla.legal_refs,
        source_refs=registry_casilla.source_refs,
    )


def amendment_observations(
    *,
    corrected_values: Mapping[CasillaId, Decimal],
    overrides: Mapping[CasillaId, Decimal],
    baseline_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build :class:`CasillaObservation` records for an amendment revision.

    The baseline :class:`CalculationRevision` contributes unchanged observations
    for casillas the amendment did not override. Newly overridden casillas are
    rebuilt from the :class:`RegistrySnapshot` so the persisted amendment
    revision carries legal/source provenance even when the imported baseline had
    sparse observation rows.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    baseline_by_id = {obs.casilla_id: obs for obs in baseline_revision.observations}
    observations: list[CasillaObservation] = []
    for casilla_id, value in corrected_values.items():
        if casilla_id not in overrides:
            carried = baseline_by_id.get(casilla_id)
            if carried is not None:
                observations.append(carried)
                continue
        registry_casilla = revision_casillas_by_id.get(casilla_id)
        if registry_casilla is None:
            raise CasillaProvenanceMissingError(
                f"casilla {casilla_id!r} is present in the amendment's corrected "
                f"values but absent from the registry snapshot revision; it has "
                f"no legal_refs / source_refs definition and cannot be projected "
                f"to a CasillaObservation without erasing legal provenance",
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=registry_casilla.legal_refs,
                source_refs=registry_casilla.source_refs,
            ),
        )
    return tuple(observations)


__all__ = [
    "WorkUnitRevisionDivergenceError",
    "amendment_observations",
    "build_typed_observations",
    "casilla_observation_for",
    "external_filing_observations",
    "load_work_unit_for_calculation",
    "resolve_registry_snapshot_for_work_unit",
]
