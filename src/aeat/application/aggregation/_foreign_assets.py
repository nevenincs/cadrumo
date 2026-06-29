"""Modelo 720 foreign-assets aggregation for the per-modelo service.

Modelo 720 is an informativa declaration for assets and rights abroad. This
module groups per-asset observations by ``(source_kind, asset_class)`` and
returns :class:`ForeignAssetsAggregation` for
:mod:`aeat.application.aggregation._service`; it is not a live calculate
source-mesh resolver.

Declarability is per asset class. The aggregate keeps raw class totals, and
:func:`declarable_asset_classes_720` applies the EUR 50,000 threshold across all
source-kind cohorts for a class. Observation construction accepts only the four
canonical source-kind values ``ledger_transaction``,
``purchase_invoice_evidence``, ``payable_invoice``, and
``collectible_invoice``; bare ``invoice`` is rejected.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, InstanceOf, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind, Modelo, Period
from ...core.aggregation import ForeignAssetClass
from ...core.external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

_CANONICAL_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_TRANSACTION,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.COLLECTIBLE_INVOICE,
    },
)


def _validate_source_kind(value: str) -> str:
    if value not in _CANONICAL_SOURCE_KINDS:
        raise ValueError(
            "unsupported source_kind; use one of ledger_transaction, "
            "purchase_invoice_evidence, payable_invoice, collectible_invoice",
        )
    return value


def _validate_country(value: str) -> str:
    if len(value) != 2 or any(char < "A" or char > "Z" for char in value):
        raise ValueError(f"country must be uppercase ISO-3166 alpha-2, got {value!r}")
    return value


class ForeignAssetIngestObservation(BaseModel):
    """One asset observation for a Modelo 720 aggregator pass."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    asset_class: ForeignAssetClass
    asset_external_id: str = Field(min_length=1, max_length=128)
    country: str = Field(min_length=2, max_length=2)
    issuer_or_institution: str = Field(default="", max_length=200)
    valuation_eur: Decimal = Field(ge=Decimal("0"))
    acquisition_date: str = Field(min_length=10, max_length=10)
    held_at_year_end: bool = True

    @field_validator("source_kind")
    @classmethod
    def _source_kind_is_canonical(cls, value: str) -> str:
        return _validate_source_kind(value)

    @field_validator("country")
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        return _validate_country(value)


class ForeignAssetClassRollup(BaseModel):
    """Per-source-kind and per-asset-class rollup row."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: str = Field(min_length=1)
    asset_class: ForeignAssetClass
    assets_count: int = Field(ge=0)
    held_at_year_end_count: int = Field(ge=0)
    total_valuation_eur: Decimal = Field(ge=Decimal("0"))
    countries: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("countries")
    @classmethod
    def _countries_are_uppercase_ascii_alpha2(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for country in value:
            _validate_country(country)
        return value

    @field_validator("source_kind")
    @classmethod
    def _source_kind_is_canonical(cls, value: str) -> str:
        return _validate_source_kind(value)

    @model_validator(mode="after")
    def _held_count_within_total(self) -> ForeignAssetClassRollup:
        if self.held_at_year_end_count > self.assets_count:
            raise ValueError(
                f"held_at_year_end_count {self.held_at_year_end_count} > assets_count {self.assets_count}",
            )
        return self


class ForeignAssetsAggregation(BaseModel):
    """720 aggregation output: per-class rollups + cross-class totals."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    period: InstanceOf[Period]
    rollups: tuple[ForeignAssetClassRollup, ...] = Field(default_factory=tuple)
    total_assets: int = Field(ge=0)
    total_valuation_eur: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> ForeignAssetsAggregation:
        computed_assets = sum(row.assets_count for row in self.rollups)
        computed_valuation = sum(
            (row.total_valuation_eur for row in self.rollups),
            Decimal("0"),
        )
        if computed_assets != self.total_assets:
            raise ValueError(
                f"total_assets {self.total_assets} != sum of rollups {computed_assets}",
            )
        if computed_valuation != self.total_valuation_eur:
            raise ValueError(
                f"total_valuation_eur {self.total_valuation_eur} != sum of rollups {computed_valuation}",
            )
        cohorts = [(row.source_kind, row.asset_class) for row in self.rollups]
        if len(cohorts) != len(set(cohorts)):
            raise ValueError("each source_kind and ForeignAssetClass cohort may appear at most once in rollups")
        return self


def declarable_asset_classes_720(aggregation: ForeignAssetsAggregation) -> frozenset[ForeignAssetClass]:
    """Return asset classes whose full valuation exceeds the 720 declaration floor.

    Returns a frozenset of :class:`ForeignAssetClass` members.
    """
    totals: dict[ForeignAssetClass, Decimal] = {}
    for rollup in aggregation.rollups:
        totals[rollup.asset_class] = totals.get(rollup.asset_class, Decimal("0")) + rollup.total_valuation_eur
    return frozenset(asset_class for asset_class, total in totals.items() if total > MODELO_720_REPORTING_THRESHOLD_EUR)


def declarable_class(aggregation: ForeignAssetsAggregation, *, asset_class: ForeignAssetClass) -> bool:
    """Return True iff an asset class crosses the 720 declaration floor across all cohorts."""
    return asset_class in declarable_asset_classes_720(aggregation)


def aggregate_foreign_assets_720(
    observations: tuple[ForeignAssetIngestObservation, ...],
    *,
    period: Period,
) -> ForeignAssetsAggregation:
    """Aggregate Modelo 720 observations into per-class rollups.

    Returns a :class:`ForeignAssetsAggregation` grouping observations
    by asset class. Pure function: identical observation input + period
    yields identical output. Rollups are sorted by asset_class.value so
    two equal aggregations serialise to identical bytes.

    No threshold gate is applied here; callers use
    :func:`declarable_class` to filter rollups before binding to
    Modelo 720 casillas.
    """
    grouped: dict[tuple[str, ForeignAssetClass], list[ForeignAssetIngestObservation]] = {}
    for obs in observations:
        grouped.setdefault((obs.source_kind, obs.asset_class), []).append(obs)
    rollups: list[ForeignAssetClassRollup] = []
    for source_kind, asset_class in sorted(grouped, key=lambda c: (c[0], c[1].value)):
        group = grouped[(source_kind, asset_class)]
        countries = tuple(sorted({obs.country for obs in group}))
        rollups.append(
            ForeignAssetClassRollup(
                source_kind=source_kind,
                asset_class=asset_class,
                assets_count=len(group),
                held_at_year_end_count=sum(1 for o in group if o.held_at_year_end),
                total_valuation_eur=sum(
                    (obs.valuation_eur for obs in group),
                    Decimal("0"),
                ),
                countries=countries,
            ),
        )
    return ForeignAssetsAggregation(
        modelo=Modelo.M720.value,
        period=period,
        rollups=tuple(rollups),
        total_assets=sum(row.assets_count for row in rollups),
        total_valuation_eur=sum(
            (row.total_valuation_eur for row in rollups),
            Decimal("0"),
        ),
    )


__all__ = [
    "ForeignAssetClass",
    "ForeignAssetClassRollup",
    "ForeignAssetIngestObservation",
    "ForeignAssetsAggregation",
    "aggregate_foreign_assets_720",
    "declarable_asset_classes_720",
    "declarable_class",
]
