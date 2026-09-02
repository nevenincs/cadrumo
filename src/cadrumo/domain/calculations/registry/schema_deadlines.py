"""Deadline-window and filing-schedule declarations for registry revisions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core.filing_year import FilingYear
from ....core.irnr import M210_TIPO_RENTA_CODE_PROJECTION
from ....core.period import Period, PeriodKind, RegistrySelectorPeriodCode, registry_period_kind
from ....core.result_disposition import ResultDisposition
from .condition_mode import ConditionMode, ConditionModeField
from .errors import RegistryValidationError
from .ids import DeadlineWindowId
from .schema_base import LegalRefs, RegistryModel, SourceRefs, coerce_enum_member
from .schema_verification import ProfilePredicateDefinition

__all__ = [
    "DeadlineWindowDefinition",
    "ModeloScheduleDefinition",
    "filing_schedule_period_kind_mismatches",
]


def _parse_deadline_window_period(value: object) -> Period:
    """Hydrate a deadline-window period through :class:`~core.Period`."""
    if isinstance(value, Period):
        return value
    if isinstance(value, Mapping):
        try:
            return Period.model_validate(value)
        except ValueError as exc:
            raise ValueError(f"invalid deadline window period mapping {value!r}: {exc}") from exc
    if not isinstance(value, str):
        raise ValueError(f"deadline window period must be a string or Period, got {type(value).__name__}")

    try:
        return Period.from_string(value)
    except ValueError as exc:
        raise ValueError(f"invalid deadline window period {value!r}: {exc}") from exc


class FilingCadence(StrEnum):
    """The filing cadence a deadline window or modelo schedule declares.

    Distinct from the period kind in the core package, which shares three member
    values but names a different axis: that vocabulary describes a period's shape,
    including instalment and extended periods, and has no ad-hoc member. Both are
    referenced from this module, so the names must not collide.
    """

    MONTHLY = "monthly"
    """One filing period per calendar month."""

    QUARTERLY = "quarterly"
    """One filing period per calendar quarter."""

    ANNUAL = "annual"
    """One filing period covering the ejercicio."""

    AD_HOC = "ad_hoc"
    """No fixed cadence; the period is opened by an event rather than a calendar."""


FilingCadenceField = Annotated[FilingCadence, BeforeValidator(coerce_enum_member(FilingCadence))]
"""Registry ``period_kind`` token hydrated into a cadence member.

Registry schema models validate strictly, which refuses a bare TOML string for an
enum-typed field, so the token is coerced at the boundary.
"""


class DeadlineWindowDefinition(RegistryModel):
    """Declare the applicable opening, closing, and payment dates for a filing."""

    id: DeadlineWindowId
    filing_year: FilingYear
    period: Annotated[Period, BeforeValidator(_parse_deadline_window_period)]
    period_kind: FilingCadenceField
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    applicability_condition_mode: ConditionModeField = ConditionMode.ALL
    applicability_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    resultado_scope: (
        Annotated[
            ResultDisposition,
            BeforeValidator(lambda value: ResultDisposition(value) if isinstance(value, str) else value),
        ]
        | None
    ) = None
    tipo_renta_scope: tuple[str, ...] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("tipo_renta_scope")
    @classmethod
    def _validate_tipo_renta_scope(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """Preserve official M210 codes without folding them into rate concepts."""
        if value is None:
            return None
        if not value:
            raise RegistryValidationError("deadline window tipo_renta_scope must not be empty")
        if len(set(value)) != len(value):
            raise RegistryValidationError("deadline window tipo_renta_scope entries must be unique")
        unknown_codes = tuple(code for code in value if code not in M210_TIPO_RENTA_CODE_PROJECTION)
        if unknown_codes:
            accepted = ", ".join(sorted(M210_TIPO_RENTA_CODE_PROJECTION))
            raise RegistryValidationError(
                f"deadline window tipo_renta_scope contains unknown official Modelo 210 codes "
                f"{unknown_codes!r}; accepted codes: {accepted}",
            )
        return value

    @model_validator(mode="after")
    def _validate_window(self) -> DeadlineWindowDefinition:
        if self.filing_year != self.period.filing_year:
            raise RegistryValidationError(
                f"deadline window {self.id!r} filing_year {self.filing_year} must match "
                f"period filing_year {self.period.filing_year}",
            )
        if self.opens_on > self.closes_on:
            raise RegistryValidationError(f"deadline window {self.id!r} opens_on must not be after closes_on")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise RegistryValidationError(f"deadline window {self.id!r} payment_cutoff_on must not be after closes_on")
        if self.applicability_condition_mode is ConditionMode.ANY and not self.applicability_conditions:
            raise RegistryValidationError(f"deadline window {self.id!r} any-mode requires applicability conditions")
        return self


_SCHEDULE_PERIOD_KINDS: dict[str, frozenset[PeriodKind]] = {
    "monthly": frozenset({PeriodKind.MONTHLY}),
    "quarterly": frozenset({PeriodKind.QUARTERLY, PeriodKind.INSTALMENT, PeriodKind.EXTENDED}),
    "annual": frozenset({PeriodKind.ANNUAL}),
    # Event and administrative tokens classify as EXTENDED. Modelo 840 uses
    # annual 0A as its exercise coordinate, so this cadence also admits ANNUAL;
    # legal/source grounding still establishes whether a declaration is correct.
    "ad_hoc": frozenset({PeriodKind.EXTENDED, PeriodKind.ANNUAL}),
}


def filing_schedule_period_kind_mismatches(period_kind: str, periods: tuple[str, ...]) -> tuple[str, ...]:
    """Return schedule tokens whose canonical cadence contradicts ``period_kind``."""
    accepted = _SCHEDULE_PERIOD_KINDS[period_kind]
    mismatches: list[str] = []
    for token in periods:
        try:
            canonical_kind = registry_period_kind(token)
        except ValueError:
            mismatches.append(token)
            continue
        if canonical_kind not in accepted:
            mismatches.append(token)
    return tuple(mismatches)


class ModeloScheduleDefinition(RegistryModel):
    """Declare the filing periods and profile conditions for a modelo schedule."""

    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    period_kind: FilingCadenceField
    periods: tuple[RegistrySelectorPeriodCode, ...] = Field(min_length=1)
    profile_condition_mode: ConditionModeField = ConditionMode.ALL
    profile_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @property
    def is_periodic(self) -> bool:
        """Whether this schedule requires complete recurring deadline coverage."""
        return self.period_kind in ("monthly", "quarterly")

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("filing schedule periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_schedule(self) -> ModeloScheduleDefinition:
        if self.profile_condition_mode is ConditionMode.ANY and not self.profile_conditions:
            raise RegistryValidationError(f"filing schedule {self.id!r} any-mode requires profile conditions")
        mismatches = filing_schedule_period_kind_mismatches(self.period_kind, self.periods)
        if mismatches:
            raise RegistryValidationError(
                f"filing schedule {self.id!r} period_kind {self.period_kind!r} contradicts periods {mismatches!r}",
            )
        return self
