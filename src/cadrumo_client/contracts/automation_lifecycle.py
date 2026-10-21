"""Neutral messages for protected automation lifecycle operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class HumanSignInRevocationResult(BaseModel):
    """Physical cleanup after a durable human-sign-in fence, never a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    receipt_removed: bool
    keychain_removed: bool


class AutomationResumeRequest(BaseModel):
    """One exact reviewed selection, bounded by the suspended control generation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    lock_generation: Annotated[int, Field(ge=0)]
    grants: frozenset[UUID]


class AutomationResumeReceipt(BaseModel):
    """Selected grants retain their original permissions and calendar deadlines."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    revision: Annotated[int, Field(ge=1)] | None
    lock_generation: Annotated[int, Field(ge=0)]
    reactivated_grants: frozenset[UUID]
    human_sign_in_revocation: HumanSignInRevocationResult | None = None
