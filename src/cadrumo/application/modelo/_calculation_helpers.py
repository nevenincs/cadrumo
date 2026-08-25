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

from ...core import CasillaId, Period, RegistryAuthorityGrade
from ...domain.calculations.registry.schema import (
    CasillaDefinition,
    RegistrySnapshot,
)
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.formula_runtime import (
    RegistryCalculationEntry,
    RegistryCalculationResult,
)
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.modelos import (
    CalculationRevision,
    WorkUnit,
    WorkUnitCatalogue,
)
from ._action_errors import (
    CalculationRegistryUnavailableError,
    CasillaProvenanceMissingError,
    WorkUnitRevisionDivergenceError,
)
from ._registry_resources import (
    authority_via_resources as _authority_via_resources,
)
from ._registry_resources import (
    registry_root as _registry_root,
)
from ._work_lifecycle import ActiveWorkUnitUse, require_active_work_unit


def load_work_unit_for_calculation(
    work_units: WorkUnitCatalogue,
    *,
    work_unit_id: str,
    repository_bucket_id: str | None = None,
) -> WorkUnit:
    """Delegate calculation target state/addressability to the canonical lifecycle guard."""
    return require_active_work_unit(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=repository_bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )


def assert_snapshot_matches_work_unit_revision(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    *,
    period: Period | None = None,
) -> None:
    """Raise when the :class:`RegistrySnapshot` revision diverges from the pinned one.

    ``snapshot``'s revision must equal the revision ``work_unit`` was pinned to.

    This is the single home for the D1 calc-time assertion's message and
    exception type: the law-determined revision must equal the revision the
    work unit was created against, or :exc:`WorkUnitRevisionDivergenceError`
    directs the operator to re-create the work unit. Divergence is possible
    only when the registry's law-mapping was corrected after the work unit was
    created, or for units persisted before the strengthened creation gate.

    ``period`` names the AEAT natural-key coordinates the message reports;
    most callers resolve ``snapshot`` from ``work_unit.period`` and can omit
    it. A caller that resolves ``snapshot`` from a different, caller-supplied
    period (see
    :func:`cadrumo.application.modelo._result_disposition_resolution._result_disposition_values_for_revision`,
    which threads the export path's period through for the Modelo 303
    refund-election decision) passes that period so the message names the
    coordinates the snapshot was actually resolved against.

    See Also:
        :func:`cadrumo.application.modelo.work_addressing.resolve_registry_revision_for_work_target`:
            Performs the create-time counterpart of this revision identity
            assertion.
        :class:`cadrumo.application.modelo._action_errors.WorkUnitRevisionDivergenceError`:
            Refusal raised when the pinned revision no longer matches the
            law-determined snapshot.
    """
    if snapshot.revision.id == work_unit.revision_id:
        return
    resolved_period = period if period is not None else work_unit.period
    raise WorkUnitRevisionDivergenceError(
        translated_message="application.modelo.errors.work_unit_revision_divergence",
        # The context keys ARE the message template's placeholder names. They
        # had drifted -- the catalogue asks for work_unit_id, work_unit_revision
        # and law_revision -- so the rendered refusal showed those three
        # placeholders literally and named NEITHER revision nor the work unit,
        # which is precisely the guidance an operator needs to re-create it.
        context={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": resolved_period.registry_token,
            "work_unit_revision": work_unit.revision_id,
            "law_revision": snapshot.revision.id,
        },
    )


def resolve_registry_snapshot_for_work_unit(
    work_unit: WorkUnit,
    *,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    """Resolve and return the :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`.

    After resolution the snapshot's revision id is asserted equal to the work
    unit's pinned ``revision_id`` via :func:`assert_snapshot_matches_work_unit_revision`
    (a calc-time assertion).

    The :class:`cadrumo.domain.modelos.WorkUnit` ``revision_id`` is never passed
    into the snapshot resolution call; it is only compared against the
    law-determined resolver answer.

    See Also:
        :func:`cadrumo.application.modelo.work_addressing.resolve_registry_revision_for_work_target`:
            Performs the create-time counterpart of this revision identity
            assertion.
        :class:`cadrumo.application.modelo._action_errors.WorkUnitRevisionDivergenceError`:
            Refusal raised when the pinned revision no longer matches the
            law-determined snapshot.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

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
            grade=grade,
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
    assert_snapshot_matches_work_unit_revision(work_unit, snapshot)
    return snapshot


def build_typed_observations(
    *,
    engine_result: RegistryCalculationResult,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build :class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows.

    The engine result is already the canonical grounded envelope, including
    text-family casillas that do not appear in its Decimal-only ``values``
    projection. This boundary verifies every observation still belongs to the
    selected registry revision, then preserves the envelope unchanged. Any
    observation without a registry casilla definition raises
    :class:`cadrumo.application.modelo.CasillaProvenanceMissingError` through
    :func:`cadrumo.application.modelo._calculation_helpers.casilla_observation_for`
    rather than emitting an ungrounded row.
    """
    revision_casillas_by_id = casillas_by_id(snapshot.revision)
    unknown = tuple(
        observation.casilla_id
        for observation in engine_result.observations
        if observation.casilla_id not in revision_casillas_by_id
    )
    if unknown:
        raise CasillaProvenanceMissingError(
            translated_message="errors.error.error_modelo_casilla_provenance_missing",
            context={"casilla_id": str(unknown[0]), "origin": "engine_result"},
        )
    return engine_result.observations


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
            translated_message="errors.error.error_modelo_casilla_provenance_missing",
            context={"casilla_id": str(casilla_id), "origin": "engine_result"},
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
                translated_message="errors.error.error_modelo_casilla_provenance_missing",
                context={"casilla_id": str(casilla_id), "origin": "amendment_corrected_values"},
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
    "assert_snapshot_matches_work_unit_revision",
    "build_typed_observations",
    "casilla_observation_for",
    "external_filing_observations",
    "load_work_unit_for_calculation",
    "resolve_registry_snapshot_for_work_unit",
]
