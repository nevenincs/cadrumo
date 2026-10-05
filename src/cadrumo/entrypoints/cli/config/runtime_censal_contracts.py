"""Censal review output and mutable terminal-receipt custody."""

from __future__ import annotations

from dataclasses import dataclass

from ....application.user_profile.censal_operation import (
    CensalReviewProjectionV1,
)
from ....core.operations import OperationEffect, OperationTerminalCondition


@dataclass(frozen=True, slots=True)
class CensalRuntimeReviewResult:
    """The exact reviewed proposal and the outcome the runtime applied."""

    projection: CensalReviewProjectionV1
    applied: bool


@dataclass(slots=True)
class _CensalReceiptState:
    """Latest admitted terminal facts retained across submitted-operation failures."""

    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    refusal_code: str | None = None
