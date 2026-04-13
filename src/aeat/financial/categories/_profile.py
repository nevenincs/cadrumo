"""Category profile schema consumed by downstream T4 classifiers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aeat.i18n import Translatable, require_authoritative

from ._casilla_mapping import CasillaMapping
from ._proportionality import ProportionalityRule
from ._spending_category import SpendingCategory


class _StrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = ConfigDict(strict=True, frozen=True)


class VatCategory(StrEnum):
    """Local VAT hint stub kept decoupled from the VAT taxonomy branch."""

    GENERAL = "general"
    EXEMPT_OR_NON_SUBJECT = "exempt_or_non_subject"
    NON_DEDUCTIBLE_INPUT = "non_deductible_input"


class CategoryProfile(_StrictFrozenModel):
    """Explainable category profile for one spending category."""

    category: SpendingCategory
    display_label: Translatable
    proportionality: ProportionalityRule
    casilla_mappings: tuple[CasillaMapping, ...] = Field(default_factory=tuple)
    vat_hint: VatCategory | None = None

    @model_validator(mode="after")
    def _validate_profile(self) -> CategoryProfile:
        try:
            require_authoritative(self.display_label, domain="aeat")
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        if not self.casilla_mappings:
            raise ValueError("category profiles require at least one casilla mapping")
        seen: set[tuple[str, str, str]] = set()
        for mapping in self.casilla_mappings:
            key = (mapping.modelo.value, mapping.period_type.value, mapping.casilla_code)
            if key in seen:
                raise ValueError("duplicate casilla mapping detected")
            seen.add(key)
        return self
