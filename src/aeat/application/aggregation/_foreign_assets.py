"""Modelo 720 foreign-assets aggregator.

Modelo 720: Declaración informativa sobre bienes y derechos situados en el
extranjero. Per-asset records grouped by asset class. Each class carries
a €50,000 valuation threshold; declarability is per-class, not per-asset.

Per apex §12 R21 and the per-modelo-aggregation-pipeline ADR. Bare
``invoice`` source-kind is rejected at observation construction; the
four canonical source kinds (ledger_transaction, purchase_invoice_evidence,
payable_invoice, collectible_invoice) plus the asset-specific source
kinds (rental_register, foreign_account_statement, etc.) are accepted.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ForeignAssetClass(StrEnum):
    """Modelo 720 asset classes (clave de tipo de bien).

    Source: AEAT Modelo 720 instrucciones. Each class is declared
    separately; declarability gate (€50,000 per class) is applied
    after the aggregator runs.
    """

    ACCOUNT = "cuenta_entidad_financiera"          # clave C
    SECURITY = "valor_seguro_renta"                 # clave V
    REAL_ESTATE = "inmueble_extranjero"             # clave I
    INSURANCE = "seguro_renta_temporal_vitalicia"   # clave S
    VIRTUAL_CURRENCY = "moneda_virtual"             # clave M


class ForeignAssetObservation(BaseModel):
    """One asset observation for a Modelo 720 aggregator pass."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
    def _reject_bare_invoice_source(cls, value: str) -> str:
        if value == "invoice":
            raise ValueError(
                "bare 'invoice' source-kind is forbidden; use ledger_transaction, "
                "purchase_invoice_evidence, payable_invoice, or collectible_invoice",
            )
        return value

    @field_validator("country")
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError(f"country must be uppercase ISO-3166 alpha-2, got {value!r}")
        return value


class ForeignAssetClassRollup(BaseModel):
    """Per-asset-class rollup row in the Modelo 720 aggregation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_class: ForeignAssetClass
    assets_count: int = Field(ge=0)
    held_at_year_end_count: int = Field(ge=0)
    total_valuation_eur: Decimal = Field(ge=Decimal("0"))
    countries: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _held_count_within_total(self) -> "ForeignAssetClassRollup":
        if self.held_at_year_end_count > self.assets_count:
            raise ValueError(
                f"held_at_year_end_count {self.held_at_year_end_count} > assets_count "
                f"{self.assets_count}",
            )
        return self


class ForeignAssetsAggregation(BaseModel):
    """720 aggregation output: per-class rollups + cross-class totals."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    rollups: tuple[ForeignAssetClassRollup, ...] = Field(default_factory=tuple)
    total_assets: int = Field(ge=0)
    total_valuation_eur: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> "ForeignAssetsAggregation":
        computed_assets = sum(row.assets_count for row in self.rollups)
        computed_valuation = sum(
            (row.total_valuation_eur for row in self.rollups), Decimal("0"),
        )
        if computed_assets != self.total_assets:
            raise ValueError(
                f"total_assets {self.total_assets} != sum of rollups {computed_assets}",
            )
        if computed_valuation != self.total_valuation_eur:
            raise ValueError(
                f"total_valuation_eur {self.total_valuation_eur} != sum of rollups "
                f"{computed_valuation}",
            )
        # No two rollups may share an asset_class (one row per class).
        classes = [row.asset_class for row in self.rollups]
        if len(classes) != len(set(classes)):
            raise ValueError("each ForeignAssetClass may appear at most once in rollups")
        return self


THRESHOLD_720_EUR_PER_CLASS: Decimal = Decimal("50000.00")
"""Modelo 720 declaration floor per asset class: a class is declarable iff
its total valuation strictly exceeds this amount per AEAT instrucciones."""


def declarable_class(rollup: ForeignAssetClassRollup) -> bool:
    """Return True iff the asset class crosses the 720 declaration floor."""
    return rollup.total_valuation_eur > THRESHOLD_720_EUR_PER_CLASS


def aggregate_foreign_assets_720(
    observations: tuple[ForeignAssetObservation, ...],
    *,
    period: str,
) -> ForeignAssetsAggregation:
    """Aggregate Modelo 720 observations into per-class rollups.

    Pure function: identical observation input + period yields
    identical output. Rollups are sorted by asset_class.value so two
    equal aggregations serialise to identical bytes.

    No threshold gate is applied here; callers use
    :func:`declarable_class` to filter rollups before binding to
    Modelo 720 casillas.
    """
    grouped: dict[ForeignAssetClass, list[ForeignAssetObservation]] = {}
    for obs in observations:
        grouped.setdefault(obs.asset_class, []).append(obs)
    rollups: list[ForeignAssetClassRollup] = []
    for asset_class in sorted(grouped, key=lambda c: c.value):
        group = grouped[asset_class]
        countries = tuple(sorted({obs.country for obs in group}))
        rollups.append(
            ForeignAssetClassRollup(
                asset_class=asset_class,
                assets_count=len(group),
                held_at_year_end_count=sum(1 for o in group if o.held_at_year_end),
                total_valuation_eur=sum(
                    (obs.valuation_eur for obs in group), Decimal("0"),
                ),
                countries=countries,
            ),
        )
    return ForeignAssetsAggregation(
        modelo="720",
        period=period,
        rollups=tuple(rollups),
        total_assets=sum(row.assets_count for row in rollups),
        total_valuation_eur=sum(
            (row.total_valuation_eur for row in rollups), Decimal("0"),
        ),
    )


__all__ = [
    "ForeignAssetClass",
    "ForeignAssetClassRollup",
    "ForeignAssetObservation",
    "ForeignAssetsAggregation",
    "THRESHOLD_720_EUR_PER_CLASS",
    "aggregate_foreign_assets_720",
    "declarable_class",
]
