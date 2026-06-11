"""Previous-filing binding selectors, requirements, and resolvers.

Use of :class:`ModeloRevision` for compliance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core import Period
from ._errors import RegistryValidationError
from ._period_offset_math import apply_period_offset
from ._schema import DataBindingDefinition, ModeloRevision, filing_period_from_scope


class _RegistryModeloObservationLike(Protocol):
    modelo: str
    filing_year: int
    period: str

    @property
    def casilla_values(self) -> Mapping[str, Decimal]: ...


class RegistryModeloObservationRequirement(BaseModel):
    """Filed declaration required by one or more registry bindings."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1, max_length=8)
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    binding_ids: tuple[str, ...] = Field(min_length=1)
    source_casillas: tuple[str, ...] = Field(min_length=1)

    @field_validator("binding_ids", "source_casillas")
    @classmethod
    def _values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("observation requirement tuple entries must be unique")
        return value


def previous_filing_observation_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryModeloObservationRequirement, ...]:
    """Return :class:`RegistryModeloObservationRequirement` records needed by direct previous-filing bindings.

    Use of :class:`ModeloRevision` for compliance.
    """
    grouped: dict[tuple[str, int, str], dict[str, set[str]]] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        if not _is_direct_previous_filing_binding(binding):
            continue
        selector = _previous_filing_selector(binding)
        for period_year_delta, required_period in selector.required_period_anchors_for_target(period):
            expected_year = filing_year + selector.filing_year_delta + period_year_delta
            key = (selector.source_modelo, expected_year, required_period)
            bucket = grouped.setdefault(key, {"binding_ids": set(), "source_casillas": set()})
            bucket["binding_ids"].add(binding.id)
            bucket["source_casillas"].update(_previous_filing_source_ids(selector))
    return tuple(
        RegistryModeloObservationRequirement(
            modelo=modelo,
            filing_period=filing_period_from_scope(expected_year, required_period),
            filing_year=expected_year,
            period=required_period,
            binding_ids=tuple(sorted(values["binding_ids"])),
            source_casillas=tuple(sorted(values["source_casillas"])),
        )
        for (modelo, expected_year, required_period), values in sorted(grouped.items())
    )


def _observed_casilla_values(
    binding: DataBindingDefinition,
    selector: _PreviousModeloSelector,
    match: _RegistryModeloObservationLike,
    expected_year: int,
    required_period: str,
) -> list[Decimal]:
    values: list[Decimal] = []
    for casilla_id in _previous_filing_source_ids(selector):
        casilla_value = match.casilla_values.get(casilla_id)
        if casilla_value is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} requires observed casilla {casilla_id!r} "
                f"from {selector.source_modelo!r}/{expected_year}/{required_period!r}",
            )
        values.append(casilla_value)
    return values


def _resolve_anchor_values(
    binding: DataBindingDefinition,
    selector: _PreviousModeloSelector,
    available: tuple[_RegistryModeloObservationLike, ...],
    *,
    expected_year: int,
    required_period: str,
) -> list[Decimal]:
    matches = tuple(
        observation
        for observation in available
        if observation.modelo == selector.source_modelo
        and observation.filing_year == expected_year
        and observation.period == required_period
    )
    if selector.grouping == "per_grupo_member":
        if not matches:
            raise RegistryValidationError(
                f"binding {binding.id!r} (per_grupo_member) expected at least one observed filing "
                f"{selector.source_modelo!r}/{expected_year}/{required_period!r}, found 0",
            )
        values: list[Decimal] = []
        for member_match in matches:
            values.extend(_observed_casilla_values(binding, selector, member_match, expected_year, required_period))
        return values
    if len(matches) != 1:
        raise RegistryValidationError(
            f"binding {binding.id!r} expected one observed filing "
            f"{selector.source_modelo!r}/{expected_year}/{required_period!r}, found {len(matches)}",
        )
    return _observed_casilla_values(binding, selector, matches[0], expected_year, required_period)


def _resolve_binding_values(
    binding: DataBindingDefinition,
    available: tuple[_RegistryModeloObservationLike, ...],
    *,
    filing_year: int,
    period: str,
) -> list[Decimal] | None:
    selector = _previous_filing_selector(binding)
    required_anchors = selector.required_period_anchors_for_target(period)
    if not required_anchors:
        return None
    values: list[Decimal] = []
    for period_year_delta, required_period in required_anchors:
        expected_year = filing_year + selector.filing_year_delta + period_year_delta
        values.extend(
            _resolve_anchor_values(
                binding, selector, available, expected_year=expected_year, required_period=required_period,
            ),
        )
    return values


def resolve_previous_filing_binding_values(
    revision: ModeloRevision,
    observations: Iterable[_RegistryModeloObservationLike],
    *,
    filing_year: int,
    period: str,
) -> dict[str, Decimal]:
    """Resolve direct previous-filing bindings from observed filed declarations.

    Use of :class:`ModeloRevision` for compliance.
    """
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        if not _is_direct_previous_filing_binding(binding):
            continue
        values = _resolve_binding_values(binding, available, filing_year=filing_year, period=period)
        if values is None:
            continue
        resolved[binding.id] = _aggregate_previous_filing_binding(binding, values)
    return resolved


def _selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {k: v for k, v in selector.items() if k != "source"}


class _PreviousModeloSelector(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year_delta: int = 0
    period: str | None = Field(default=None, min_length=1, max_length=8)
    source_periods: tuple[str, ...] = ()
    source_period_offset_from_target: int | None = None
    source_casillas: tuple[str, ...] = ()
    source_output: str | None = Field(default=None, min_length=1)
    max_year_delta: int | None = None
    grouping: Literal["per_grupo_member"] | None = None

    @field_validator("max_year_delta")
    @classmethod
    def _max_year_delta_non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise RegistryValidationError("previous-filing max_year_delta must be non-negative")
        return value

    @field_validator("source_periods")
    @classmethod
    def _source_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("previous-filing source_periods entries must be unique")
        return value

    @property
    def required_periods(self) -> tuple[str, ...]:
        if self.period is not None:
            return (self.period,)
        return self.source_periods

    def required_periods_for_target(self, target_period: str) -> tuple[str, ...]:
        return tuple(period for _year_delta, period in self.required_period_anchors_for_target(target_period))

    def required_period_anchors_for_target(self, target_period: str) -> tuple[tuple[int, str], ...]:
        if self.source_period_offset_from_target is None:
            anchors: tuple[tuple[int, str], ...] = tuple((0, period) for period in self.required_periods)
        else:
            anchors = (
                _derive_offset_source_anchor(self.source_period_offset_from_target, target_period=target_period),
            )
        if self.max_year_delta is None:
            return anchors
        return tuple(anchor for anchor in anchors if abs(anchor[0]) <= self.max_year_delta)

    @field_validator("period")
    @classmethod
    def _period_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise RegistryValidationError("previous-filing period must be non-empty")
        return value

    @field_validator("source_casillas")
    @classmethod
    def _source_casillas_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("previous-filing source_casillas entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_period_selector(self) -> _PreviousModeloSelector:
        if self.source_period_offset_from_target is not None:
            if self.period is not None or self.source_periods:
                raise RegistryValidationError(
                    "previous-filing selector cannot declare period/source_periods together with "
                    "source_period_offset_from_target",
                )
            if self.source_period_offset_from_target == 0 and self.grouping != "per_grupo_member":
                raise RegistryValidationError("previous-filing source_period_offset_from_target must be non-zero")
        if self.period is not None and self.source_periods:
            raise RegistryValidationError("previous-filing selector must use period or source_periods, not both")
        if (
            self.period is None
            and not self.source_periods
            and self.source_period_offset_from_target is None
            and self.source_casillas
        ):
            raise RegistryValidationError(
                "previous-filing selector must declare period, source_periods, or source_period_offset_from_target",
            )
        return self

    @model_validator(mode="after")
    def _validate_source_spec(self) -> _PreviousModeloSelector:
        if self.source_casillas and self.source_output is not None:
            raise RegistryValidationError(
                "previous-filing selector cannot declare both source_casillas and source_output",
            )
        return self


def _previous_filing_selector(binding: DataBindingDefinition) -> _PreviousModeloSelector:
    try:
        return _PreviousModeloSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed previous-filing selector") from exc


def _is_direct_previous_filing_binding(binding: DataBindingDefinition) -> bool:
    selector = _selector_as_dict(binding)
    if selector.get("source_casillas"):
        return True
    if selector.get("source_output") is None:
        return False
    return any(key in selector for key in ("period", "source_periods", "source_period_offset_from_target"))


def _previous_filing_source_ids(selector: _PreviousModeloSelector) -> tuple[str, ...]:
    if selector.source_casillas:
        return selector.source_casillas
    if selector.source_output is not None:
        return (selector.source_output,)
    return ()


def _derive_offset_source_anchor(offset: int, *, target_period: str) -> tuple[int, str]:
    try:
        return apply_period_offset(offset, target_period=target_period)
    except RegistryValidationError as exc:
        raise RegistryValidationError(
            f"previous-filing source_period_offset_from_target cannot interpret target period {target_period!r}",
        ) from exc


def _aggregate_previous_filing_binding(binding: DataBindingDefinition, values: list[Decimal]) -> Decimal:
    op = str((binding.aggregation or {}).get("op", "sum"))
    if op == "sum":
        return sum(values, Decimal("0"))
    if op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(f"binding {binding.id!r} copy aggregation requires one source casilla")
        return values[0]
    raise RegistryValidationError(f"binding {binding.id!r} uses unsupported previous-filing aggregation {op!r}")
