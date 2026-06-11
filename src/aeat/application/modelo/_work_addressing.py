"""Application-level addressing for modelo work CLI consumers.

Use of :class:`CalculationRevision` for compliance.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core import Period
from ...core.resources import resources
from ...domain.calculations.registry._errors import RegistrySnapshotError
from ...domain.calculations.registry._temporal import select_revision
from ...domain.contribuyente import CCAA
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._ids import CalculationRevisionId, WorkUnitId
from ...domain.modelos._work_unit import WorkUnit
from ._calculation_actions import get_calculation_revision
from ._registry_discovery import declared_modelo_period_tokens
from ._selectors import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloWorkResolution,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    resolve_modelo_calculation_revision_pick,
    resolve_modelo_work_unit,
)
from ._work_lifecycle import create_work_unit, rename_work_unit


class ModeloRevisionPickError(ModeloError, ValueError):
    """Raised when a calculation-revision selector is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ModeloVisibleFilingTarget:
    """Operator-visible modelo filing target under one bucket/profile."""

    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: str | None = None
    bucket_id: str | None = None

    def to_work_address(self) -> ModeloWorkAddress:
        """Project the visible target into the legacy-compatible :class:`ModeloWorkAddress` shape."""
        return ModeloWorkAddress(
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            registry_revision_id=self.registry_revision_id,
            bucket_id=self.bucket_id,
        )


@dataclass(frozen=True, slots=True)
class ModeloExactWorkUnitTarget:
    """Advanced exact-addressing target for one content-addressed work unit."""

    work_unit_id: WorkUnitId
    bucket_id: str | None = None

    def to_work_address(self) -> ModeloWorkAddress:
        """Project the exact target into the legacy-compatible :class:`ModeloWorkAddress` shape."""
        return ModeloWorkAddress(work_unit_id=self.work_unit_id, bucket_id=self.bucket_id)


@dataclass(frozen=True, slots=True)
class ModeloRevisionPick:
    """Command-specific calculation-revision pick under a resolved work target."""

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
    """Support-safe projection of a resolved modelo work target."""

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: str
    state: str
    current_calculation_revision_id: CalculationRevisionId | None
    filed_calculation_revision_id: CalculationRevisionId | None
    current_filing_record_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_work_unit(cls, work_unit: WorkUnit) -> ModeloResolvedWorkProjection:
        """Project an internal :class:`WorkUnit` into a :class:`ModeloResolvedWorkProjection`."""
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
    """Support-safe projection of a resolved calculation revision."""

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
        """Project an internal calculation revision into a :class:`ModeloResolvedRevisionProjection` support metadata.

        Use of :class:`CalculationRevision` for compliance.
        """
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

    This is the legacy-compatible transport shape consumed by existing
    callers. New code should prefer ``ModeloVisibleFilingTarget`` for
    model/year/period addressing or ``ModeloExactWorkUnitTarget`` for
    the advanced exact-id escape hatch, then project into this shape at
    the application facade boundary.
    """

    work_unit_id: WorkUnitId | None = None
    modelo: str | None = None
    filing_year: int | None = None
    period: Period | None = None
    registry_revision_id: str | None = None
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


class ModeloWorkAddressNotFoundError(ModeloError, LookupError):
    """Raised when a natural modelo work address resolves no active work unit."""


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
    if isinstance(target, ModeloExactWorkUnitTarget):
        return target.to_work_address()
    raise TypeError(f"expected modelo work target, got {type(target).__name__}")


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
    registry_revision_id: str | None,
    bucket_id: str | None = None,
) -> ModeloWorkAddress:
    """Build a :class:`ModeloWorkAddress` from exact or visible operator input."""
    if modelo is not None and year is not None and period is not None:
        period = _modelo_work_period_from_core(year, period, modelo=modelo)
        year = period.year
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
    registry_revision_id: str | None = None,
    bucket_id: str | None = None,
) -> WorkUnit:
    """Resolve exact or visible operator input to one active :class:`WorkUnit`."""
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
    calculation_revision_id: str | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: str | None,
    bucket_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: ModeloCalculationRevisionDefault | None = None,
) -> CalculationRevision:
    """Resolve one :class:`CalculationRevision` from exact or visible operator input."""
    if (
        calculation_revision_id is not None
        and work_unit_id is None
        and modelo is None
        and year is None
        and period is None
        and registry_revision_id is None
        and bucket_id is None
    ):
        address = ModeloWorkAddress()
    else:
        address = modelo_work_address_from_operator_target(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=registry_revision_id,
            bucket_id=bucket_id,
        )
    if default_for == "verify":
        return resolve_verifiable_modelo_calculation_revision_address(
            address=address,
            calculation_revision_id=calculation_revision_id,
            selector=selector,
        )
    if default_for == "file":
        return resolve_fileable_modelo_calculation_revision_address(
            address=address,
            calculation_revision_id=calculation_revision_id,
            selector=selector,
        )
    if default_for == "export":
        return resolve_exportable_modelo_calculation_revision_address(
            address=address,
            calculation_revision_id=calculation_revision_id,
            selector=selector,
        )
    return resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
    )


def resolve_modelo_work_target(target: ModeloWorkTarget) -> ModeloWorkResolution:
    """Resolve any supported modelo target through the shared selector boundary.

    Returns a :class:`ModeloWorkResolution`.
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
    registry_revision_id: str | None,
) -> str:
    """Resolve and validate the registry revision for a visible filing target.

    When ``registry_revision_id`` is ``None`` the law-determined revision for
    ``(modelo, filing_year, period)`` is returned unconditionally.

    When ``registry_revision_id`` is supplied it is treated as an
    *assertion parameter* (per :class:`select_revision`'s structural property):
    an explicit ``--revision`` is accepted only when it names exactly the revision
    that ``select_revision`` would pick from ``(filing_year, period)`` alone.  If
    the supplied id diverges from the law-determined revision the call refuses with
    an instructive error naming both the requested and the law-determined revision
    and stating that the binding is fixed by law (per the CLI-boundary
    instructive-refusal mandate in ``aeat-architecture-boundaries``).

    ``--revision`` is thereby demoted from a free override to an
    idempotence/assertion handle, mirroring the operator-surface ADR's D8
    shape for ``preflight --revision-id``.
    """
    definition = resources().modelos.authority.modelo(modelo.strip())
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


def ensure_modelo_work_unit_for_visible_target(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: str | None,
    name: str | None = None,
    actor: str = "operator",
    causante_ccaa: CCAA | None = None,
) -> ModeloWorkEnsureResult:
    """Resume or create the active work unit for one visible filing target.

    Returns a :class:`ModeloWorkEnsureResult`.
    """
    requested_revision = registry_revision_id.strip() if registry_revision_id is not None else None
    resolution = resolve_optional_modelo_work_address(
        ModeloWorkAddress(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            registry_revision_id=requested_revision,
        ),
    )
    if resolution.work_unit is not None:
        unit = resolution.work_unit
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
    )
    return ModeloWorkEnsureResult(work_unit=unit, reused=False)


def resolve_modelo_work_address(address: ModeloWorkAddress) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address and return a :class:`ModeloWorkResolution`."""
    resolution = resolve_optional_modelo_work_address(address)
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise ModeloWorkAddressNotFoundError("no active modelo work unit matches the supplied address")
    return resolution


def resolve_optional_modelo_work_address(address: ModeloWorkAddress) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address and return a :class:`ModeloWorkResolution`, allowing absence."""
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
    """Resolve an operator-facing modelo work address to one :class:`WorkUnit`."""
    resolution = resolve_modelo_work_address(address)
    assert resolution.work_unit is not None
    return resolution.work_unit


def resolve_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: ModeloCalculationRevisionDefault | None = None,
) -> CalculationRevision:
    """Resolve a :class:`CalculationRevision` by exact id or under a modelo work address."""
    if calculation_revision_id is not None and address == ModeloWorkAddress():
        return get_calculation_revision(calculation_revision_id)

    work_unit = resolve_modelo_work_address_unit(address)
    return resolve_modelo_calculation_revision_pick(
        work_unit,
        selector=selector,
        calculation_revision_id=calculation_revision_id,
        default_for=default_for,
    ).revision


def resolve_modelo_revision_pick(
    *,
    target: ModeloWorkTarget,
    pick: ModeloRevisionPick | None = None,
) -> ModeloResolvedRevisionProjection:
    """Resolve and project a :class:`ModeloResolvedRevisionProjection` for a visible or exact work target."""
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
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the :class:`CalculationRevision` that ``work verify`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="verify",
    )
    return _require_revision_state(
        revision,
        allowed=(CalculationRevisionState.BORRADOR,),
        purpose="verification",
    )


def resolve_fileable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the :class:`CalculationRevision` that ``work file`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="file",
    )
    return _require_revision_state(
        revision,
        allowed=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        purpose="filing",
    )


def resolve_exportable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the :class:`CalculationRevision` that ``modelo export`` may consume."""
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
    "ensure_modelo_work_unit_for_visible_target",
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
