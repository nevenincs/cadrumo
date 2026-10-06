"""Nonsecret authentication refusal facts shared by runtime and interactive clients."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal


class SignInRefusal(BaseModel):
    """Preserve receipt provenance and throttling without diagnostic strings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    reason: ProfileSessionRefusalReason | Literal["throttled"]
    binding: ReceiptBindingRefusal | None = None
    remaining_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _throttle_time(self) -> "SignInRefusal":
        if (self.reason == "throttled") != (self.remaining_seconds is not None):
            raise ValueError("remaining time is required exactly for throttling")
        return self
