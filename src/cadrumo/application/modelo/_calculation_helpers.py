"""Shared calculation helpers for modelo application actions.

The helpers load mutable :class:`~cadrumo.domain.modelos.WorkUnit` records, resolve
their law-determined
:class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`, and project engine,
imported, or amended values into
:class:`~cadrumo.domain.calculations.registry.CasillaObservation` provenance rows.
Amendment helpers reuse the baseline
:class:`~cadrumo.domain.modelos.CalculationRevision` where a corrected casilla was
not overridden, and rebuild overridden rows from the selected snapshot so
legal/source grounding is never silently erased.

See Also:
    :mod:`cadrumo.application.modelo._calculation_actions`:
        Uses these helpers before registry-engine execution and persistence.
    :mod:`cadrumo.application.modelo._amendment_actions`:
        Reuses amendment observation projection for corrected filing records.
    :mod:`cadrumo.application.modelo._registry_resources`:
        Supplies the packaged registry authority used for snapshot resolution.
    :class:`~cadrumo.domain.calculations.registry.RegistryCalculationResult`:
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
from ...domain.modelos import (
    CalculationRevision,
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
)
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


def load_work_unit_for_calculation(
    work_units: WorkUnitCatalogue,
    *,
    work_unit_id: str,
    repository_bucket_id: str | None = None,
) -> WorkUnit:
    """Load a mutable :class:`cadrumo.domain.modelos.WorkUnit` for calculation.

    Missing ids raise :class:`WorkUnitNotFoundError`. A unit whose own
    ``bucket_id`` disagrees with ``repository_bucket_id`` (the caller-supplied
    ``work_unit_repository``'s bound bucket) is reported as NOT FOUND rather
    than as a refusal: from that repository's scope it genuinely is not
    addressable, and a distinct refusal would confirm the existence of a work
    unit in a bucket the caller has no claim on. Mirrors
    :func:`~application.modelo._work_lifecycle._work_unit_in_repository_bucket`
    and :func:`~application.modelo._calculation_actions._calculation_revision_in_repository_bucket`,
    the equivalent checks on the work-unit-lifecycle and calculation-revision
    addressing paths -- this is the calculate entrypoint's own counterpart.
    The check is skipped only when ``repository_bucket_id`` is ``None``,
    where there is no scope to compare against.

    Work units already marked ``DESCARTADO`` raise
    :class:`WorkUnitMutationRefusedError`, because the calculate path must not
    create a new revision for a discarded lifecycle record.
    """
    work_unit = work_units.get(work_unit_id)
    if work_unit is None or (repository_bucket_id is not None and work_unit.bucket_id != repository_bucket_id):
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
    """Resolve and return the :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`.

    After resolution the snapshot's revision id is asserted equal to the work
    unit's pinned ``revision_id`` (a calc-time assertion).  Divergence — possible only when
    the registry's law-mapping was corrected after the work unit was created, or
    for units persisted before the strengthened creation gate — raises
    :exc:`WorkUnitRevisionDivergenceError` directing the operator to re-create
    the work unit.

    The :class:`cadrumo.domain.modelos.WorkUnit` ``revision_id`` is never passed
    into the snapshot resolution call; it is only compared against the
    law-determined resolver answer.

    See Also:
        :func:`cadrumo.application.modelo._work_addressing.resolve_registry_revision_for_work_target`:
            Performs the create-time counterpart of this revision identity
            assertion.
        :class:`cadrumo.application.modelo._action_errors.WorkUnitRevisionDivergenceError`:
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
    """Build :class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows.

    Formula targets carry their
    :class:`~cadrumo.domain.calculations.registry.RegistryCalculationEntry`
    provenance. Non-formula values get legal/source references from the
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` casilla
    definitions. Any value without a formula entry or registry casilla
    definition raises
    :class:`cadrumo.application.modelo.CasillaProvenanceMissingError` through
    :func:`cadrumo.application.modelo._calculation_helpers.casilla_observation_for`
    rather than emitting an ungrounded row.
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
    """Build :class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows for imports.

    The :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` supplies the
    provenance for imported values that have no
    :class:`~cadrumo.domain.calculations.registry.RegistryCalculationEntry`
    in the current process. This keeps imported AEAT baselines on the same
    typed-observation contract as locally calculated revisions.

    See Also:
        :func:`cadrumo.application.modelo.import_external_filing_evidence`:
            Persists the external-evidence baseline that consumes these rows.
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
    """Project one casilla into a typed observation with full provenance.

    Formula entries contribute formula id, operand lineage, and legal/source
    refs. Non-formula casillas use the
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` selected by
    the :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`. A missing
    definition is a hard provenance error because emitting a
    :class:`~cadrumo.domain.calculations.registry.CasillaObservation` without
    ``legal_refs`` and ``source_refs`` would erase legal grounding.
    """
    if entry is not None:
        return CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=entry.formula_id,
            op=entry.op,
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
    """Build amendment :class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows.

    The baseline :class:`~cadrumo.domain.modelos.CalculationRevision` contributes
    unchanged observations for casillas the amendment did not override. Newly
    overridden casillas are rebuilt from the
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` so the persisted
    amendment revision carries legal/source provenance even when the imported
    baseline had sparse observation rows. A corrected casilla absent from the
    snapshot raises :class:`cadrumo.application.modelo.CasillaProvenanceMissingError`.

    See Also:
        :func:`cadrumo.application.modelo.amend_modelo_revision`:
            Uses these rows for the corrected amendment revision.
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
