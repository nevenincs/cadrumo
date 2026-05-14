"""Retenciones aggregator for Modelo 111 (withholding on labor + economic activities).

Implements the slim aggregation contract for the retenciones family
per apex §12 R21 and the per-modelo-aggregation-pipeline ADR. The
aggregator consumes typed observations carrying the canonical source
kind (``ledger_transaction``) and produces per-perceptor rollups
plus a totals payload suitable for Modelo 111 binding consumption.

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


class RetencionScheme(StrEnum):
    """Closed catalogue of retenciones schemes covered by Modelo 111.

    Source: AEAT Modelo 111 instrucciones (claves de retención).
    Each scheme maps to one of the casillas (or grouped casillas)
    on the Modelo 111 form.
    """

    WORK_INCOME = "rendimientos_trabajo"        # clave A
    ECONOMIC_ACTIVITY = "actividades_economicas"  # clave G
    PROFESSIONAL = "actividades_profesionales"   # clave H (subset of G)
    PRIZE = "premios"                            # clave I (lottery, prize)


class RetencionObservation(BaseModel):
    """One typed observation feeding a retenciones aggregator.

    The source ledger transaction (``source_object_id``) is referenced
    by its canonical source kind ``ledger_transaction`` per apex §2.
    Bare ``invoice`` source bindings are forbidden at the registry
    domain layer; observations originating from invoice records carry
    one of ``payable_invoice`` / ``collectible_invoice`` instead.
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
        return value


class RetencionPerceptorRollup(BaseModel):
    """One row in the aggregation: a perceptor's totals across schemes."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
    def _totals_match_rollups(self) -> "RetencionesAggregation":
        computed_base = sum((row.total_taxable_base for row in self.rollups), Decimal("0"))
        computed_ret = sum((row.total_retencion for row in self.rollups), Decimal("0"))
        if computed_base != self.total_taxable_base:
            raise ValueError(
                f"total_taxable_base {self.total_taxable_base} does not match "
                f"sum of rollups {computed_base}",
            )
        if computed_ret != self.total_retencion:
            raise ValueError(
                f"total_retencion {self.total_retencion} does not match "
                f"sum of rollups {computed_ret}",
            )
        unique_perceptors = {row.perceptor_nif for row in self.rollups}
        if len(unique_perceptors) != self.total_perceptors:
            raise ValueError(
                f"total_perceptors {self.total_perceptors} does not match "
                f"distinct perceptor NIFs {len(unique_perceptors)}",
            )
        return self


def _filter_observations_for_modelo(
    observations: tuple[RetencionObservation, ...],
    modelo: str,
) -> tuple[RetencionObservation, ...]:
    """Filter observations to those whose scheme is in-scope for ``modelo``.

    Modelo 111 covers WORK_INCOME + ECONOMIC_ACTIVITY +
    PROFESSIONAL + PRIZE. Other modelos (115/123/180/190/193) use
    different scheme catalogues; their entry points filter their own
    in-scope sets.
    """
    if modelo == "111":
        eligible = frozenset(RetencionScheme)
    else:
        msg = f"retenciones aggregator for modelo {modelo!r} is not implemented"
        raise NotImplementedError(msg)
    return tuple(o for o in observations if o.scheme in eligible)


def aggregate_retenciones_111(
    observations: tuple[RetencionObservation, ...],
    *,
    period: str,
) -> RetencionesAggregation:
    """Aggregate per (perceptor_nif, scheme) into a Modelo 111 payload.

    The function is pure: identical observation input + period yields
    identical output. Rollups are sorted by (perceptor_nif, scheme.value)
    so two equal aggregations serialise to identical bytes.
    """
    filtered = _filter_observations_for_modelo(observations, modelo="111")
    grouped: dict[tuple[str, RetencionScheme], list[RetencionObservation]] = {}
    perceptor_names: dict[str, str] = {}
    for obs in filtered:
        key = (obs.perceptor_nif, obs.scheme)
        grouped.setdefault(key, []).append(obs)
        if obs.perceptor_name and not perceptor_names.get(obs.perceptor_nif):
            perceptor_names[obs.perceptor_nif] = obs.perceptor_name
    rollups: list[RetencionPerceptorRollup] = []
    for (nif, scheme), group in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1].value)):
        total_base = sum((g.taxable_base for g in group), Decimal("0"))
        total_ret = sum((g.retencion_amount for g in group), Decimal("0"))
        rollups.append(
            RetencionPerceptorRollup(
                perceptor_nif=nif,
                perceptor_name=perceptor_names.get(nif, ""),
                scheme=scheme,
                observations_count=len(group),
                total_taxable_base=total_base,
                total_retencion=total_ret,
            ),
        )
    perceptors = {row.perceptor_nif for row in rollups}
    return RetencionesAggregation(
        modelo="111",
        period=period,
        rollups=tuple(rollups),
        total_perceptors=len(perceptors),
        total_taxable_base=sum((row.total_taxable_base for row in rollups), Decimal("0")),
        total_retencion=sum((row.total_retencion for row in rollups), Decimal("0")),
    )


__all__ = [
    "RetencionesAggregation",
    "RetencionObservation",
    "RetencionPerceptorRollup",
    "RetencionScheme",
    "aggregate_retenciones_111",
]
