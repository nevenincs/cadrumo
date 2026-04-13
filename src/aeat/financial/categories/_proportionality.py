"""Proportionality and explainability primitives for category profiles."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class _StrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = ConfigDict(strict=True, frozen=True)


class CitationSource(StrEnum):
    """Allowed citation sources for explainable category profiles."""

    MANUAL_RENTA = "manual_renta"
    MANUAL_IVA = "manual_iva"
    LEY_IRPF = "ley_irpf"
    REGLAMENTO_IRPF = "reglamento_irpf"
    AEAT_HELP = "aeat_help"


class Citation(_StrictFrozenModel):
    """A traceable citation backing one category or proportionality rule."""

    source: CitationSource
    reference: str = Field(min_length=1, max_length=256)
    locator: str = Field(min_length=1, max_length=256)
    url: AnyHttpUrl
    quote_es: str = Field(min_length=1, max_length=1024)


_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def parse_http_url(value: str) -> AnyHttpUrl:
    """Parse a string into a statically typed :class:`AnyHttpUrl`."""

    return _HTTP_URL_ADAPTER.validate_python(value)


class ProportionalityKind(StrEnum):
    """Supported proportionality kinds for downstream evaluator engines."""

    FULL_DEDUCTIBLE = "full_deductible"
    FIXED_PERCENTAGE = "fixed_percentage"
    USAGE_RATIO_PERSONAL = "usage_ratio_personal"
    USAGE_RATIO_HOME_AREA = "usage_ratio_home_area"
    STATUTORY_CAP = "statutory_cap"
    NON_DEDUCTIBLE = "non_deductible"


class StatutoryCapPeriod(StrEnum):
    """Supported statutory-cap periods."""

    DAY = "day"
    YEAR_PER_PERSON = "year_per_person"


class ProportionalityRule(_StrictFrozenModel):
    """Deductibility and proportionality rule for one spending category."""

    kind: ProportionalityKind
    fixed_pct: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    default_ratio: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    statutory_cap_eur_per_day: Decimal | None = Field(default=None, ge=Decimal("0"))
    statutory_cap_eur: Decimal | None = Field(default=None, ge=Decimal("0"))
    statutory_cap_period: StatutoryCapPeriod | None = None
    citations: tuple[Citation, ...] = Field(default_factory=tuple)
    notes_es: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def _validate_shape(self) -> ProportionalityRule:
        if not self.citations:
            raise ValueError("proportionality rules require at least one citation")
        if self.kind is ProportionalityKind.FIXED_PERCENTAGE and self.fixed_pct is None:
            raise ValueError("fixed_percentage rules require fixed_pct")
        if self.kind is not ProportionalityKind.FIXED_PERCENTAGE and self.fixed_pct is not None:
            raise ValueError("fixed_pct is only valid for fixed_percentage rules")
        is_usage_ratio = self.kind in {
            ProportionalityKind.USAGE_RATIO_HOME_AREA,
            ProportionalityKind.USAGE_RATIO_PERSONAL,
        }
        if not is_usage_ratio and self.default_ratio is not None:
            raise ValueError("default_ratio is only valid for usage_ratio rules")
        has_daily_cap = self.statutory_cap_eur_per_day is not None
        has_generic_cap = self.statutory_cap_eur is not None or self.statutory_cap_period is not None
        if self.kind is ProportionalityKind.STATUTORY_CAP:
            if not has_daily_cap and not has_generic_cap:
                raise ValueError("statutory_cap rules require a cap amount")
            if has_daily_cap and has_generic_cap:
                raise ValueError("statutory cap rules must use either daily or generic cap fields, not both")
            if self.statutory_cap_eur is None and self.statutory_cap_period is not None:
                raise ValueError("statutory_cap_period requires statutory_cap_eur")
            if self.statutory_cap_eur is not None and self.statutory_cap_period is None:
                raise ValueError("statutory_cap_eur requires statutory_cap_period")
            return self
        if has_daily_cap:
            raise ValueError("statutory_cap_eur_per_day is only valid for statutory_cap rules")
        if self.statutory_cap_eur is not None:
            raise ValueError("statutory_cap_eur is only valid for statutory_cap rules")
        if self.statutory_cap_period is not None:
            raise ValueError("statutory_cap_period is only valid for statutory_cap rules")
        return self
