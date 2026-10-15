"""Native-to-service startup contract, separate from cadrumo-agent hosting v1."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .providers.domain.catalog import ProviderId


class HostedCertificationStatus(BaseModel):
    """One bounded certification fact copied from a live hosted lane."""

    model_config = ConfigDict(extra="ignore", strict=True, frozen=True, hide_input_in_errors=True)

    provider: ProviderId = Field(validation_alias="provider_id")
    transport: Literal["api", "cli"]
    execution_mode: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    status: Literal["unknown", "pending", "proven"] = Field(default="unknown", validation_alias="hosted_certification")


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
