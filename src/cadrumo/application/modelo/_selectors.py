"""Calculation-revision selector policy for Modelo work units.

Revision selectors load persisted :class:`CalculationRevision` rows and return a
:class:`ModeloCalculationRevisionSelection` for current, latest draft, latest
verified, filed, or explicit-id picks.

Command-specific revision defaults stay here rather than in CLI modules:
verification selects the current draft, filing selects the current
verified-complete revision, and export prefers the current filed revision before
falling back to an unambiguous verified-complete revision.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import CalculationRevisionId, WorkUnitId
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloError,
    WorkUnit,
)


class ModeloCalculationRevisionSelector(StrEnum):
    """Closed selector set for calculation revisions under a work unit."""

    CURRENT = "current"
    LATEST_DRAFT = "latest-draft"
    LATEST_VERIFIED = "latest-verified"
    FILED = "filed"
    EXPLICIT = "explicit"


class ModeloCalculationRevisionSelectorError(ModeloError):
    """Base error for calculation-revision selector refusals."""


class ModeloCalculationRevisionSelectorNotFoundError(ModeloCalculationRevisionSelectorError, KeyError):
    """Raised when a requested calculation revision cannot be selected."""


class ModeloCalculationRevisionSelectorStateError(ModeloCalculationRevisionSelectorError):
    """Raised when a command-specific selector finds a revision in the wrong state."""


class ModeloCalculationRevisionSelectorAmbiguousError(ModeloCalculationRevisionSelectorError):
    """Raised when a default revision selector would have to guess."""

    def __init__(self, candidates: tuple[ModeloCalculationRevisionCandidate, ...]) -> None:
        self.candidates = candidates
        super().__init__("calculation revision selector is ambiguous; choose an explicit selector or revision id")


class ModeloCalculationRevisionCandidate(BaseModel):
    """Human-readable calculation revision metadata for selector guidance."""

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId
    short_calculation_revision_id: str
    work_unit_id: WorkUnitId
    state: CalculationRevisionState
    created_at: str
    updated_at: str
    verified_at: str | None = None
    filed_at: str | None = None

    @classmethod
    def from_revision(cls, revision: CalculationRevision) -> ModeloCalculationRevisionCandidate:
        """Project a :class:`CalculationRevision` into a :class:`ModeloCalculationRevisionCandidate`."""
        return cls(
            calculation_revision_id=revision.calculation_revision_id,
            short_calculation_revision_id=revision.calculation_revision_id[-12:],
            work_unit_id=revision.work_unit_id,
            state=revision.state,
            created_at=revision.created_at.isoformat(),
            updated_at=revision.updated_at.isoformat(),
            verified_at=revision.verified_at.isoformat() if revision.verified_at is not None else None,
            filed_at=revision.filed_at.isoformat() if revision.filed_at is not None else None,
        )


class ModeloCalculationRevisionSelection(BaseModel):
    """Resolved calculation revision selection under a work unit."""

    model_config = STRICT_FROZEN_CONFIG

    selector: ModeloCalculationRevisionSelector
    work_unit_id: WorkUnitId
    revision: CalculationRevision
    candidates: tuple[ModeloCalculationRevisionCandidate, ...] = ()


type ModeloCalculationRevisionDefault = Literal["verify", "file", "export"]
"""Command-specific default selector modes for calculation revisions."""


def select_modelo_calculation_revision(
    work_unit: WorkUnit,
    *,
    selector: ModeloCalculationRevisionSelector,
    calculation_revision_id: CalculationRevisionId | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationRevisionSelection:
    """Select one persisted calculation revision as :class:`ModeloCalculationRevisionSelection`.

    ``EXPLICIT`` requires ``calculation_revision_id`` and verifies the revision
    belongs to the supplied :class:`cadrumo.domain.modelos.WorkUnit`. Non-explicit
    selectors resolve through the work unit's current/filed pointers or by
    latest state, and refuse missing or mismatched state instead of falling back
    to another revision.
    """
    revisions = _revisions_for_work_unit(work_unit, calculation_repository=calculation_repository)
    if selector is ModeloCalculationRevisionSelector.EXPLICIT:
        if calculation_revision_id is None:
            raise ModeloCalculationRevisionSelectorNotFoundError(
                translated_message="errors.error.modelo_calculation_revision_selector_not_found",
                context={"selection": "explicit", "calculation_revision_id_present": False},
            )
        revision = _explicit_revision_for_work_unit(
            work_unit=work_unit,
            calculation_revision_id=calculation_revision_id,
            calculation_repository=calculation_repository,
        )
        return ModeloCalculationRevisionSelection(
            selector=selector,
            work_unit_id=work_unit.work_unit_id,
            revision=revision,
            candidates=(ModeloCalculationRevisionCandidate.from_revision(revision),),
        )
    if calculation_revision_id is not None:
        raise ModeloCalculationRevisionSelectorStateError(
            translated_message="errors.refused.modelo_calculation_revision_selector_state",
        )

    selected = {
        ModeloCalculationRevisionSelector.CURRENT: lambda: _revision_by_pointer(
            work_unit,
            work_unit.current_calculation_revision_id,
            calculation_repository=calculation_repository,
            pointer_name="current_calculation_revision_id",
        ),
        ModeloCalculationRevisionSelector.LATEST_DRAFT: lambda: _latest_revision_with_state(
            revisions,
            state=CalculationRevisionState.BORRADOR,
        ),
        ModeloCalculationRevisionSelector.LATEST_VERIFIED: lambda: _latest_revision_with_state(
            revisions,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
        ),
        ModeloCalculationRevisionSelector.FILED: lambda: _revision_by_pointer(
            work_unit,
            work_unit.filed_calculation_revision_id,
            calculation_repository=calculation_repository,
            pointer_name="filed_calculation_revision_id",
        ),
    }[selector]()
    return ModeloCalculationRevisionSelection(
        selector=selector,
        work_unit_id=work_unit.work_unit_id,
        revision=selected,
        candidates=(ModeloCalculationRevisionCandidate.from_revision(selected),),
    )


def resolve_modelo_calculation_revision_pick(
    work_unit: WorkUnit,
    *,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    calculation_revision_id: CalculationRevisionId | None = None,
    default_for: ModeloCalculationRevisionDefault | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationRevisionSelection:
    """Resolve a command-specific :class:`ModeloCalculationRevisionSelection` pick under one work unit.

    This is the application selector policy surface for commands that
    accept a natural work target plus a revision selector. It preserves
    the exact calculation-revision id escape hatch, while keeping
    command defaults explicit: verification consumes the current draft,
    filing consumes the current verified-complete revision, and export
    prefers filed/current verified revisions according to
    ``select_exportable_revision``.
    """
    if calculation_revision_id is not None:
        return select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.EXPLICIT,
            calculation_revision_id=calculation_revision_id,
            calculation_repository=calculation_repository,
        )
    if default_for == "file" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_current_verified_revision(work_unit, calculation_repository=calculation_repository)
    if default_for == "export" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_exportable_revision(work_unit, calculation_repository=calculation_repository)
    return select_modelo_calculation_revision(
        work_unit,
        selector=selector,
        calculation_repository=calculation_repository,
    )


def select_current_verified_revision(
    work_unit: WorkUnit,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationRevisionSelection:
    """Select the current verified-complete revision for filing.

    Returns a :class:`ModeloCalculationRevisionSelection`.
    """
    selection = select_modelo_calculation_revision(
        work_unit,
        selector=ModeloCalculationRevisionSelector.CURRENT,
        calculation_repository=calculation_repository,
    )
    if selection.revision.state is not CalculationRevisionState.VERIFICADO_COMPLETO:
        raise ModeloCalculationRevisionSelectorStateError(
            translated_message="errors.refused.modelo_calculation_revision_selector_state",
        )
    return selection


def select_exportable_revision(
    work_unit: WorkUnit,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationRevisionSelection:
    """Select the default exportable :class:`ModeloCalculationRevisionSelection` for a work unit.

    Preference order:
    1. current filed pointer, when it points to a current filed revision;
    2. current calculation pointer, when it is verified-complete;
    3. one unambiguous verified-complete revision, only when no current draft conflicts.
    """
    filed_revision = _optional_revision_by_pointer(
        work_unit,
        work_unit.filed_calculation_revision_id,
        calculation_repository=calculation_repository,
    )
    if filed_revision is not None and filed_revision.state is CalculationRevisionState.PRESENTADO:
        return ModeloCalculationRevisionSelection(
            selector=ModeloCalculationRevisionSelector.FILED,
            work_unit_id=work_unit.work_unit_id,
            revision=filed_revision,
            candidates=(ModeloCalculationRevisionCandidate.from_revision(filed_revision),),
        )

    current_revision = _optional_revision_by_pointer(
        work_unit,
        work_unit.current_calculation_revision_id,
        calculation_repository=calculation_repository,
    )
    if current_revision is not None:
        if current_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO:
            return ModeloCalculationRevisionSelection(
                selector=ModeloCalculationRevisionSelector.CURRENT,
                work_unit_id=work_unit.work_unit_id,
                revision=current_revision,
                candidates=(ModeloCalculationRevisionCandidate.from_revision(current_revision),),
            )
        if current_revision.state is CalculationRevisionState.BORRADOR:
            raise ModeloCalculationRevisionSelectorStateError(
                translated_message="errors.refused.modelo_calculation_revision_selector_state",
            )

    verified = tuple(
        revision
        for revision in _revisions_for_work_unit(work_unit, calculation_repository=calculation_repository)
        if revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    )
    if len(verified) == 1:
        revision = verified[0]
        return ModeloCalculationRevisionSelection(
            selector=ModeloCalculationRevisionSelector.LATEST_VERIFIED,
            work_unit_id=work_unit.work_unit_id,
            revision=revision,
            candidates=(ModeloCalculationRevisionCandidate.from_revision(revision),),
        )
    if len(verified) > 1:
        raise ModeloCalculationRevisionSelectorAmbiguousError(
            tuple(ModeloCalculationRevisionCandidate.from_revision(revision) for revision in verified),
        )
    raise ModeloCalculationRevisionSelectorNotFoundError(
        translated_message="errors.error.modelo_calculation_revision_selector_not_found",
        context={"selection": "exportable", "exportable_revision_present": False},
    )


def _revisions_for_work_unit(
    work_unit: WorkUnit,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> tuple[CalculationRevision, ...]:
    catalogue = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    return tuple(sorted(catalogue.for_work_unit(work_unit.work_unit_id), key=lambda revision: revision.created_at))


def _explicit_revision_for_work_unit(
    *,
    work_unit: WorkUnit,
    calculation_revision_id: CalculationRevisionId,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> CalculationRevision:
    catalogue = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise ModeloCalculationRevisionSelectorNotFoundError(
            translated_message="errors.error.modelo_calculation_revision_selector_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if revision.work_unit_id != work_unit.work_unit_id:
        raise ModeloCalculationRevisionSelectorStateError(
            translated_message="errors.refused.modelo_calculation_revision_selector_state",
        )
    return revision


def _revision_by_pointer(
    work_unit: WorkUnit,
    pointer_value: str | None,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
    pointer_name: str,
) -> CalculationRevision:
    revision = _optional_revision_by_pointer(
        work_unit,
        pointer_value,
        calculation_repository=calculation_repository,
    )
    if revision is None:
        raise ModeloCalculationRevisionSelectorNotFoundError(
            translated_message="errors.error.modelo_calculation_revision_selector_not_found",
            context={"selection": "pointer", "pointer_name": pointer_name},
        )
    return revision


def _optional_revision_by_pointer(
    work_unit: WorkUnit,
    pointer_value: str | None,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> CalculationRevision | None:
    if pointer_value is None:
        return None
    return _explicit_revision_for_work_unit(
        work_unit=work_unit,
        calculation_revision_id=pointer_value,
        calculation_repository=calculation_repository,
    )


def _latest_revision_with_state(
    revisions: tuple[CalculationRevision, ...],
    *,
    state: CalculationRevisionState,
) -> CalculationRevision:
    candidates = tuple(revision for revision in revisions if revision.state is state)
    if not candidates:
        raise ModeloCalculationRevisionSelectorNotFoundError(
            translated_message="errors.error.modelo_calculation_revision_selector_not_found",
            context={"selection": "state", "revision_state": state.value},
        )
    return max(candidates, key=lambda revision: (revision.created_at, revision.calculation_revision_id))


__all__ = [
    "ModeloCalculationRevisionCandidate",
    "ModeloCalculationRevisionDefault",
    "ModeloCalculationRevisionSelection",
    "ModeloCalculationRevisionSelector",
    "ModeloCalculationRevisionSelectorAmbiguousError",
    "ModeloCalculationRevisionSelectorError",
    "ModeloCalculationRevisionSelectorNotFoundError",
    "ModeloCalculationRevisionSelectorStateError",
    "resolve_modelo_calculation_revision_pick",
    "select_current_verified_revision",
    "select_exportable_revision",
    "select_modelo_calculation_revision",
]
