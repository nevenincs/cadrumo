"""Data binding helpers for registry-backed factual inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "DataBindingDefinition",
    "RegistryFilingObservation",
    "RegistryFilingObservationRequirement",
    "previous_filing_observation_requirements",
    "resolve_bound_casilla_inputs",
    "resolve_previous_filing_binding_values",
]


class RegistryFilingObservation(BaseModel):
    """Observed casilla values from a filed declaration."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    casilla_values: Mapping[str, Decimal]

    @field_validator("casilla_values")
    @classmethod
    def _values_are_decimal(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        for casilla_id, casilla_value in value.items():
            if not casilla_id:
                raise ValueError("observed casilla id must be non-empty")
            if isinstance(casilla_value, bool) or not isinstance(casilla_value, Decimal):
                raise ValueError(f"observed casilla {casilla_id!r} must be a Decimal")
        return value


class RegistryFilingObservationRequirement(BaseModel):
    """Filed declaration required by one or more registry bindings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    binding_ids: tuple[str, ...] = Field(min_length=1)
    source_casillas: tuple[str, ...] = Field(min_length=1)

    @field_validator("binding_ids", "source_casillas")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("observation requirement tuple entries must be unique")
        return value


def resolve_bound_casilla_inputs(
    revision: ModeloRevision,
    facts: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Resolve factual binding values into casilla input values.

    ``facts`` is keyed by registry binding id. The binding layer only selects
    factual values; it does not own legal rates, thresholds, or casilla meaning.
    """

    for key, value in facts.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"binding fact {key!r} must be a Decimal")
    binding_ids = {binding.id for binding in revision.bindings}
    unknown = sorted(set(facts).difference(binding_ids))
    if unknown:
        raise RegistryValidationError(f"unknown binding fact ids: {unknown!r}")
    resolved: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != "bound":
            continue
        if casilla.binding is None:
            raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
        if casilla.binding not in facts:
            raise RegistryValidationError(f"missing binding fact for casilla {casilla.id!r}: {casilla.binding!r}")
        resolved[casilla.id] = facts[casilla.binding]
    return resolved


def previous_filing_observation_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
    source_schedule_ids: Mapping[str, str] | None = None,
) -> tuple[RegistryFilingObservationRequirement, ...]:
    """Return filed declarations needed by previous-filing bindings."""

    grouped: dict[tuple[str, int, str], dict[str, set[str]]] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        selector = _previous_filing_selector(binding)
        expected_year = filing_year + selector.filing_year_delta
        for required_period in _binding_requirement_periods(selector, source_schedule_ids):
            key = (selector.source_modelo, expected_year, required_period)
            bucket = grouped.setdefault(key, {"binding_ids": set(), "source_casillas": set()})
            bucket["binding_ids"].add(binding.id)
            bucket["source_casillas"].update(selector.source_casillas)
    return tuple(
        RegistryFilingObservationRequirement(
            modelo=modelo,
            filing_year=expected_year,
            period=required_period,
            binding_ids=tuple(sorted(values["binding_ids"])),
            source_casillas=tuple(sorted(values["source_casillas"])),
        )
        for (modelo, expected_year, required_period), values in sorted(grouped.items())
    )


def resolve_previous_filing_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RegistryFilingObservation],
    *,
    filing_year: int,
    period: str,
    source_schedule_ids: Mapping[str, str] | None = None,
) -> dict[str, Decimal]:
    """Resolve previous-filing bindings from observed filed declarations."""

    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        selector = _previous_filing_selector(binding)
        expected_year = filing_year + selector.filing_year_delta
        values = []
        for required_period in _selected_binding_periods(selector, available, expected_year, source_schedule_ids):
            matches = tuple(
                observation
                for observation in available
                if observation.modelo == selector.source_modelo
                and observation.filing_year == expected_year
                and observation.period == required_period
            )
            if len(matches) != 1:
                raise RegistryValidationError(
                    f"binding {binding.id!r} expected one observed filing "
                    f"{selector.source_modelo!r}/{expected_year}/{required_period!r}, found {len(matches)}"
                )
            for casilla_id in selector.source_casillas:
                casilla_value = matches[0].casilla_values.get(casilla_id)
                if casilla_value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} requires observed casilla {casilla_id!r} "
                        f"from {selector.source_modelo!r}/{expected_year}/{required_period!r}"
                    )
                values.append(casilla_value)
        resolved[binding.id] = _aggregate_previous_filing_binding(binding, values)
    return resolved


class _PreviousFilingPeriodSet(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    source_schedule_id: str | None = Field(default=None, min_length=1)
    source_periods: tuple[str, ...] = Field(min_length=1)

    @field_validator("source_periods")
    @classmethod
    def _source_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("previous-filing source period set entries must be unique")
        return value


class _PreviousFilingSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year_delta: int = 0
    period: str | None = Field(default=None, min_length=1, max_length=8)
    source_periods: tuple[str, ...] = ()
    source_period_sets: tuple[_PreviousFilingPeriodSet, ...] = ()
    source_casillas: tuple[str, ...] = Field(min_length=1)

    @field_validator("source_periods")
    @classmethod
    def _source_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("previous-filing source_periods entries must be unique")
        return value

    @field_validator("source_period_sets")
    @classmethod
    def _source_period_sets_unique(
        cls, value: tuple[_PreviousFilingPeriodSet, ...]
    ) -> tuple[_PreviousFilingPeriodSet, ...]:
        ids = [period_set.id for period_set in value]
        if len(set(ids)) != len(ids):
            raise ValueError("previous-filing source period set ids must be unique")
        schedule_ids = [
            period_set.source_schedule_id for period_set in value if period_set.source_schedule_id is not None
        ]
        if len(set(schedule_ids)) != len(schedule_ids):
            raise ValueError("previous-filing source schedule ids must be unique")
        return value

    @property
    def required_periods(self) -> tuple[str, ...]:
        if self.period is not None:
            return (self.period,)
        return self.source_periods

    @field_validator("period")
    @classmethod
    def _period_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("previous-filing period must be non-empty")
        return value

    @field_validator("source_casillas")
    @classmethod
    def _source_casillas_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("previous-filing source_casillas entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_period_selector(self) -> _PreviousFilingSelector:
        declared = sum((self.period is not None, bool(self.source_periods), bool(self.source_period_sets)))
        if declared != 1:
            raise ValueError("previous-filing selector must declare exactly one period selector")
        return self


def _previous_filing_selector(binding: DataBindingDefinition) -> _PreviousFilingSelector:
    try:
        return _PreviousFilingSelector.model_validate(binding.selector)
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed previous-filing selector") from exc


def _binding_requirement_periods(
    selector: _PreviousFilingSelector,
    source_schedule_ids: Mapping[str, str] | None,
) -> tuple[str, ...]:
    if not selector.source_period_sets:
        return selector.required_periods
    selected_schedule = (source_schedule_ids or {}).get(selector.source_modelo)
    if selected_schedule is None:
        return tuple(period for period_set in selector.source_period_sets for period in period_set.source_periods)
    for period_set in selector.source_period_sets:
        if period_set.source_schedule_id == selected_schedule:
            return period_set.source_periods
    raise RegistryValidationError(
        f"previous-filing selector for {selector.source_modelo!r} has no period set for schedule {selected_schedule!r}"
    )


def _selected_binding_periods(
    selector: _PreviousFilingSelector,
    observations: tuple[RegistryFilingObservation, ...],
    filing_year: int,
    source_schedule_ids: Mapping[str, str] | None,
) -> tuple[str, ...]:
    if not selector.source_period_sets:
        return selector.required_periods
    selected_schedule = (source_schedule_ids or {}).get(selector.source_modelo)
    candidates = (
        tuple(
            period_set
            for period_set in selector.source_period_sets
            if period_set.source_schedule_id == selected_schedule
        )
        if selected_schedule is not None
        else selector.source_period_sets
    )
    complete = tuple(
        period_set
        for period_set in candidates
        if _has_observations_for_period_set(selector, period_set.source_periods, observations, filing_year)
    )
    if len(complete) == 1:
        return complete[0].source_periods
    if selected_schedule is not None:
        raise RegistryValidationError(
            f"previous-filing selector for {selector.source_modelo!r} schedule {selected_schedule!r} "
            f"does not have one complete observed period set"
        )
    if not complete:
        raise RegistryValidationError(
            f"previous-filing selector for {selector.source_modelo!r} does not match a complete observed period set"
        )
    raise RegistryValidationError(
        f"previous-filing selector for {selector.source_modelo!r} matches multiple complete period sets"
    )


def _has_observations_for_period_set(
    selector: _PreviousFilingSelector,
    periods: tuple[str, ...],
    observations: tuple[RegistryFilingObservation, ...],
    filing_year: int,
) -> bool:
    return all(
        any(
            observation.modelo == selector.source_modelo
            and observation.filing_year == filing_year
            and observation.period == period
            for observation in observations
        )
        for period in periods
    )


def _aggregate_previous_filing_binding(binding: DataBindingDefinition, values: list[Decimal]) -> Decimal:
    op = str((binding.aggregation or {}).get("op", "sum"))
    if op == "sum":
        return sum(values, Decimal("0"))
    if op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(f"binding {binding.id!r} copy aggregation requires one source casilla")
        return values[0]
    raise RegistryValidationError(f"binding {binding.id!r} uses unsupported previous-filing aggregation {op!r}")
