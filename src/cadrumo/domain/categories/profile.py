"""Category profile schema consumed by downstream classifiers.

:class:`CategoryProfile` binds a :class:`SpendingCategory` to its display label,
:class:`ProportionalityRule`, and optional :class:`IvaDeductibilityHint`.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from ...core.i18n.translatable import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import CategoryValidationError
from .proportionality import ProportionalityRule
from .spending_category import SpendingCategory


class _CategoryProfileStrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = STRICT_FROZEN_CONFIG


class IvaDeductibilityHint(str):
    """Opaque registry-projected IVA deductibility hint token."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a string to Pydantic without a catalogue."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @property
    def value(self) -> str:
        """Return the opaque token for string-oriented serialization."""
        return str(self)


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
