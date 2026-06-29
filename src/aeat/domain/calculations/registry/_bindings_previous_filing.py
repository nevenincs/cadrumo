"""Previous-filing binding selectors, requirements, and resolvers.

The :class:`ModeloRevision` supplies ``previous_filing`` binding declarations;
this module turns those selectors into source-observation requirements and
resolved binding values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import BindingAggregationOp
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import invariant_diagnostics, selector_against_model
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, ModeloId
from ._observation_fold import fold_sum_or_copy
from ._period_offset_math import apply_period_offset
from ._relations import RegistryFoldRequirement
from ._schema import DataBindingDefinition, ModeloRevision, filing_period_from_scope


class _RegistryModeloObservationLike(Protocol):
    modelo: ModeloId
    filing_year: int
    period: str

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]: ...


@dataclass(frozen=True, slots=True)
class PreviousFilingSourceReference:
    """Canonical source reference extracted from a typed previous-filing selector."""

    source_modelo: ModeloId
    required_periods: tuple[str, ...]
    source_casilla_ids: tuple[CasillaId, ...]


def previous_filing_source_reference(binding: DataBindingDefinition) -> PreviousFilingSourceReference:
    """Return the :class:`PreviousFilingSourceReference` for a ``previous_filing`` binding."""
    selector = _previous_filing_selector(binding)
    return PreviousFilingSourceReference(
        source_modelo=selector.source_modelo,
        required_periods=selector.required_periods,
        source_casilla_ids=_previous_filing_source_ids(selector),
    )


def previous_filing_observation_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryFoldRequirement, ...]:
    """Return :class:`RegistryFoldRequirement` records needed by direct previous-filing bindings.

    The :class:`ModeloRevision` is scanned for direct ``previous_filing``
    bindings, and each selector becomes a source modelo/year/period
    requirement.
    """
    binding_ids_by_key: dict[tuple[ModeloId, int, str], set[BindingId]] = {}
    source_casilla_ids_by_key: dict[tuple[ModeloId, int, str], set[CasillaId]] = {}
    for binding in revision.bindings:
        if binding.source != "previous_filing":
            continue
        if not _is_direct_previous_filing_binding(binding):
            continue
        selector = _previous_filing_selector(binding)
        for period_year_delta, required_period in selector.required_period_anchors_for_target(period):
            expected_year = filing_year + selector.filing_year_delta + period_year_delta
            key = (selector.source_modelo, expected_year, required_period)
            binding_ids_by_key.setdefault(key, set()).add(binding.id)
            source_casilla_ids_by_key.setdefault(key, set()).update(_previous_filing_source_ids(selector))
    return tuple(
        RegistryFoldRequirement(
            source_modelo=modelo,
            filing_periods=tuple(
                filing_period
                for filing_period in (filing_period_from_scope(expected_year, required_period),)
                if filing_period is not None
            ),
            filing_year=expected_year,
            periods=(required_period,),
            binding_ids=tuple(sorted(binding_ids_by_key[(modelo, expected_year, required_period)])),
            source_casilla_ids=tuple(sorted(source_casilla_ids_by_key[(modelo, expected_year, required_period)])),
        )
        for modelo, expected_year, required_period in sorted(binding_ids_by_key)
    )


def _optional_source_casilla_ids(
    binding: DataBindingDefinition,
    selector: _PreviousModeloSelector,
) -> frozenset[CasillaId]:
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
    if binding_aggregation_op(binding) != BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS:
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
    activity_start_date: date | None = None,
) -> list[Decimal] | None:
    selector = _previous_filing_selector(binding)
    required_anchors = selector.required_period_anchors_for_target(period)
    if not required_anchors:
        return None
    values: list[Decimal] = []
    scoped_pre_activity = False
    for period_year_delta, required_period in required_anchors:
        expected_year = filing_year + selector.filing_year_delta + period_year_delta
        if _anchor_strictly_before_activity_start(
            expected_year,
            required_period,
            activity_start_date=activity_start_date,
        ):
            scoped_pre_activity = True
            continue
        values.extend(
            _resolve_anchor_values(
                binding,
                selector,
                available,
                expected_year=expected_year,
                required_period=required_period,
            ),
        )
    if not values and scoped_pre_activity:
        return _zero_values_for_scoped_out_binding(selector)
    return values


def resolve_previous_filing_binding_values(
    revision: ModeloRevision,
    observations: Iterable[_RegistryModeloObservationLike],
    *,
    filing_year: int,
    period: str,
    activity_start_date: date | None = None,
    excluded_binding_ids: frozenset[BindingId] | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve direct previous-filing bindings from observed filed declarations.

    The :class:`ModeloRevision` supplies the binding selectors and aggregation
    operators; ``observations`` supply the filed casilla values they fold.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    excluded = excluded_binding_ids or frozenset()
    for binding in revision.bindings:
        if binding.id in excluded:
            continue
        if binding.source != "previous_filing":
            continue
        if not _is_direct_previous_filing_binding(binding):
            continue
        values = _resolve_binding_values(
            binding,
            available,
            filing_year=filing_year,
            period=period,
            activity_start_date=activity_start_date,
        )
        if values is None:
            continue
        resolved[binding.id] = _aggregate_previous_filing_binding(
            binding,
            values,
            source_casilla_ids=_previous_filing_source_ids(_previous_filing_selector(binding)),
        )
    return resolved


def _anchor_strictly_before_activity_start(
    expected_year: int,
    required_period: str,
    *,
    activity_start_date: date | None,
) -> bool:
    """Return whether a source period ended before the taxpayer's activity started."""
    if activity_start_date is None:
        return False
    filing_period = filing_period_from_scope(expected_year, required_period)
    if filing_period is None or not filing_period.has_date_span():
        return False
    return filing_period.end_date < activity_start_date


def _zero_values_for_scoped_out_binding(selector: _PreviousModeloSelector) -> list[Decimal]:
    """Return a neutral zero vector matching the binding's source-casilla shape."""
    return [Decimal("0")] * max(1, len(_previous_filing_source_ids(selector)))


class _PreviousModeloSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    filing_year_delta: int = 0
    period: str | None = Field(default=None, min_length=1, max_length=8)
    source_periods: tuple[str, ...] = ()
    source_period_offset_from_target: int | None = None
    prior_quarter_expanding_span: bool = False
    source_casilla_ids: tuple[CasillaId, ...] = ()
    source_casilla_id: CasillaId | None = None
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

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("previous-filing source_casilla_ids entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_period_selector(self) -> _PreviousModeloSelector:
        if self.prior_quarter_expanding_span and (
            self.period is not None or self.source_periods or self.source_period_offset_from_target is not None
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
            and self.source_casilla_ids
        ):
            raise RegistryValidationError(
                "previous-filing selector must declare period, source_periods, "
                "source_period_offset_from_target, or prior_quarter_expanding_span",
            )
        return self

    @model_validator(mode="after")
    def _validate_source_spec(self) -> _PreviousModeloSelector:
        if self.source_casilla_ids and self.source_casilla_id is not None:
            raise RegistryValidationError(
                "previous-filing selector cannot declare both source_casilla_ids and source_casilla_id",
            )
        return self


def _previous_filing_selector(binding: DataBindingDefinition) -> _PreviousModeloSelector:
    selector = _selector_as_dict(binding)
    try:
        return _PreviousModeloSelector.model_validate(selector)
    except ValueError as exc:
        hint = ""
        if "source_casillas" in selector:
            hint = "; use source_casilla_ids, not source_casillas"
        elif "source_output" in selector:
            hint = "; use source_casilla_id, not source_output"
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed previous-filing selector: {exc}{hint}",
        ) from exc


_PREVIOUS_FILING_OPS: frozenset[BindingAggregationOp] = frozenset(
    {
        BindingAggregationOp.SUM,
        BindingAggregationOp.COPY,
        BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS,
    },
)


def _validate_previous_filing_invariants(binding: DataBindingDefinition) -> None:
    """Lift the resolve-time previous-filing op/source invariants to build time.

    A previous_filing binding aggregates one or more source casillas under one of
    the supported ops. The op must be a member of :data:`_PREVIOUS_FILING_OPS`
    (the same closed set :func:`_aggregate_previous_filing_binding` accepts at
    resolve time); ``copy`` requires exactly one source casilla and
    ``prior_pagos_fraccionados`` requires exactly two (per quarter pair). These
    are determinable from the selector at build time, so a malformed pairing
    fails at snapshot construction rather than only on a taxpayer calculation.

    Only direct previous_filing bindings carry a source-casilla shape; a
    relation-targeted previous_filing slot is short-circuited (its value is
    produced by relation resolution, not this aggregator).
    """
    op = binding_aggregation_op(binding)
    if op not in _PREVIOUS_FILING_OPS:
        raise RegistryValidationError(
            f"binding {binding.id!r} uses unsupported previous-filing aggregation {op.value!r}",
        )
    if not _is_direct_previous_filing_binding(binding):
        return
    selector = _previous_filing_selector(binding)
    source_ids = _previous_filing_source_ids(selector)
    if op == BindingAggregationOp.COPY and len(source_ids) != 1:
        raise RegistryValidationError(
            f"binding {binding.id!r} copy aggregation requires one source casilla",
        )
    if op == BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS and len(source_ids) != 2:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation requires exactly two "
            f"source casillas (positive-part casilla then minoracion casilla); got {source_ids!r}",
        )


def validate_previous_filing_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a previous_filing binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector shape against
    :class:`_PreviousModeloSelector` and lifts the previous-filing op/source
    invariants (supported op set, copy single-casilla, pagos-fraccionados
    casilla-pair) to build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _PreviousModeloSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "previous-filing", _validate_previous_filing_invariants)


def _is_direct_previous_filing_binding(binding: DataBindingDefinition) -> bool:
    selector = _selector_as_dict(binding)
    if selector.get("source_casilla_ids"):
        return True
    if selector.get("source_casilla_id") is None:
        return False
    return any(key in selector for key in ("period", "source_periods", "source_period_offset_from_target"))


def _previous_filing_source_ids(selector: _PreviousModeloSelector) -> tuple[CasillaId, ...]:
    if selector.source_casilla_ids:
        return selector.source_casilla_ids
    if selector.source_casilla_id is not None:
        return (selector.source_casilla_id,)
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
    source_casilla_ids: tuple[CasillaId, ...] = (),
) -> Decimal:
    op = binding_aggregation_op(binding)
    if op in (BindingAggregationOp.SUM, BindingAggregationOp.COPY):
        return fold_sum_or_copy(
            op.value,
            values,
            subject=f"binding {binding.id!r}",
            copy_unit="source casilla",
        )
    if op == BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS:
        return _aggregate_prior_pagos_fraccionados(binding, values, source_casilla_ids=source_casilla_ids)
    raise RegistryValidationError(f"binding {binding.id!r} uses unsupported previous-filing aggregation {op.value!r}")


def _aggregate_prior_pagos_fraccionados(
    binding: DataBindingDefinition,
    values: list[Decimal],
    *,
    source_casilla_ids: tuple[CasillaId, ...],
) -> Decimal:
    """Compute the AEAT Modelo 130 casilla-05 identity from per-anchor pairs.

    casilla 05 = SUM over prior quarters q of max(0, casilla 07_q)
                 minus SUM over the same q of casilla 16_q

    The flat ``values`` list carries per-anchor groups in ``source_casilla_ids``
    order (``[07_q1, 16_q1, 07_q2, 16_q2, ...]``); the op slices that grouping,
    applies the positive-part to the first casilla (07) PER QUARTER before
    summing, and subtracts the sum of the second casilla (16). Both terms are
    load-bearing: a negative prior 07 contributes 0 (not its negative value),
    and the prior casilla-16 minoración is never dropped (per the
    aeat-modelo-130-instructions verbatim rule).
    """
    if len(source_casilla_ids) != 2:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation requires exactly two "
            f"source casillas (positive-part casilla then minoracion casilla); got {source_casilla_ids!r}",
        )
    group_size = len(source_casilla_ids)
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
