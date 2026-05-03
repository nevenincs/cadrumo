"""Category profile schema consumed by downstream classifiers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ...core.i18n import Translatable, TranslationError, require_authoritative
from ._proportionality import ProportionalityRule
from ._spending_category import SpendingCategory


class _CategoryProfileStrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class VatCategory(StrEnum):
    """Local VAT hint kept decoupled from the VAT taxonomy branch."""

    GENERAL = "general"
    EXEMPT_OR_NON_SUBJECT = "exempt_or_non_subject"
    NON_DEDUCTIBLE_INPUT = "non_deductible_input"


class CategoryProfile(_CategoryProfileStrictFrozenModel):
    """Explainable category profile for one spending category."""

    category: SpendingCategory
    display_label: Translatable
    proportionality: ProportionalityRule
    vat_hint: VatCategory | None = None

    @model_validator(mode="after")
    def _validate_profile(self) -> CategoryProfile:
        try:
            require_authoritative(self.display_label, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return self
