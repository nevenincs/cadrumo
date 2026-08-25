"""Application-level addressing for modelo work commands.

The address facade converts visible modelo/year/period filing targets and exact
work-unit ids into :class:`ModeloWorkAddress` values, resolves them through the
central selector contract, and returns the matching
:class:`~cadrumo.domain.modelos.WorkUnit` or :class:`CalculationRevision`.

This module is the application facade over the accepted addressing policy:
operators address the active bucket/profile plus modelo, filing year, and period;
raw ids remain advanced exact-addressing escape hatches. Ambiguous visible
targets, contradictory exact-id plus natural-key flags, and discarded natural-key
matches are handled by :mod:`~cadrumo.application.modelo._selectors` rather than
by CLI-local string logic.

Creation flows validate the law-determined registry revision before delegating
to :func:`~cadrumo.application.modelo.create_work_unit`; an explicit
``--revision`` is an assertion of the selected legal revision, not a free
override. Revision flows apply
:class:`~cadrumo.application.modelo.ModeloCalculationRevisionSelector`
defaults so verify, file, and export commands consume only the lifecycle states
they are allowed to handle.

See Also:
    :mod:`~cadrumo.application.modelo._selectors`:
        The authoritative visible-target and revision-selector resolver.
    :mod:`~cadrumo.entrypoints.cli._modelo`:
        CLI commands that project operator flags into this facade.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core import ActionEvidenceProvenance, Period
from ...core.identity import CalculationRevisionId, WorkUnitId
from ...core.resources import bundled_path
from ...domain.calculations.registry import (
    RegistrySnapshotError,
    RevisionId,
    load_registry_tree,
    select_revision,
)
from ...domain.contribuyente import CCAA
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloError,
    WorkUnit,
    WorkUnitState,
)
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloPreconditionErrorMixin,
)
from ._calculation_actions import get_calculation_revision
from ._preconditions import (
    build_modelo_precondition_failure_for_scenario,
    build_modelo_work_file_unverified_revision_failure,
)
from ._registry_discovery import declared_modelo_period_tokens
from ._selectors import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    resolve_modelo_calculation_revision_pick,
)
from ._work_lifecycle import RevisionParentOperation, create_work_unit, rename_work_unit, require_revision_parent_active
from .work_unit_selection import (
    ModeloWorkResolution,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    ModeloWorkUnitNotFoundError,
    resolve_active_natural_modelo_work_unit,
    resolve_modelo_work_unit,
)


class ModeloRevisionPickError(ModeloError, ValueError):
    """Raised when a calculation-revision selector is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ModeloVisibleFilingTarget:
    """Operator-visible modelo filing target under one bucket/profile.

    This is the normal user-facing address: bucket/profile plus modelo, filing
    year, and period, with an optional registry-revision assertion for
    disambiguation.
    """

    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId | None = None
    bucket_id: str | None = None

    def to_work_address(self) -> ModeloWorkAddress:
        """Project the visible target into the shared :class:`ModeloWorkAddress` shape."""
        return ModeloWorkAddress(
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            registry_revision_id=self.registry_revision_id,
            bucket_id=self.bucket_id,
        )


@dataclass(frozen=True, slots=True)
class ModeloExactWorkUnitTarget:
    """Advanced exact-addressing target for one content-addressed work unit.

    Use this only when the caller already has an authoritative ``WorkUnitId``;
    visible filing targets remain the default operator path.
    """

    work_unit_id: WorkUnitId
    bucket_id: str | None = None

    def to_work_address(self) -> ModeloWorkAddress:
        """Project the exact target into the shared :class:`ModeloWorkAddress` shape."""
        return ModeloWorkAddress(work_unit_id=self.work_unit_id, bucket_id=self.bucket_id)


@dataclass(frozen=True, slots=True)
class ModeloRevisionPick:
    """Command-specific calculation-revision pick under a resolved work target.

    ``default_for`` applies the command policy owned by
    :mod:`~cadrumo.application.modelo._selectors`: verify selects a draft, file
    selects a verified-complete revision, and export prefers the current filed
    revision before falling back to an unambiguous verified revision.
    """

    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT
    calculation_revision_id: CalculationRevisionId | None = None
    default_for: ModeloCalculationRevisionDefault | None = None

    def __post_init__(self) -> None:
        if self.selector is ModeloCalculationRevisionSelector.EXPLICIT:
            if self.calculation_revision_id is None:
                raise ModeloRevisionPickError(
                    "explicit revision picks require calculation_revision_id",
                    translated_message="application.modelo.errors.revision_pick_explicit_id_required",
                )
            return
        if self.calculation_revision_id is not None:
            raise ModeloRevisionPickError(
                "calculation_revision_id is only valid with the explicit revision selector",
                translated_message="application.modelo.errors.revision_pick_id_requires_explicit_selector",
            )

    @classmethod
    def explicit(cls, calculation_revision_id: CalculationRevisionId) -> ModeloRevisionPick:
        """Create an exact calculation-revision :class:`ModeloRevisionPick`."""
        return cls(
            selector=ModeloCalculationRevisionSelector.EXPLICIT,
            calculation_revision_id=calculation_revision_id,
        )


@dataclass(frozen=True, slots=True)
class ModeloResolvedWorkProjection:
    """Support-safe projection of a resolved modelo work target.

    The projection exposes the visible filing coordinates plus short ids for
    support guidance without making raw ids the normal operator workflow.
    """

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    state: str
    current_calculation_revision_id: CalculationRevisionId | None
    filed_calculation_revision_id: CalculationRevisionId | None
    current_filing_record_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_work_unit(cls, work_unit: WorkUnit) -> ModeloResolvedWorkProjection:
        """Project a Cadrumo work unit into a resolved-work projection.

        Converts :class:`~cadrumo.domain.modelos.WorkUnit` into
        :class:`ModeloResolvedWorkProjection`.
        """
        return cls(
            work_unit_id=work_unit.work_unit_id,
            short_work_unit_id=work_unit.work_unit_id[-12:],
            bucket_id=work_unit.bucket_id,
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            registry_revision_id=work_unit.revision_id,
            state=work_unit.state.value,
            current_calculation_revision_id=work_unit.current_calculation_revision_id,
            filed_calculation_revision_id=work_unit.filed_calculation_revision_id,
            current_filing_record_id=work_unit.current_filing_record_id,
            created_at=work_unit.created_at.isoformat(),
            updated_at=work_unit.updated_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class ModeloResolvedRevisionProjection:
    """Support-safe projection of a resolved calculation revision.

    Carries the selected revision, selector policy, lifecycle state, and short
    ids used by CLI guidance after a work target has been resolved.
    """

    calculation_revision_id: CalculationRevisionId
    short_calculation_revision_id: str
    work_unit_id: WorkUnitId
    short_work_unit_id: str
    selector: ModeloCalculationRevisionSelector
    state: str
    created_at: str
    updated_at: str
    verified_at: str | None = None
    filed_at: str | None = None

    @classmethod
    def from_revision(
        cls,
        revision: CalculationRevision,
        *,
        selector: ModeloCalculationRevisionSelector,
    ) -> ModeloResolvedRevisionProjection:
        """Project a :class:`CalculationRevision` into a :class:`ModeloResolvedRevisionProjection`."""
        return cls(
            calculation_revision_id=revision.calculation_revision_id,
            short_calculation_revision_id=revision.calculation_revision_id[-12:],
            work_unit_id=revision.work_unit_id,
            short_work_unit_id=revision.work_unit_id[-12:],
            selector=selector,
            state=revision.state.value,
            created_at=revision.created_at.isoformat(),
            updated_at=revision.updated_at.isoformat(),
            verified_at=revision.verified_at.isoformat() if revision.verified_at is not None else None,
            filed_at=revision.filed_at.isoformat() if revision.filed_at is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ModeloWorkAddress:
    """Operator-facing or exact modelo work address.

    This is the shared transport shape consumed at the application facade
    boundary. Prefer ``ModeloVisibleFilingTarget`` for model/year/period
    addressing or ``ModeloExactWorkUnitTarget`` for the advanced exact-id
    escape hatch, then project into this shape before selector resolution.
    """

    work_unit_id: WorkUnitId | None = None
    modelo: str | None = None
    filing_year: int | None = None
    period: Period | None = None
    registry_revision_id: RevisionId | None = None
    bucket_id: str | None = None

    @classmethod
    def from_visible_target(cls, target: ModeloVisibleFilingTarget) -> ModeloWorkAddress:
        """Create a :class:`ModeloWorkAddress` from a natural modelo filing target."""
        return target.to_work_address()

    @classmethod
    def from_exact_target(cls, target: ModeloExactWorkUnitTarget) -> ModeloWorkAddress:
        """Create a :class:`ModeloWorkAddress` from an exact work-unit target."""
        return target.to_work_address()


type ModeloWorkTarget = ModeloVisibleFilingTarget | ModeloExactWorkUnitTarget | ModeloWorkAddress
"""Supported work-target shapes for centralized modelo addressing."""


class ModeloWorkAddressNotFoundError(ModeloPreconditionErrorMixin, ModeloError, LookupError):
    """Raised when a natural modelo work address resolves no work unit."""


class ModeloWorkRegistryYearMismatchError(ModeloError, ValueError):
    """Raised when an explicit revision diverges from the law-determined one."""


class ModeloWorkPeriodTokenError(ModeloError, ValueError):
    """Raised when an operator-facing period token cannot be normalized."""

    def __init__(
        self,
        *,
        year: int,
        token: str,
        modelo: str | None,
        declared_tokens: tuple[str, ...],
        fallback: str | None = None,
    ) -> None:
        context = {
            "year": year,
            "token": token,
            "modelo": modelo or "",
            "tokens": ", ".join(declared_tokens),
        }
        if declared_tokens:
            super().__init__(
                context=context,
                translated_message="application.modelo.errors.work_period_token_invalid",
            )
            return
        del fallback
        super().__init__(
            context=context,
            translated_message="application.modelo.errors.work_period_token_unrecognised",
        )


@dataclass(frozen=True, slots=True)
class ModeloWorkEnsureResult:
    """Result of resolving or creating a visible-target work unit."""

    work_unit: WorkUnit
    reused: bool
    name_applied: str | None = None


def work_address_for_modelo_target(target: ModeloWorkTarget) -> ModeloWorkAddress:
    """Coerce a typed modelo work target into a :class:`ModeloWorkAddress` selector shape."""
    if isinstance(target, ModeloWorkAddress):
        return target
    if isinstance(target, ModeloVisibleFilingTarget):
        return target.to_work_address()
    return target.to_work_address()


def _modelo_work_period_from_core(year: int, period: Period, *, modelo: str | None = None) -> Period:
    """Resolve a modelo work period through the core ``Period`` value object only."""
    declared = declared_modelo_period_tokens(modelo)
    if period.filing_year != year:
        raise ModeloWorkPeriodTokenError(
            year=year,
            token=str(period),
            modelo=modelo,
            declared_tokens=declared,
        )
    return period


def modelo_work_address_from_operator_target(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None = None,
) -> ModeloWorkAddress:
    """Build a :class:`ModeloWorkAddress` from exact or visible operator input.

    A complete visible target is ``modelo`` + ``year`` + typed ``Period``. If no
    visible target is supplied, an exact ``work_unit_id`` is required. Period year
    mismatches fail here before the selector sees the request.
    """
    if modelo is not None and year is not None and period is not None:
        period = _modelo_work_period_from_core(year, period, modelo=modelo)
        year = period.filing_year
    elif work_unit_id is None:
        raise ModeloWorkAddressNotFoundError(
            "pass an exact work-unit id, or address the filing with modelo, year, and period",
        )
    return ModeloWorkAddress(
        work_unit_id=work_unit_id,
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )


def resolve_modelo_work_unit_for_operator_target(
    *,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: Period | None = None,
    registry_revision_id: RevisionId | None = None,
    bucket_id: str | None = None,
) -> WorkUnit:
    """Resolve exact or visible operator input to one active :class:`~cadrumo.domain.modelos.WorkUnit`.

    The result comes from the shared selector boundary, so ambiguity and
    exact-id/natural-key contradictions surface as typed selector errors.
    """
    return resolve_modelo_work_address_unit(
        modelo_work_address_from_operator_target(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=registry_revision_id,
            bucket_id=bucket_id,
        ),
    )


def resolve_modelo_revision_for_operator_target(
    *,
    calculation_revision_id: CalculationRevisionId | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: ModeloCalculationRevisionDefault | None = None,
) -> CalculationRevision:
    """Resolve one :class:`CalculationRevision` from exact or visible operator input.

    An explicit calculation-revision id can stand alone as the exact escape hatch.
    Otherwise the work target is resolved first and the selector/default policy is
    applied under that work unit.
    """
    address = _revision_target_address(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )
    return _resolve_revision_with_precondition_translation(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for=default_for,
    )


def _revision_target_address(
    *,
    calculation_revision_id: CalculationRevisionId | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None,
) -> ModeloWorkAddress:
    if (
        calculation_revision_id is not None
        and work_unit_id is None
        and modelo is None
        and year is None
        and period is None
        and registry_revision_id is None
        and bucket_id is None
    ):
        return ModeloWorkAddress()
    return modelo_work_address_from_operator_target(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )


def _resolve_revision_with_precondition_translation(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None,
    selector: ModeloCalculationRevisionSelector,
    default_for: ModeloCalculationRevisionDefault | None,
) -> CalculationRevision:
    try:
        return _resolve_revision_for_default(
            address=address,
            calculation_revision_id=calculation_revision_id,
            selector=selector,
            default_for=default_for,
        )
    except CalculationRevisionNotFoundError as error:
        recovery_error = _calculation_revision_work_unit_target_error(
            error=error,
            calculation_revision_id=calculation_revision_id,
            address=address,
            default_for=default_for,
        )
        if recovery_error is error:
            raise
        raise recovery_error from error
    except ModeloWorkAddressNotFoundError as error:
        precondition_error = _natural_target_absent_precondition_error(
            error=error,
            address=address,
            default_for=default_for,
        )
        if precondition_error is error:
            raise
        raise precondition_error from error
    except ModeloWorkUnitNotFoundError as error:
        precondition_error = _exact_work_unit_absent_precondition_error(
            error=error,
            address=address,
            default_for=default_for,
        )
        if precondition_error is error:
            raise
        raise precondition_error from error


def _resolve_revision_for_default(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None,
    selector: ModeloCalculationRevisionSelector,
    default_for: ModeloCalculationRevisionDefault | None,
) -> CalculationRevision:
    resolver = (
        {
            "verify": resolve_verifiable_modelo_calculation_revision_address,
            "file": resolve_fileable_modelo_calculation_revision_address,
            "export": resolve_exportable_modelo_calculation_revision_address,
        }.get(default_for)
        if default_for is not None
        else None
    )
    if resolver is None:
        resolver = resolve_modelo_calculation_revision_address
    return resolver(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
    )


def _calculation_revision_work_unit_target_error(
    *,
    error: CalculationRevisionNotFoundError,
    calculation_revision_id: CalculationRevisionId | None,
    address: ModeloWorkAddress,
    default_for: ModeloCalculationRevisionDefault | None,
) -> CalculationRevisionNotFoundError:
    """Attach the declared calculate recovery when an exact work unit was supplied."""
    if default_for == "verify":
        subject_leaf_key = "modelo.work.verify"
    elif default_for == "file":
        subject_leaf_key = "modelo.work.file"
    else:
        return error
    if calculation_revision_id is None or address != ModeloWorkAddress():
        return error
    try:
        work_unit = resolve_modelo_work_unit_for_operator_target(work_unit_id=calculation_revision_id)
    except ModeloWorkUnitNotFoundError:
        return error
    is_active = work_unit.state is WorkUnitState.BORRADOR
    scenario_id = (
        f"{subject_leaf_key}.calculation_revision.work_unit_target"
        if is_active
        else f"{subject_leaf_key}.calculation_revision.work_unit_target_discarded"
    )
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=subject_leaf_key,
        scenario_id=scenario_id,
        evidence_id=f"{subject_leaf_key}.calculation_revision.addressing",
        evidence_values={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "work_unit_state": work_unit.state.value,
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"work_unit_id": work_unit.work_unit_id} if is_active else None,
    )
    return CalculationRevisionNotFoundError(
        translated_message=(
            "application.modelo.errors.calculation_revision_id_is_work_unit"
            if is_active
            else "application.modelo.errors.calculation_revision_id_is_discarded_work_unit"
        ),
        context={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "work_unit_state": work_unit.state.value,
        },
        precondition_failure=failure,
    )


def _natural_target_absent_precondition_error(
    *,
    error: ModeloWorkAddressNotFoundError,
    address: ModeloWorkAddress,
    default_for: ModeloCalculationRevisionDefault | None,
) -> ModeloWorkAddressNotFoundError:
    """Attach the declared no-action verdict to an absent natural verify/file target."""
    subject_leaf_key = _natural_target_subject_leaf_key(default_for)
    if subject_leaf_key is None or not _natural_target_is_addressed(address):
        return error
    assert address.modelo is not None
    assert address.filing_year is not None
    assert address.period is not None
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=subject_leaf_key,
        scenario_id=f"{subject_leaf_key}.work_address.natural_target_absent",
        evidence_id=f"{subject_leaf_key}.work_address.addressing",
        evidence_values={
            "modelo": address.modelo,
            "filing_year": address.filing_year,
            "period": address.period.registry_token,
            "registry_revision_id": address.registry_revision_id or "",
            "bucket_id": address.bucket_id or "",
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
    return ModeloWorkAddressNotFoundError(
        str(error),
        translated_message="errors.error.modelo_work_address_not_found",
        context={
            "modelo": address.modelo,
            "filing_year": address.filing_year,
            "period": address.period.registry_token,
            "registry_revision_id": address.registry_revision_id or "",
            "bucket_id": address.bucket_id or "",
        },
        precondition_failure=failure,
    )


def _natural_target_subject_leaf_key(default_for: ModeloCalculationRevisionDefault | None) -> str | None:
    if default_for == "verify":
        return "modelo.work.verify"
    if default_for == "file":
        return "modelo.work.file"
    return None


def _natural_target_is_addressed(address: ModeloWorkAddress) -> bool:
    return (
        address.work_unit_id is None
        and address.modelo is not None
        and address.filing_year is not None
        and address.period is not None
    )


def _exact_work_unit_absent_precondition_error(
    *,
    error: ModeloWorkUnitNotFoundError,
    address: ModeloWorkAddress,
    default_for: ModeloCalculationRevisionDefault | None,
) -> ModeloWorkAddressNotFoundError | ModeloWorkUnitNotFoundError:
    """Attach the declared no-action verdict to an absent exact verify/file work-unit target."""
    if default_for == "verify":
        subject_leaf_key = "modelo.work.verify"
    elif default_for == "file":
        subject_leaf_key = "modelo.work.file"
    else:
        return error
    if address.work_unit_id is None:
        return error
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=subject_leaf_key,
        scenario_id=f"{subject_leaf_key}.work_address.exact_work_unit_absent",
        evidence_id=f"{subject_leaf_key}.work_address.addressing",
        evidence_values={
            "work_unit_id": address.work_unit_id,
            "bucket_id": address.bucket_id or "",
            "selector_kind": "work_unit_id",
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
    return ModeloWorkAddressNotFoundError(
        str(error),
        translated_message="errors.error.modelo_work_address_not_found",
        context={
            "work_unit_id": address.work_unit_id,
            "bucket_id": address.bucket_id or "",
            "selector_kind": "work_unit_id",
        },
        precondition_failure=failure,
    )


def resolve_modelo_work_target(target: ModeloWorkTarget) -> ModeloWorkResolution:
    """Resolve any supported modelo target through the shared selector boundary.

    Returns a :class:`ModeloWorkResolution` containing the resolved work unit or
    typed absence/ambiguity metadata from :mod:`~cadrumo.application.modelo._selectors`.
    """
    return resolve_modelo_work_address(work_address_for_modelo_target(target))


def resolve_modelo_work_unit_id(target: ModeloWorkTarget) -> WorkUnitId:
    """Resolve a visible or exact modelo target to the authoritative work-unit id."""
    resolution = resolve_modelo_work_target(target)
    assert resolution.work_unit is not None
    return resolution.work_unit.work_unit_id


def project_modelo_work_unit(work_unit: WorkUnit) -> ModeloResolvedWorkProjection:
    """Project an internal work unit into the visible :class:`ModeloResolvedWorkProjection` addressing contract."""
    return ModeloResolvedWorkProjection.from_work_unit(work_unit)


def project_modelo_work_target(target: ModeloWorkTarget) -> ModeloResolvedWorkProjection:
    """Resolve a target and project it back to a :class:`ModeloResolvedWorkProjection`."""
    resolution = resolve_modelo_work_target(target)
    assert resolution.work_unit is not None
    return project_modelo_work_unit(resolution.work_unit)


def resolve_registry_revision_for_work_target(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
) -> str:
    """Resolve and validate the registry revision for a visible filing target.

    When ``registry_revision_id`` is ``None`` the law-determined revision for
    ``(modelo, filing_year, period)`` is returned unconditionally.

    When ``registry_revision_id`` is supplied it is treated as an
    *assertion parameter* (per :func:`~cadrumo.domain.calculations.registry._temporal.select_revision`):
    an explicit ``--revision`` is accepted only when it names exactly the revision
    that ``select_revision`` would pick from ``(filing_year, period)`` alone.  If
    the supplied id diverges from the law-determined revision the call refuses with
    an instructive error naming both the requested and the law-determined revision
    and stating that the binding is fixed by law (per the CLI-boundary
    instructive-refusal mandate in ``aeat-architecture-boundaries``).

    ``--revision`` is thereby demoted from a free override to an
    idempotence/assertion handle, mirroring the same shape used by
    ``preflight --revision-id``.

    Returns:
        The revision id selected by
        :func:`~cadrumo.domain.calculations.registry._temporal.select_revision`.

    Raises:
        ModeloWorkRegistryYearMismatchError: The supplied revision id is not the
            law-determined revision for the visible filing period.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    stripped_modelo = modelo.strip()
    definition = next((candidate for candidate in modelos if candidate.id == stripped_modelo), None)
    if definition is None:
        raise RegistrySnapshotError(f"modelo {stripped_modelo!r} is not present in the calculation registry")
    if registry_revision_id is None:
        return select_revision(definition, filing_year=filing_year, period=period.registry_token).id
    revision_id = registry_revision_id.strip()
    try:
        # Delegate the assertion to select_revision itself.  Within a valid
        # registry the non-overlap gate guarantees uniqueness, so narrowing by
        # an id that genuinely covers (filing_year, period) returns the same
        # revision the unconstrained call would; narrowing by any other id raises
        # RegistrySnapshotError.  This makes the structural property do the work
        # instead of re-implementing a weaker year-only coverage check.
        select_revision(definition, filing_year=filing_year, period=period.registry_token, revision_id=revision_id)
    except RegistrySnapshotError:
        # Determine the law-determined revision for a clear instructive message.
        try:
            law_revision = select_revision(definition, filing_year=filing_year, period=period.registry_token)
            law_id = law_revision.id
        except RegistrySnapshotError:
            law_id = "<no revision found for this period>"
        raise ModeloWorkRegistryYearMismatchError(
            f"registry revision {revision_id!r} is not the law-determined revision for "
            f"modelo {modelo.strip()!r} {filing_year} {period.registry_token!r}. "
            f"The law-determined revision is {law_id!r}. "
            f"The period-to-revision binding is fixed by law (AEAT orden ministerial); "
            f"you cannot override it. Re-create the work unit without --revision to use "
            f"the correct revision, or omit --revision to accept the law-determined default.",
        ) from None
    return revision_id


def ensure_modelo_work_unit_for_active_target(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
    name: str | None = None,
    actor: str = "operator",
    causante_ccaa: CCAA | None = None,
    enforce_applicability: bool = True,
) -> ModeloWorkEnsureResult:
    """Resume or create the active work unit for one visible filing target.

    The visible target is resolved first. If one active unit exists, it is reused
    after profile-readiness validation and optional rename. If none exists, the
    law-determined registry revision is selected and a work unit is created.

    Returns:
        A :class:`ModeloWorkEnsureResult` marking whether the unit was reused or
        newly created.
    """
    requested_revision = registry_revision_id.strip() if registry_revision_id is not None else None
    resolution = resolve_active_natural_modelo_work_unit(
        ModeloWorkSelectorRequest(
            bucket_id=bucket_id,
            modelo=ModeloCode(modelo),
            filing_year=filing_year,
            period=period,
            revision_id=requested_revision,
        ),
    )
    if resolution.work_unit is not None:
        unit = resolution.work_unit
        from ._profile_readiness_gate import require_profile_ready_for_work_unit

        require_profile_ready_for_work_unit(unit, enforce_applicability=enforce_applicability)
        name_applied: str | None = None
        if name is not None and name.strip() and name.strip() != unit.name:
            unit = rename_work_unit(unit.work_unit_id, name, actor=actor)
            name_applied = unit.name
        return ModeloWorkEnsureResult(work_unit=unit, reused=True, name_applied=name_applied)

    revision_id = resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=requested_revision,
    )
    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=name,
        actor=actor,
        causante_ccaa=causante_ccaa,
        enforce_applicability=enforce_applicability,
    )
    return ModeloWorkEnsureResult(work_unit=unit, reused=False)


def resolve_modelo_work_address(address: ModeloWorkAddress) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address to a required :class:`ModeloWorkResolution`."""
    resolution = resolve_optional_modelo_work_address(address)
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise ModeloWorkAddressNotFoundError(
            translated_message="errors.error.modelo_work_address_not_found",
            context={"work_unit_present": False},
        )
    return resolution


def resolve_optional_modelo_work_address(address: ModeloWorkAddress) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address to a :class:`ModeloWorkResolution`."""
    resolution = resolve_modelo_work_unit(
        ModeloWorkSelectorRequest(
            work_unit_id=address.work_unit_id,
            modelo=ModeloCode(address.modelo) if address.modelo is not None else None,
            filing_year=address.filing_year,
            period=address.period,
            revision_id=address.registry_revision_id,
            bucket_id=address.bucket_id,
        ),
    )
    return resolution


def resolve_modelo_work_address_unit(address: ModeloWorkAddress) -> WorkUnit:
    """Resolve an operator-facing modelo work address to one :class:`~cadrumo.domain.modelos.WorkUnit`."""
    resolution = resolve_modelo_work_address(address)
    assert resolution.work_unit is not None
    return resolution.work_unit


def resolve_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: ModeloCalculationRevisionDefault | None = None,
) -> CalculationRevision:
    """Resolve a :class:`CalculationRevision` by exact id or under a modelo work address.

    ``default_for`` applies the command-specific selector default after the work
    unit is resolved. A bare exact calculation-revision id bypasses work-address
    resolution and loads the revision directly.  For verify and file only, a
    positional exact token that names a persisted work unit is reconciled through
    that unit's current-revision pointer.  This is not an alternate CLI grammar:
    it closes the application-owned recovery edge where the exact persisted
    identity initially has no calculation revision, calculation creates the
    current revision, and the unchanged original invocation must then address it.
    """
    if calculation_revision_id is not None and address == ModeloWorkAddress():
        revision = _resolve_exact_calculation_revision_or_current_work_unit_revision(
            calculation_revision_id=calculation_revision_id,
            default_for=default_for,
        )
        return _require_revision_parent_admitted_for_operation(revision, default_for=default_for)

    work_unit = resolve_modelo_work_address_unit(address)
    revision = resolve_modelo_calculation_revision_pick(
        work_unit,
        selector=selector,
        calculation_revision_id=calculation_revision_id,
        default_for=default_for,
    ).revision
    return _require_revision_parent_admitted_for_operation(revision, default_for=default_for)


def _resolve_exact_calculation_revision_or_current_work_unit_revision(
    *,
    calculation_revision_id: CalculationRevisionId,
    default_for: ModeloCalculationRevisionDefault | None,
) -> CalculationRevision:
    """Resolve an exact revision, or a current revision reached through its work unit.

    ``work verify`` and ``work file`` have an existing, declared recovery for a
    positional identifier which proves to be a work-unit id: calculate that unit.
    Before calculation the unit has no current revision and the original lookup
    must keep that verdict.  Afterwards, resolving the current pointer here makes
    the exact same operator invocation executable.  A discarded parent remains
    deliberately unresolved so the existing terminal profile is projected by the
    caller's typed error path.
    """
    try:
        return get_calculation_revision(calculation_revision_id)
    except CalculationRevisionNotFoundError as revision_error:
        if default_for not in {"verify", "file"}:
            raise
        try:
            work_unit = resolve_modelo_work_unit_for_operator_target(work_unit_id=calculation_revision_id)
        except ModeloWorkUnitNotFoundError:
            raise revision_error from None
        if work_unit.state is not WorkUnitState.BORRADOR or work_unit.current_calculation_revision_id is None:
            raise revision_error from None
        return get_calculation_revision(work_unit.current_calculation_revision_id)


def _require_revision_parent_admitted_for_operation(
    revision: CalculationRevision,
    *,
    default_for: ModeloCalculationRevisionDefault | None,
) -> CalculationRevision:
    """Refuse verify/file when a resolved revision belongs to a discarded work unit."""
    if default_for == "verify":
        operation = RevisionParentOperation.VERIFY
    elif default_for == "file":
        operation = RevisionParentOperation.FILE
    else:
        return revision
    work_unit = resolve_modelo_work_unit_for_operator_target(work_unit_id=revision.work_unit_id)
    require_revision_parent_active(
        work_unit=work_unit,
        calculation_revision_id=revision.calculation_revision_id,
        operation=operation,
    )
    return revision


def resolve_modelo_revision_pick(
    *,
    target: ModeloWorkTarget,
    pick: ModeloRevisionPick | None = None,
) -> ModeloResolvedRevisionProjection:
    """Resolve and project a revision selection as :class:`ModeloResolvedRevisionProjection`."""
    if pick is None:
        pick = ModeloRevisionPick()
    work_unit = resolve_modelo_work_address_unit(work_address_for_modelo_target(target))
    selection = resolve_modelo_calculation_revision_pick(
        work_unit,
        selector=pick.selector,
        calculation_revision_id=pick.calculation_revision_id,
        default_for=pick.default_for,
    )
    return ModeloResolvedRevisionProjection.from_revision(selection.revision, selector=selection.selector)


def _require_revision_state(
    revision: CalculationRevision,
    *,
    allowed: tuple[CalculationRevisionState, ...],
    purpose: str,
) -> CalculationRevision:
    if revision.state not in allowed:
        allowed_values = ", ".join(state.value for state in allowed)
        raise ModeloCalculationRevisionSelectorStateError(
            f"selected revision {revision.calculation_revision_id!r} is in state "
            f"{revision.state.value!r}; {purpose} requires {allowed_values}",
        )
    return revision


def resolve_verifiable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the :class:`CalculationRevision` that ``work verify`` addresses.

    Returns the resolved revision in ANY lifecycle state; no draft gate is
    applied here. Verification-state policy is owned by
    :func:`~cadrumo.application.modelo.verify_modelo_revision` under
    ``aeat-cli-contract``: a revision already out of
    ``BORRADOR`` that carries a granting :class:`VerificationReport` collapses to
    that existing report as an idempotent no-op, and the hard refusal is reserved
    for the inconsistent non-draft/no-granting-report state. Gating ``BORRADOR``
    here would refuse the idempotent retry before the collapse could fire.
    """
    return resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="verify",
    )


def resolve_fileable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the verified-complete :class:`CalculationRevision` that ``work file`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="file",
    )
    if revision.state is CalculationRevisionState.VERIFICADO_COMPLETO:
        return revision
    work_unit = resolve_modelo_work_unit_for_operator_target(work_unit_id=revision.work_unit_id)
    raise CalculationRevisionStateError(
        translated_message="errors.error.error_modelo_calculation_revision_state",
        context={"calculation_revision_id": revision.calculation_revision_id, "state": revision.state.value},
        precondition_failure=build_modelo_work_file_unverified_revision_failure(
            calculation_revision_id=revision.calculation_revision_id,
            state=revision.state.value,
            work_unit=work_unit,
        ),
    )


def resolve_exportable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the filed or verified-complete :class:`CalculationRevision` that ``modelo export`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="export",
    )
    return _require_revision_state(
        revision,
        allowed=(
            CalculationRevisionState.VERIFICADO_COMPLETO,
            CalculationRevisionState.PRESENTADO,
        ),
        purpose="export",
    )


__all__ = [
    "ModeloCalculationRevisionSelector",
    "ModeloCalculationRevisionSelectorAmbiguousError",
    "ModeloCalculationRevisionSelectorNotFoundError",
    "ModeloCalculationRevisionSelectorStateError",
    "ModeloExactWorkUnitTarget",
    "ModeloResolvedRevisionProjection",
    "ModeloResolvedWorkProjection",
    "ModeloRevisionPick",
    "ModeloRevisionPickError",
    "ModeloVisibleFilingTarget",
    "ModeloWorkAddress",
    "ModeloWorkAddressNotFoundError",
    "ModeloWorkEnsureResult",
    "ModeloWorkPeriodTokenError",
    "ModeloWorkRegistryYearMismatchError",
    "ModeloWorkTarget",
    "ensure_modelo_work_unit_for_active_target",
    "modelo_work_address_from_operator_target",
    "project_modelo_work_target",
    "project_modelo_work_unit",
    "resolve_exportable_modelo_calculation_revision_address",
    "resolve_fileable_modelo_calculation_revision_address",
    "resolve_modelo_calculation_revision_address",
    "resolve_modelo_revision_for_operator_target",
    "resolve_modelo_revision_pick",
    "resolve_modelo_work_address",
    "resolve_modelo_work_address_unit",
    "resolve_modelo_work_target",
    "resolve_modelo_work_unit_for_operator_target",
    "resolve_modelo_work_unit_id",
    "resolve_optional_modelo_work_address",
    "resolve_registry_revision_for_work_target",
    "resolve_verifiable_modelo_calculation_revision_address",
    "work_address_for_modelo_target",
]
