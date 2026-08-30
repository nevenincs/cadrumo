"""Category profile schema consumed by downstream classifiers.

:class:`CategoryProfile` binds a :class:`SpendingCategory` to its display label,
:class:`ProportionalityRule`, and optional :class:`IvaDeductibilityHint`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.i18n import Translatable as tr
from .errors import CategoryValidationError
from .proportionality import ProportionalityRule
from .spending_category import SpendingCategory


class _CategoryProfileStrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = STRICT_FROZEN_CONFIG


class IvaDeductibilityHint(StrEnum):
    """Local IVA hint kept decoupled from the IVA taxonomy branch."""

    GENERAL = "general"
    EXEMPT_OR_NON_SUBJECT = "exempt_or_non_subject"
    NON_DEDUCTIBLE_INPUT = "non_deductible_input"


class CategoryProfile(_CategoryProfileStrictFrozenModel):
    """Explainable category profile for one spending category."""

    category: SpendingCategory
    display_label: tr
    proportionality: ProportionalityRule
    iva_hint: IvaDeductibilityHint | None = None

    @model_validator(mode="after")
    def _validate_profile(self) -> CategoryProfile:
        if not str(self.display_label).strip():
            raise CategoryValidationError("category profile display_label must not be blank")
        return self
