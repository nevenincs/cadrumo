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


def _optional_source_casilla_ids(binding: DataBindingDefinition, selector: _PreviousModeloSelector) -> frozenset[str]:
    """Return the source casillas a prior observation may legitimately omit.

    For the ``prior_pagos_fraccionados`` op (AEAT Modelo 130 casilla 05) the
    minoración casilla (the SECOND declared source casilla, casilla 16) is
    optional: a prior filing that genuinely lacks any casilla-16 entry
    ("not captured", distinct from "filed 0") must not hard-fail the carry. The
    resolver treats the absent minoración as ``Decimal`` zero and the
    application layer surfaces the not-captured advisory naming the gap, so the
    minoración is never silently dropped (ADR
    ``2026-06-13-modelo-130-pagos-fraccionados-carry``, ratified casilla-16
    filed-zero-vs-not-captured distinction; ``no-silent-under-declaration``).

    The positive-part casilla (casilla 07) stays REQUIRED: a payment that was
    never filed cannot be carried, so its absence is a real integrity error.
    Every other op keeps every source casilla required (empty optional set).
    """
    aggregation = binding.aggregation or {}
    if str(aggregation.get("op", "sum")) != "prior_pagos_fraccionados":
        return frozenset()
    source_ids = _previous_filing_source_ids(selector)
    if len(source_ids) != 2:
        return frozenset()
    return frozenset({source_ids[1]})


def _observed_casilla_values(
    binding: DataBindingDefinition,
    selector: _PreviousModeloSelector,
    match: _RegistryModeloObservationLike,
    expected_year: int,
    required_period: str,
) -> list[Decimal]:
    optional_ids = _optional_source_casilla_ids(binding, selector)
    values: list[Decimal] = []
    for casilla_id in _previous_filing_source_ids(selector):
        casilla_value = match.casilla_values.get(casilla_id)
        if casilla_value is None:
            if casilla_id in optional_ids:
                # Not-captured optional minoración: default to zero and let the
                # application advisory name the gap rather than dropping the carry.
                values.append(Decimal("0"))
                continue
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
        resolved[binding.id] = _aggregate_previous_filing_binding(
            binding,
            values,
            source_casillas=_previous_filing_source_ids(_previous_filing_selector(binding)),
        )
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
    prior_quarter_expanding_span: bool = False
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
        if self.prior_quarter_expanding_span:
            anchors: tuple[tuple[int, str], ...] = _prior_quarter_expanding_span_anchors(target_period)
        elif self.source_period_offset_from_target is None:
            anchors = tuple((0, period) for period in self.required_periods)
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
        if self.prior_quarter_expanding_span and (
            self.period is not None
            or self.source_periods
            or self.source_period_offset_from_target is not None
        ):
            raise RegistryValidationError(
                "previous-filing prior_quarter_expanding_span is mutually exclusive with "
                "period, source_periods, and source_period_offset_from_target",
            )
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
            and not self.prior_quarter_expanding_span
            and self.source_casillas
        ):
            raise RegistryValidationError(
                "previous-filing selector must declare period, source_periods, "
                "source_period_offset_from_target, or prior_quarter_expanding_span",
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


_QUARTER_ORDINAL: dict[str, int] = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}
_ORDINAL_QUARTER: dict[int, str] = {ordinal: code for code, ordinal in _QUARTER_ORDINAL.items()}


def _prior_quarter_expanding_span_anchors(target_period: str) -> tuple[tuple[int, str], ...]:
    """Enumerate the same-ejercicio quarters strictly preceding ``target_period``.

    Models the AEAT Modelo 130 casilla-05 ``trimestres anteriores del mismo
    ejercicio`` span: ``1T`` yields the empty span (no prior quarter within the
    ejercicio, absent-by-design), ``2T`` yields ``{1T}``, ``3T`` yields
    ``{1T, 2T}``, and ``4T`` yields ``{1T, 2T, 3T}``. Every anchor carries
    ``year_delta = 0`` because the span never reaches across the ejercicio
    boundary (paired with ``max_year_delta = 0`` on the binding).
    """
    ordinal = _QUARTER_ORDINAL.get(target_period)
    if ordinal is None:
        raise RegistryValidationError(
            "previous-filing prior_quarter_expanding_span cannot interpret target period "
            f"{target_period!r}; only quarterly codes 1T..4T are supported",
        )
    return tuple((0, _ORDINAL_QUARTER[prior]) for prior in range(1, ordinal))


def _aggregate_previous_filing_binding(
    binding: DataBindingDefinition,
    values: list[Decimal],
    *,
    source_casillas: tuple[str, ...] = (),
) -> Decimal:
    aggregation = binding.aggregation or {}
    op = str(aggregation.get("op", "sum"))
    if op == "sum":
        return sum(values, Decimal("0"))
    if op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(f"binding {binding.id!r} copy aggregation requires one source casilla")
        return values[0]
    if op == "prior_pagos_fraccionados":
        return _aggregate_prior_pagos_fraccionados(binding, values, source_casillas=source_casillas)
    raise RegistryValidationError(f"binding {binding.id!r} uses unsupported previous-filing aggregation {op!r}")


def _aggregate_prior_pagos_fraccionados(
    binding: DataBindingDefinition,
    values: list[Decimal],
    *,
    source_casillas: tuple[str, ...],
) -> Decimal:
    """Compute the AEAT Modelo 130 casilla-05 identity from per-anchor pairs.

    casilla 05 = SUM over prior quarters q of max(0, casilla 07_q)
                 minus SUM over the same q of casilla 16_q

    The flat ``values`` list carries per-anchor groups in ``source_casillas``
    order (``[07_q1, 16_q1, 07_q2, 16_q2, ...]``); the op slices that grouping,
    applies the positive-part to the first casilla (07) PER QUARTER before
    summing, and subtracts the sum of the second casilla (16). Both terms are
    load-bearing: a negative prior 07 contributes 0 (not its negative value),
    and the prior casilla-16 minoración is never dropped (per the
    aeat-modelo-130-instructions verbatim rule).
    """
    if len(source_casillas) != 2:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation requires exactly two "
            f"source casillas (positive-part casilla then minoracion casilla); got {source_casillas!r}",
        )
    group_size = len(source_casillas)
    if len(values) % group_size != 0:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation expected per-quarter pairs; "
            f"got {len(values)} values for {group_size} source casillas",
        )
    zero = Decimal("0")
    positive_part_total = zero
    minoracion_total = zero
    for index in range(0, len(values), group_size):
        positive_casilla_value = values[index]
        minoracion_casilla_value = values[index + 1]
        positive_part_total += positive_casilla_value if positive_casilla_value > zero else zero
        minoracion_total += minoracion_casilla_value
    return positive_part_total - minoracion_total
