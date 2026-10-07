"""Typed registered CLI completion, operator review and observed-progress contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from ...application.operations.events import OperationEventCode
from ...application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from ...application.operations.models import OperationId
from ...application.operations.schema_identity import OperationSchemaIdentityV1
from ...core.operations import OperationEffect, OperationTerminalCondition


@dataclass(slots=True)
class RegisteredOperationProgress:
    """Retain only the observed condition, effect and refusal across transport failures."""

    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    refusal_code: str | None = None


@dataclass(frozen=True, slots=True)
class RegisteredOperationCompletion[ResultT: BaseModel]:
    """One registered result and the effect that settled its exact operation."""

    operation_id: OperationId
    projection: ResultT
    effect: OperationEffect
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED
    refusal_code: str | None = None


@dataclass(frozen=True, slots=True)
class RegisteredOperationReviewHandler[ReviewT: BaseModel]:
    """Bind a typed registered review to an explicit operator decision."""

    review_type: type[ReviewT]
    review_schema: OperationSchemaIdentityV1
    response_schema: OperationSchemaIdentityV1
    decide: Callable[[ReviewT], Literal["apply", "reject"] | None]
    reject_reason_code: OperationEventCode | None = None
    validate_reference: Callable[[ReviewT, OperationReviewProjectionReferenceV1], None] | None = None


@dataclass(frozen=True, slots=True)
class RegisteredOperationReviewCompletion[ReviewT: BaseModel]:
    """A detached pending review, without claiming a terminal outcome."""

    operation_id: OperationId
    review: ReviewT
    effect: OperationEffect
