"""Native-to-service startup contract, separate from cadrumo-agent hosting v1."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ServiceStartupFrame(BaseModel):
    """Distinct native-owned admin and gateway secrets; stdin remains the stop signal."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    bearer: Annotated[str, Field(min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")]
    gateway_bearer: Annotated[str, Field(min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")]

    @model_validator(mode="after")
    def distinct_authorities(self) -> ServiceStartupFrame:
        """Refuse a shared secret that would grant the hosted agent administration."""
        if self.bearer == self.gateway_bearer:
            raise ValueError("shared_service_authority")
        return self
