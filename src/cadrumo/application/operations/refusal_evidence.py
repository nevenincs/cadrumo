"""Explicit, encrypted explanatory evidence for a refused operation."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, field_validator, model_validator

from ...core.errors.error_codes import ErrorCategory, current_error_code, get_registered_error_code_by_code
from ...core.errors.hierarchy import InternalInvariantError
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .models import OperationFailureErrorCode, OperationReference


def validate_refusal_code(code: str) -> None:
    """Require one canonical refusal code without accepting exception content."""
    try:
        registered = get_registered_error_code_by_code(code)
    except InternalInvariantError:
        raise ValueError("operation refusal evidence requires a registered refusal code") from None
    if registered.category is not ErrorCategory.REFUSED:
        raise ValueError("operation refusal evidence requires a registered refusal code")


class OperationRefusalEvidence(BaseModel):
    """Executor-returned references; only the supervisor may settle the refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    refusal_code: OperationFailureErrorCode
    detail_ref: ContentDigest

    @field_validator("refusal_code", mode="before")
    @classmethod
    def _read_retired_code_as_its_successor(cls, value: object) -> object:
        return current_error_code(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _registered_refusal(self) -> Self:
        validate_refusal_code(self.refusal_code)
        return self


type OperationExecutorResult = OperationReference | OperationRefusalEvidence | None
"""One completed executor outcome or an intentionally unsettled continuation."""
