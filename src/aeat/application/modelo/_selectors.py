"""Selector policy for operator-facing modelo work targets.

Visible modelo/year/period input is normalized into a
:class:`ModeloWorkSelectorRequest` and resolved to a
:class:`ModeloWorkResolution` over active
:class:`aeat.domain.modelos.WorkUnit` records. Revision selectors
then load persisted :class:`CalculationRevision` rows and return a
:class:`ModeloCalculationRevisionSelection` for current, latest draft, latest
verified, filed, or explicit-id picks.

The selector boundary implements the accepted visible-target addressing policy:
the common operator target is active bucket/profile plus modelo, filing year,
and period; raw work-unit and calculation-revision ids remain exact-addressing
escape hatches. An explicit work-unit id is validated against any natural-key
flags supplied beside it, discarded work units are ignored by default, and an
ambiguous visible target refuses with candidate guidance instead of guessing.

Command-specific revision defaults stay here rather than in CLI modules:
verification selects the current draft, filing selects the current
verified-complete revision, and export prefers the current filed revision before
falling back to an unambiguous verified-complete revision.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ...core import STRICT_FROZEN_CONFIG, Period, resolve_active_bucket_id
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._errors import ModeloError, ModeloValidationError
from ...domain.modelos._ids import CalculationRevisionId, WorkUnitId
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._work_unit import WorkUnit, WorkUnitState

_BucketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_RevisionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ModeloWorkSelectorState(StrEnum):
    """Resolution state for a visible modelo filing target."""

    ABSENT = "absent"
    RESOLVED = "resolved"


class ModeloCalculationRevisionSelector(StrEnum):
    """Closed selector set for calculation revisions under a work unit."""

    CURRENT = "current"
    LATEST_DRAFT = "latest-draft"
    LATEST_VERIFIED = "latest-verified"
    FILED = "filed"
    EXPLICIT = "explicit"


class ModeloVerifySelector(StrEnum):
    """Draft-reachable selector subset accepted by ``modelo work verify``.

    ``verify_modelo_revision`` refuses any revision not in state ``BORRADOR``,
    so the only selectors that can resolve to a verifiable revision are the ones
    that reach a draft: ``current`` (when the current revision is still a draft),
    ``latest-draft``, and ``explicit`` (an explicitly-named draft revision id).
    The post-draft selectors ``latest-verified`` and ``filed`` on the full
    :class:`ModeloCalculationRevisionSelector` name states verify rejects, so
    advertising them on the verify command is an advertised-but-impossible
    combination (audit ``2026-06-10-cli-operator-surface-audit`` F5(d), decision
    D5). This narrowed enum is what the verify ``--select`` option advertises;
    other commands keep the full selector enum.
    """

    CURRENT = "current"
    LATEST_DRAFT = "latest-draft"
    EXPLICIT = "explicit"

    def to_calculation_revision_selector(self) -> ModeloCalculationRevisionSelector:
        """Map a verify selector to its :class:`ModeloCalculationRevisionSelector` member."""
        return ModeloCalculationRevisionSelector(self.value)


class ModeloWorkSelectorError(ModeloError):
    """Base error for modelo work selector refusals."""


class ModeloWorkNoActiveBucketError(ModeloWorkSelectorError):
    """Raised when a selector requires the active bucket but none is selected."""


class ModeloWorkUnitNotFoundError(ModeloWorkSelectorError, KeyError):
    """Raised when an explicit work-unit id does not exist."""


class ModeloWorkSelectorContradictionError(ModeloWorkSelectorError, ValueError):
    """Raised when explicit id and natural-key flags address different work."""


class ModeloWorkVisibleTargetAmbiguousError(ModeloWorkSelectorError):
    """Raised when a visible target matches multiple active work units."""

    def __init__(self, candidates: tuple[ModeloWorkUnitCandidate, ...]) -> None:
        self.candidates = candidates
        super().__init__(
            "modelo work target is ambiguous; choose a registry revision or explicit work_unit_id",
        )


class ModeloWorkRevisionConflictError(ModeloWorkSelectorError):
    """Raised when the requested registry revision conflicts with active work."""

    def __init__(
        self,
        *,
        requested_revision_id: str,
        existing: ModeloWorkUnitCandidate,
    ) -> None:
        self.requested_revision_id = requested_revision_id
        self.existing = existing
        super().__init__(
            "modelo work target already has an active work unit for a different registry revision",
        )


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


class ModeloWorkSelectorRequest(BaseModel):
    """Operator-facing modelo work selector.

    ``bucket_id`` is optional so callers can address the active profile
    bucket by default. ``work_unit_id`` is the exact-addressing escape hatch;
    when present, any natural-key flags supplied alongside it are validated
    against the loaded work unit.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode | None = None
    filing_year: Annotated[int, Field(ge=2000, le=2099)] | None = None
    period: Period | None = None
    revision_id: _RevisionId | None = None
    bucket_id: _BucketId | None = None
    work_unit_id: WorkUnitId | None = None

    @field_validator("modelo", mode="before")
    @classmethod
    def _coerce_modelo(cls, value: object) -> ModeloCode | None:
        if value is None or isinstance(value, ModeloCode):
            return value
        if isinstance(value, str):
            return ModeloCode(value)
        raise ModeloValidationError(f"expected ModeloCode or str, got {type(value).__name__}")

    @field_validator("revision_id", "bucket_id")
    @classmethod
    def _normalise_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @property
    def has_visible_target(self) -> bool:
        """Return whether modelo/year/period were all supplied."""
        return self.modelo is not None and self.filing_year is not None and self.period is not None


class ModeloWorkUnitCandidate(BaseModel):
    """Human-readable candidate metadata for selector guidance."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: _BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    period: Period
    revision_id: _RevisionId
    state: WorkUnitState
    current_calculation_revision_id: str | None = None
    filed_calculation_revision_id: str | None = None
    current_filing_record_id: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_work_unit(cls, unit: WorkUnit) -> ModeloWorkUnitCandidate:
        """Project a work unit into a :class:`ModeloWorkUnitCandidate` selector guidance record."""
        return cls(
            work_unit_id=unit.work_unit_id,
            short_work_unit_id=unit.work_unit_id[-12:],
            bucket_id=unit.bucket_id,
            modelo=unit.modelo,
            filing_year=unit.filing_year,
            period=unit.period,
            revision_id=unit.revision_id,
            state=unit.state,
            current_calculation_revision_id=unit.current_calculation_revision_id,
            filed_calculation_revision_id=unit.filed_calculation_revision_id,
            current_filing_record_id=unit.current_filing_record_id,
            created_at=unit.created_at.isoformat(),
            updated_at=unit.updated_at.isoformat(),
        )


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


class ModeloWorkResolution(BaseModel):
    """Resolved selector outcome for a visible modelo filing target."""

    model_config = STRICT_FROZEN_CONFIG

    state: ModeloWorkSelectorState
    bucket_id: _BucketId
    modelo: ModeloCode | None = None
    filing_year: Annotated[int, Field(ge=2000, le=2099)] | None = None
    period: Period | None = None
    requested_revision_id: _RevisionId | None = None
    work_unit: WorkUnit | None = None
    candidates: tuple[ModeloWorkUnitCandidate, ...] = ()


def resolve_modelo_work_bucket(request: ModeloWorkSelectorRequest) -> str:
    """Resolve the selector bucket from an explicit id or the active profile."""
    if request.bucket_id is not None:
        return request.bucket_id
    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloWorkNoActiveBucketError("modelo work selector requires an active profile bucket")
    return active_bucket_id


def visible_target_work_units(
    request: ModeloWorkSelectorRequest,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> tuple[WorkUnit, ...]:
    """Return active :class:`aeat.domain.modelos.WorkUnit` records matching the visible target.

    The visible target is bucket/modelo/filing-year/period only. Registry
    revision is intentionally not part of this lookup so a conflicting
    ``revision_id`` can be reported as a conflict against the existing active
    work unit instead of silently selecting or creating a second target.
    """
    if not request.has_visible_target:
        raise ModeloWorkSelectorContradictionError("modelo, filing_year, and period are required for natural lookup")
    bucket_id = resolve_modelo_work_bucket(request)
    catalogue = (repository or WorkUnitCatalogueRepository(bucket_id=bucket_id)).load()
    modelo = request.modelo
    filing_year = request.filing_year
    period = request.period
    return tuple(
        sorted(
            (
                unit
                for unit in catalogue.values()
                if unit.state is not WorkUnitState.DESCARTADO
                and unit.bucket_id == bucket_id
                and unit.modelo == modelo
                and unit.filing_year == filing_year
                and unit.period == period
            ),
            key=lambda unit: (unit.revision_id, unit.created_at, unit.work_unit_id),
        ),
    )


def resolve_modelo_work_unit(
    request: ModeloWorkSelectorRequest,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> ModeloWorkResolution:
    """Resolve one work unit and return a :class:`ModeloWorkResolution` by exact id or visible target.

    The visible-target path deliberately searches by bucket/modelo/year/period
    before registry-revision exact targeting. That prevents a command from
    silently creating or selecting a second active work unit for the same filing.
    """
    bucket_id = resolve_modelo_work_bucket(request)
    repo = repository or WorkUnitCatalogueRepository(bucket_id=bucket_id)
    catalogue = repo.load()

    if request.work_unit_id is not None:
        work_unit = catalogue.get(request.work_unit_id)
        if work_unit is None:
            raise ModeloWorkUnitNotFoundError(f"no modelo work unit found with id={request.work_unit_id}")
        _validate_explicit_work_unit_matches_request(work_unit, request, resolved_bucket_id=bucket_id)
        return ModeloWorkResolution(
            state=ModeloWorkSelectorState.RESOLVED,
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            requested_revision_id=request.revision_id,
            work_unit=work_unit,
            candidates=(ModeloWorkUnitCandidate.from_work_unit(work_unit),),
        )

    matches = visible_target_work_units(request, repository=repo)
    if not matches:
        return ModeloWorkResolution(
            state=ModeloWorkSelectorState.ABSENT,
            bucket_id=bucket_id,
            modelo=request.modelo,
            filing_year=request.filing_year,
            period=request.period,
            requested_revision_id=request.revision_id,
        )
    if len(matches) > 1:
        raise ModeloWorkVisibleTargetAmbiguousError(
            tuple(ModeloWorkUnitCandidate.from_work_unit(unit) for unit in matches),
        )

    assert len(matches) == 1
    work_unit = matches[0]
    if request.revision_id is not None and request.revision_id != work_unit.revision_id:
        raise ModeloWorkRevisionConflictError(
            requested_revision_id=request.revision_id,
            existing=ModeloWorkUnitCandidate.from_work_unit(work_unit),
        )
    return ModeloWorkResolution(
        state=ModeloWorkSelectorState.RESOLVED,
        bucket_id=bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        requested_revision_id=request.revision_id,
        work_unit=work_unit,
        candidates=(ModeloWorkUnitCandidate.from_work_unit(work_unit),),
    )


def _validate_explicit_work_unit_matches_request(
    work_unit: WorkUnit,
    request: ModeloWorkSelectorRequest,
    *,
    resolved_bucket_id: str,
) -> None:
    expected: tuple[tuple[str, object | None, object], ...] = (
        ("bucket_id", resolved_bucket_id, work_unit.bucket_id),
        ("modelo", request.modelo, work_unit.modelo),
        ("filing_year", request.filing_year, work_unit.filing_year),
        ("period", request.period, work_unit.period),
        ("revision_id", request.revision_id, work_unit.revision_id),
    )
    for field_name, supplied, actual in expected:
        if supplied is not None and supplied != actual:
            raise ModeloWorkSelectorContradictionError(
                f"explicit work_unit_id {work_unit.work_unit_id} has {field_name}={actual!r}, "
                f"but selector supplied {field_name}={supplied!r}",
            )


def select_modelo_calculation_revision(
    work_unit: WorkUnit,
    *,
    selector: ModeloCalculationRevisionSelector,
    calculation_revision_id: str | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationRevisionSelection:
    """Select one persisted calculation revision as :class:`ModeloCalculationRevisionSelection`.

    ``EXPLICIT`` requires ``calculation_revision_id`` and verifies the revision
    belongs to the supplied :class:`aeat.domain.modelos.WorkUnit`. Non-explicit
    selectors resolve through the work unit's current/filed pointers or by
    latest state, and refuse missing or mismatched state instead of falling back
    to another revision.
    """
    revisions = _revisions_for_work_unit(work_unit, calculation_repository=calculation_repository)
    if selector is ModeloCalculationRevisionSelector.EXPLICIT:
        if calculation_revision_id is None:
            raise ModeloCalculationRevisionSelectorNotFoundError("explicit revision selection requires an id")
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
            "calculation_revision_id is only accepted with the explicit revision selector",
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
    calculation_revision_id: str | None = None,
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
    if default_for == "verify" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_current_draft_revision(work_unit, calculation_repository=calculation_repository)
    if default_for == "file" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_current_verified_revision(work_unit, calculation_repository=calculation_repository)
    if default_for == "export" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_exportable_revision(work_unit, calculation_repository=calculation_repository)
    return select_modelo_calculation_revision(
        work_unit,
        selector=selector,
        calculation_repository=calculation_repository,
    )


def select_current_draft_revision(
    work_unit: WorkUnit,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationRevisionSelection:
    """Select the current draft revision as a :class:`ModeloCalculationRevisionSelection` for verification."""
    selection = select_modelo_calculation_revision(
        work_unit,
        selector=ModeloCalculationRevisionSelector.CURRENT,
        calculation_repository=calculation_repository,
    )
    if selection.revision.state is not CalculationRevisionState.BORRADOR:
        raise ModeloCalculationRevisionSelectorStateError(
            f"current revision {selection.revision.calculation_revision_id!r} is in state "
            f"{selection.revision.state.value!r}; verification requires a draft revision",
        )
    return selection


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
            f"current revision {selection.revision.calculation_revision_id!r} is in state "
            f"{selection.revision.state.value!r}; filing requires a verified-complete revision",
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
                "current revision is still draft; verify it before exporting or select a verified revision explicitly",
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
    raise ModeloCalculationRevisionSelectorNotFoundError("no exportable verified or filed revision exists")


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
    calculation_revision_id: str,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> CalculationRevision:
    catalogue = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise ModeloCalculationRevisionSelectorNotFoundError(
            f"no calculation revision found with id={calculation_revision_id}",
        )
    if revision.work_unit_id != work_unit.work_unit_id:
        raise ModeloCalculationRevisionSelectorStateError(
            f"calculation revision {calculation_revision_id} belongs to work_unit_id={revision.work_unit_id}, "
            f"not {work_unit.work_unit_id}",
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
        raise ModeloCalculationRevisionSelectorNotFoundError(f"work unit has no selectable {pointer_name}")
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
        raise ModeloCalculationRevisionSelectorNotFoundError(f"no calculation revision in state {state.value!r}")
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
    "ModeloVerifySelector",
    "ModeloWorkNoActiveBucketError",
    "ModeloWorkResolution",
    "ModeloWorkRevisionConflictError",
    "ModeloWorkSelectorContradictionError",
    "ModeloWorkSelectorError",
    "ModeloWorkSelectorRequest",
    "ModeloWorkSelectorState",
    "ModeloWorkUnitCandidate",
    "ModeloWorkUnitNotFoundError",
    "ModeloWorkVisibleTargetAmbiguousError",
    "resolve_modelo_calculation_revision_pick",
    "resolve_modelo_work_bucket",
    "resolve_modelo_work_unit",
    "select_current_draft_revision",
    "select_current_verified_revision",
    "select_exportable_revision",
    "select_modelo_calculation_revision",
    "visible_target_work_units",
]
