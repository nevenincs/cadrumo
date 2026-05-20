"""Retenciones aggregator for Modelo 111 (withholding on labor + economic activities).

Implements the slim aggregation contract for the retenciones family.
The aggregator consumes typed observations carrying the canonical
source kind (``ledger_transaction``) and produces per-perceptor
rollups plus a totals payload suitable for Modelo 111 binding
consumption.

This module is the contract layer; the bridge from
:class:`Transaction` records to :class:`RetencionObservation`
instances lives in an upstream binding provider that the modelo
calculation entry point invokes. Keeping the aggregator pure-function
makes it trivially testable and forward-compatible with the
remaining retenciones modelos (115, 123, 180, 190, 193).
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._grouping import filter_observations_for_modelo, group_and_collect_names


class RetencionScheme(StrEnum):
    """Closed catalogue of retenciones schemes across the retenciones family.

    Each scheme maps to one of the casillas (or grouped casillas) on
    a retenciones modelo form. The mapping from scheme to modelo lives
    in the per-modelo entry-point functions; this enum is the union.
    """

    # Modelo 111 schemes (quarterly retenciones IRPF on labor + activities)
    WORK_INCOME = "rendimientos_trabajo"  # clave A
    ECONOMIC_ACTIVITY = "actividades_economicas"  # clave G
    PROFESSIONAL = "actividades_profesionales"  # clave H (subset of G)
    PRIZE = "premios"  # clave I (lottery, prize)
    # Modelo 115 schemes (urban rental withholding)
    URBAN_RENTAL = "arrendamiento_urbano"  # locales de negocio
    # Modelo 123 schemes (capital mobiliario, dividends, interest)
    CAPITAL_INTEREST = "intereses"  # clave I (interest income)
    CAPITAL_DIVIDEND = "dividendos"  # clave A (dividend income)
    CAPITAL_OTHER = "otros_capital_mobiliario"  # clave C (other capital income)


_CANONICAL_SOURCE_KINDS = (
    "ledger_transaction",
    "purchase_invoice_evidence",
    "payable_invoice",
    "collectible_invoice",
)


class RetencionObservation(BaseModel):
    """One typed observation feeding a retenciones aggregator.

    The source ledger transaction (``source_object_id``) is referenced
    by its canonical source kind ``ledger_transaction``. Bare
    ``invoice`` source bindings are forbidden at the registry domain
    layer; observations originating from invoice records carry one of
    ``payable_invoice`` / ``collectible_invoice`` instead.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_kind: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    perceptor_nif: str = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    taxable_base: Decimal = Field(ge=Decimal("0"))
    retencion_amount: Decimal = Field(ge=Decimal("0"))
    accrued_on: str = Field(min_length=10, max_length=10)  # ISO YYYY-MM-DD

    @field_validator("source_kind")
    @classmethod
    def _reject_bare_invoice_source(cls, value: str) -> str:
        if value == "invoice":
            raise ValueError(
                "bare 'invoice' source-kind is forbidden; use ledger_transaction, "
                "purchase_invoice_evidence, payable_invoice, or collectible_invoice",
            )
        if value not in _CANONICAL_SOURCE_KINDS:
            allowed = ", ".join(_CANONICAL_SOURCE_KINDS)
            raise ValueError(f"retenciones source_kind {value!r} is unsupported; use one of {allowed}")
        return value


class RetencionPerceptorRollup(BaseModel):
    """One row in the aggregation: a perceptor's totals across schemes."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_kind: str = Field(min_length=1)
    perceptor_nif: str = Field(min_length=1, max_length=16)
    perceptor_name: str = Field(default="", max_length=200)
    scheme: RetencionScheme
    observations_count: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_retencion: Decimal = Field(ge=Decimal("0"))


class RetencionesAggregation(BaseModel):
    """Aggregate output for a retenciones modelo + period.

    The output is content-addressable: identical input observations
    in any order produce the same rollup tuple (sorted by perceptor +
    scheme) and the same totals.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    rollups: tuple[RetencionPerceptorRollup, ...] = Field(default_factory=tuple)
    total_perceptors: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_retencion: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> RetencionesAggregation:
        computed_base = sum((row.total_taxable_base for row in self.rollups), Decimal("0"))
        computed_ret = sum((row.total_retencion for row in self.rollups), Decimal("0"))
        if computed_base != self.total_taxable_base:
            raise ValueError(
                f"total_taxable_base {self.total_taxable_base} does not match sum of rollups {computed_base}",
            )
        if computed_ret != self.total_retencion:
            raise ValueError(
                f"total_retencion {self.total_retencion} does not match sum of rollups {computed_ret}",
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
        RetencionScheme.ECONOMIC_ACTIVITY,
        RetencionScheme.PROFESSIONAL,
        RetencionScheme.PRIZE,
    }
)

_MODELO_115_SCHEMES: frozenset[RetencionScheme] = frozenset(
    {
        RetencionScheme.URBAN_RENTAL,
    }
)

_MODELO_123_SCHEMES: frozenset[RetencionScheme] = frozenset(
    {
        RetencionScheme.CAPITAL_INTEREST,
        RetencionScheme.CAPITAL_DIVIDEND,
        RetencionScheme.CAPITAL_OTHER,
    }
)

# Modelo 180/190/193 are annual summaries of 115/111/123 respectively;
# they consume the same observation set widened over a full year period.
_MODELO_SCHEME_CATALOGUE: dict[str, frozenset[RetencionScheme]] = {
    "111": _MODELO_111_SCHEMES,
    "115": _MODELO_115_SCHEMES,
    "123": _MODELO_123_SCHEMES,
    "180": _MODELO_115_SCHEMES,
    "190": _MODELO_111_SCHEMES,
    "193": _MODELO_123_SCHEMES,
}


def _aggregate_for_modelo(
    observations: tuple[RetencionObservation, ...],
    *,
    modelo: str,
    period: str,
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
        grouped.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2].value)
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
    period: str,
) -> RetencionesAggregation:
    """Aggregate per (perceptor_nif, scheme) into a Modelo 111 payload.

    Pure function: identical observation input + period yields identical
    output. Rollups are sorted by (perceptor_nif, scheme.value) so two
    equal aggregations serialise to identical bytes.
    """
    return _aggregate_for_modelo(observations, modelo="111", period=period)


def aggregate_retenciones_115(
    observations: tuple[RetencionObservation, ...],
    *,
    period: str,
) -> RetencionesAggregation:
    """Aggregate Modelo 115 (retenciones sobre arrendamiento urbano).

    Only ``URBAN_RENTAL`` scheme observations are in scope.
    """
    return _aggregate_for_modelo(observations, modelo="115", period=period)


def aggregate_retenciones_123(
    observations: tuple[RetencionObservation, ...],
    *,
    period: str,
) -> RetencionesAggregation:
    """Aggregate Modelo 123 (retenciones sobre rendimientos del capital mobiliario:
    intereses, dividendos, otros).

    In-scope schemes: CAPITAL_INTEREST, CAPITAL_DIVIDEND, CAPITAL_OTHER.
    """
    return _aggregate_for_modelo(observations, modelo="123", period=period)


def aggregate_retenciones_180(
    observations: tuple[RetencionObservation, ...],
    *,
    period: str,
) -> RetencionesAggregation:
    """Aggregate Modelo 180 (resumen anual de retenciones sobre arrendamiento urbano).

    Shares the URBAN_RENTAL scheme catalogue with Modelo 115; the
    difference is the period scope (full year vs quarter) which the
    caller supplies. Callers should pass an annual period string
    (e.g. ``"2025"``) and feed in the union of the year's 115
    observations.
    """
    return _aggregate_for_modelo(observations, modelo="180", period=period)


def aggregate_retenciones_190(
    observations: tuple[RetencionObservation, ...],
    *,
    period: str,
) -> RetencionesAggregation:
    """Aggregate Modelo 190 (resumen anual de retenciones IRPF de Modelo 111).

    Shares the 111 scheme catalogue (WORK_INCOME + ECONOMIC_ACTIVITY +
    PROFESSIONAL + PRIZE) widened over the annual period.
    """
    return _aggregate_for_modelo(observations, modelo="190", period=period)


def aggregate_retenciones_193(
    observations: tuple[RetencionObservation, ...],
    *,
    period: str,
) -> RetencionesAggregation:
    """Aggregate Modelo 193 (resumen anual de retenciones sobre capital mobiliario).

    Shares the 123 scheme catalogue.
    """
    return _aggregate_for_modelo(observations, modelo="193", period=period)


__all__ = [
    "RetencionObservation",
    "RetencionPerceptorRollup",
    "RetencionScheme",
    "RetencionesAggregation",
    "aggregate_retenciones_111",
    "aggregate_retenciones_115",
    "aggregate_retenciones_123",
    "aggregate_retenciones_180",
    "aggregate_retenciones_190",
    "aggregate_retenciones_193",
]
