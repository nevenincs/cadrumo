"""Pure aggregation primitives for the retenciones modelo family.

This module groups typed :class:`RetencionObservation` rows into stable
per-perceptor rollups and totals for Modelos 111, 115, 123, 180, 190, and 193.
Observations must carry canonical source kinds from
:class:`~core.BindingSourceKind`; bare ``invoice`` provenance
is rejected in favour of ``payable_invoice`` or ``collectible_invoice``.

The live calculation mesh uses these primitives through
:class:`~._modelo_bindings.RetencionesAggregationSourceResolver` for the
Modelo 180/193 distinct-NIF perceptor count. Modelo 190's distinct
perceptor/clave/subclave percepciones count is intentionally handled by
:class:`~._withholding_source.WithholdingSourceResolver`, not by this rollup
family.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, Field, InstanceOf, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, Modelo, Period
from ...core.aggregation import BindingSourceKind
from ...core.aggregation import COUNTERPART_SOURCE_KIND_ORDER, COUNTERPART_SOURCE_KINDS, RetencionScheme
from ...core.identity import TaxIdIdentityToken
from ...core.parsing import IsoDateString
from ._grouping import assert_rollup_totals_match, filter_observations_for_modelo, group_and_collect_names


def _retenciones_source_kind(value: object) -> BindingSourceKind:
    if isinstance(value, BindingSourceKind):
        source_kind = value
    elif isinstance(value, str):
        try:
            source_kind = BindingSourceKind(value)
        except ValueError as exc:
            raise ValueError(f"retenciones source_kind {value!r} is not a BindingSourceKind") from exc
    else:
        raise ValueError("retenciones source_kind must be a BindingSourceKind or source-kind string")
    if source_kind not in COUNTERPART_SOURCE_KINDS:
        allowed = ", ".join(COUNTERPART_SOURCE_KIND_ORDER)
        raise ValueError(f"retenciones source_kind {source_kind.value!r} is unsupported; use one of {allowed}")
    return source_kind


class RetencionObservation(BaseModel):
    """One typed observation feeding a retenciones aggregator.

    The source ledger transaction (``source_object_id``) is referenced
    by its canonical source kind ``ledger_transaction``. Bare
    ``invoice`` source bindings are forbidden at the registry domain
    layer; observations originating from invoice records carry one of
    ``payable_invoice`` / ``collectible_invoice`` instead.

    ``perceptor_nif`` is normalised to its canonical identity token on
    construction, so the identity this aggregator groups by is the identity
    the encrypted per-perceptor store keys by. Holding the raw declaration
    here split the two: the repository trimmed and uppercased the NIF before
    hashing it into the object key, so two canonically-equal declarations
    produced two rollups and two perceptors in the count while sharing one
    stored row -- the later write overwriting the earlier evidence for a
    perceptor the declaration still counts twice.

    ``accrued_on`` is admitted by the canonical date authority. A ten-character
    length bound is not a date check: ``2026-99-99`` and ``2026-02-30`` both
    satisfy it, and the aggregators then summed and counted a row whose accrual
    date does not exist, with the encrypted store persisting it as declared
    evidence.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    source_object_id: str = Field(min_length=1)
    perceptor_nif: TaxIdIdentityToken = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    taxable_base: Decimal = Field(ge=Decimal("0"))
    retencion_amount: Decimal = Field(ge=Decimal("0"))
    accrued_on: IsoDateString = Field(min_length=10, max_length=10)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> BindingSourceKind:
        return _retenciones_source_kind(value)


class RetencionPerceptorRollup(BaseModel):
    """One row in the aggregation: a perceptor's totals across schemes."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    perceptor_nif: TaxIdIdentityToken = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    observations_count: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_retencion: Decimal = Field(ge=Decimal("0"))

    @field_validator("source_kind", mode="before")
    @classmethod
    def _source_kind_is_canonical(cls, value: object) -> BindingSourceKind:
        return _retenciones_source_kind(value)


class RetencionesAggregation(BaseModel):
    """Aggregate output for a retenciones modelo + period.

    The output is content-addressable: identical input observations
    in any order produce the same rollup tuple (sorted by perceptor +
    scheme) and the same totals.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    period: InstanceOf[Period]
    rollups: tuple[RetencionPerceptorRollup, ...] = Field(default_factory=tuple)
    total_perceptors: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_retencion: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> RetencionesAggregation:
        assert_rollup_totals_match(
            self.rollups,
            checks=(
                ("total_taxable_base", self.total_taxable_base, lambda row: row.total_taxable_base),
                ("total_retencion", self.total_retencion, lambda row: row.total_retencion),
            ),
        )
        unique_perceptors = {row.perceptor_nif for row in self.rollups}
        if len(unique_perceptors) != self.total_perceptors:
            raise ValueError(
                f"total_perceptors {self.total_perceptors} does not match "
                f"distinct perceptor NIFs {len(unique_perceptors)}",
            )
        return self


_MODELO_111_SCHEMES: frozenset[RetencionScheme] = frozenset(
    {
        RetencionScheme.WORK_INCOME,
        RetencionScheme.WORK_INCOME_DIRECTOR,
        RetencionScheme.ECONOMIC_ACTIVITY,
        RetencionScheme.PROFESSIONAL,
        RetencionScheme.PRIZE,
    },
)

_MODELO_115_SCHEMES: frozenset[RetencionScheme] = frozenset(
    {
        RetencionScheme.URBAN_RENTAL,
    },
)

_MODELO_123_SCHEMES: frozenset[RetencionScheme] = frozenset(
    {
        RetencionScheme.CAPITAL_INTEREST,
        RetencionScheme.CAPITAL_DIVIDEND,
        RetencionScheme.CAPITAL_OTHER,
    },
)

# Modelo 180/190/193 are annual summaries of 115/111/123 respectively;
# they consume the same observation set widened over a full year period.
_MODELO_SCHEME_CATALOGUE: dict[str, frozenset[RetencionScheme]] = {
    Modelo.M111.value: _MODELO_111_SCHEMES,
    Modelo.M115.value: _MODELO_115_SCHEMES,
    Modelo.M123.value: _MODELO_123_SCHEMES,
    Modelo.M180.value: _MODELO_115_SCHEMES,
    Modelo.M190.value: _MODELO_111_SCHEMES,
    Modelo.M193.value: _MODELO_123_SCHEMES,
}
RETENCIONES_MODELO_SCHEME_CATALOGUE: Mapping[str, frozenset[RetencionScheme]] = MappingProxyType(
    _MODELO_SCHEME_CATALOGUE,
)


def _aggregate_for_modelo(
    observations: tuple[RetencionObservation, ...],
    *,
    modelo: str,
    period: Period,
) -> RetencionesAggregation:
    """Shared per-modelo aggregation. Filters by scheme catalogue + rolls up.

    Modelo 111 covers WORK_INCOME + ECONOMIC_ACTIVITY + PROFESSIONAL +
    PRIZE. Modelo 115 covers URBAN_RENTAL. Modelo 123 covers capital
    income schemes, and annual summaries 180/190/193 reuse the matching
    quarterly scheme catalogue over an annual period.
    """
    filtered = filter_observations_for_modelo(
        observations,
        modelo=modelo,
        catalogue=_MODELO_SCHEME_CATALOGUE,
        attribute_fn=lambda obs: obs.scheme,
        aggregator_label="retenciones aggregator",
    )
    grouped, perceptor_names = group_and_collect_names(
        filtered,
        group_key_fn=lambda obs: (obs.source_kind, obs.perceptor_nif, obs.scheme),
        identity_key_fn=lambda obs: (obs.source_kind, obs.perceptor_nif),
        name_fn=lambda obs: obs.perceptor_name,
    )
    rollups: list[RetencionPerceptorRollup] = []
    for (source_kind, nif, scheme), group in sorted(
        grouped.items(),
        key=lambda kv: (kv[0][0], kv[0][1], kv[0][2].value),
    ):
        total_base = sum((g.taxable_base for g in group), Decimal("0"))
        total_ret = sum((g.retencion_amount for g in group), Decimal("0"))
        rollups.append(
            RetencionPerceptorRollup(
                source_kind=source_kind,
                perceptor_nif=nif,
                perceptor_name=perceptor_names.get((source_kind, nif), ""),
                scheme=scheme,
                observations_count=len(group),
                total_taxable_base=total_base,
                total_retencion=total_ret,
            ),
        )
    perceptors = {row.perceptor_nif for row in rollups}
    return RetencionesAggregation(
        modelo=modelo,
        period=period,
        rollups=tuple(rollups),
        total_perceptors=len(perceptors),
        total_taxable_base=sum((row.total_taxable_base for row in rollups), Decimal("0")),
        total_retencion=sum((row.total_retencion for row in rollups), Decimal("0")),
    )


def aggregate_retenciones_111(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
) -> RetencionesAggregation:
    """Aggregate per (perceptor_nif, scheme) into a Modelo 111 payload.

    Pure function: identical observation input + period yields identical
    output. Rollups are sorted by (perceptor_nif, scheme.value) so two
    equal aggregations serialise to identical bytes.

    Returns a :class:`RetencionesAggregation`.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M111.value, period=period)


def aggregate_retenciones_115(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
) -> RetencionesAggregation:
    """Aggregate Modelo 115 (retenciones sobre arrendamiento urbano).

    Only ``URBAN_RENTAL`` scheme observations are in scope.

    Returns a :class:`RetencionesAggregation` with per-perceptor rollups
    and grand totals for Modelo 115.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M115.value, period=period)


def aggregate_retenciones_123(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
) -> RetencionesAggregation:
    """Aggregate Modelo 123 retenciones into a :class:`RetencionesAggregation`.

    Covers rendimientos del capital mobiliario: intereses, dividendos, y otros.
    In-scope schemes: CAPITAL_INTEREST, CAPITAL_DIVIDEND, CAPITAL_OTHER.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M123.value, period=period)


def aggregate_retenciones_180(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
) -> RetencionesAggregation:
    """Aggregate Modelo 180 (resumen anual de retenciones sobre arrendamiento urbano).

    Shares the URBAN_RENTAL scheme catalogue with Modelo 115; the
    difference is the period scope (full year vs quarter) which the
    caller supplies. Callers should pass an annual period string
    (e.g. ``"2025"``) and feed in the union of the year's 115
    observations.

    Returns a :class:`RetencionesAggregation`.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M180.value, period=period)


def aggregate_retenciones_190(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
) -> RetencionesAggregation:
    """Aggregate Modelo 190 (resumen anual de retenciones IRPF de Modelo 111).

    Shares the 111 scheme catalogue (WORK_INCOME + ECONOMIC_ACTIVITY +
    PROFESSIONAL + PRIZE) widened over the annual period.

    Returns a :class:`RetencionesAggregation` with per-perceptor rollups
    and grand totals for the annual summary.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M190.value, period=period)


def aggregate_retenciones_193(
    observations: tuple[RetencionObservation, ...],
    *,
    period: Period,
) -> RetencionesAggregation:
    """Aggregate Modelo 193 retenciones into a :class:`RetencionesAggregation`.

    Resumen anual de retenciones sobre capital mobiliario.
    Shares the 123 scheme catalogue.
    """
    return _aggregate_for_modelo(observations, modelo=Modelo.M193.value, period=period)


class RetencionesTotalsParity(BaseModel):
    """Totals-parity verdict between the dedicated per-perceptor retención store and a resumen-anual summary.

    Modelo 193's (and Modelo 180's) monetary resumen casillas
    (``decl.base-total``, ``decl.retenciones-total``) are computed by the
    registry as a SUM of the taxpayer's four Modelo 123 (Modelo 115 for 180)
    quarterly filings (``source = "relation_prefill"``), and the distinct-NIF
    perceptor count (``decl.total-perceptores``) is bound to
    :func:`aggregate_retenciones_193` / :func:`aggregate_retenciones_180` over
    the dedicated per-perceptor retención store
    (:class:`RetencionesAggregation`). Both are independently sourced:
    nothing in the registry cross-checks that the quarterly-relation totals and
    the per-perceptor store's totals agree.

    This model is the pure comparison result of that cross-check: the
    aggregation's ``total_perceptors`` / ``total_taxable_base`` /
    ``total_retencion`` against the resolved summary casilla values.
    ``is_consistent`` is ``True`` only when every delta is within
    ``tolerance`` (the perceptor-count delta is compared as an exact integer
    match) — a divergence on any axis surfaces as a loud, actionable finding
    (``no-silent-under-declaration``), never a silent pass.
    """

    model_config = STRICT_FROZEN_CONFIG

    perceptores_aggregation_total: int = Field(ge=0)
    perceptores_summary_total: int = Field(ge=0)
    perceptores_delta: int
    base_aggregation_total: Decimal = Field(ge=Decimal("0"))
    base_summary_total: Decimal = Field(ge=Decimal("0"))
    base_delta: Decimal
    retenciones_aggregation_total: Decimal = Field(ge=Decimal("0"))
    retenciones_summary_total: Decimal = Field(ge=Decimal("0"))
    retenciones_delta: Decimal
    tolerance: Decimal = Field(ge=Decimal("0"))
    is_consistent: bool


def compute_retenciones_totals_parity(
    aggregation: RetencionesAggregation,
    *,
    perceptores_summary_total: int,
    base_summary_total: Decimal,
    retenciones_summary_total: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> RetencionesTotalsParity:
    """Cross-check a :class:`RetencionesAggregation` against a resumen-anual summary's casillas.

    Args:
        aggregation: The real per-perceptor :class:`RetencionesAggregation`
            (typically :func:`aggregate_retenciones_193` or
            :func:`aggregate_retenciones_180`) built from the dedicated
            per-perceptor retención store for the filing year.
        perceptores_summary_total: The resolved value of casilla
            ``decl.total-perceptores`` (already sourced from the SAME
            aggregation via the ``retenciones_aggregation`` binding, so this
            axis is expected to always match; included for completeness and
            to catch a stale/desynchronised binding read).
        base_summary_total: The resolved value of casilla
            ``decl.base-total`` (the relation-prefill sum of the taxpayer's
            quarterly filings' base casilla).
        retenciones_summary_total: The resolved value of casilla
            ``decl.retenciones-total`` (the relation-prefill sum of the
            taxpayer's quarterly filings' retenciones casilla).
        tolerance: Maximum absolute EUR delta that does not surface a
            divergence on the monetary axes. THE REGISTRY IS THE AUTHORITY FOR
            THIS VALUE and publishes it per revision: resolve it with
            ``snapshot.verification_policy().tolerance`` and pass it. The
            default is exact equality rather than a cent, because Modelo 193's
            own 2025 revision publishes exact equality (``0.00``) -- a
            hardcoded cent here would silently absorb a genuine one-cent
            under-declaration on exactly the modelo this function's own
            docstring names. Modelo 180 publishes ``0.01`` for the same
            comparison shape, which is why the value must be resolved per
            revision rather than assumed constant across both.

    Returns:
        A :class:`RetencionesTotalsParity` verdict. ``is_consistent`` is
        ``False`` whenever the perceptor count differs at all, or either
        monetary total diverges from its corresponding summary casilla by more
        than ``tolerance`` — a dropped or double-counted perceptor row, or a
        quarterly filing missing from the relation-prefill sum, must surface
        as a divergence, never silently collapse into ``is_consistent=True``.
    """
    perceptores_delta = aggregation.total_perceptors - perceptores_summary_total
    base_delta = aggregation.total_taxable_base - base_summary_total
    retenciones_delta = aggregation.total_retencion - retenciones_summary_total
    is_consistent = perceptores_delta == 0 and abs(base_delta) <= tolerance and abs(retenciones_delta) <= tolerance
    return RetencionesTotalsParity(
        perceptores_aggregation_total=aggregation.total_perceptors,
        perceptores_summary_total=perceptores_summary_total,
        perceptores_delta=perceptores_delta,
        base_aggregation_total=aggregation.total_taxable_base,
        base_summary_total=base_summary_total,
        base_delta=base_delta,
        retenciones_aggregation_total=aggregation.total_retencion,
        retenciones_summary_total=retenciones_summary_total,
        retenciones_delta=retenciones_delta,
        tolerance=tolerance,
        is_consistent=is_consistent,
    )


__all__ = [
    "RETENCIONES_MODELO_SCHEME_CATALOGUE",
    "RetencionObservation",
    "RetencionPerceptorRollup",
    "RetencionScheme",
    "RetencionesAggregation",
    "RetencionesTotalsParity",
    "aggregate_retenciones_111",
    "aggregate_retenciones_115",
    "aggregate_retenciones_123",
    "aggregate_retenciones_180",
    "aggregate_retenciones_190",
    "aggregate_retenciones_193",
    "compute_retenciones_totals_parity",
]
