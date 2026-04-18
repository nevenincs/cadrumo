from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ._protocols import AuthProviderKind
from ._providers._certificate.certificate import HandshakeResult


class CertificateSessionDetail(BaseModel):
    """Certificate-specific details of an authenticated session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    kind: Literal[AuthProviderKind.CERTIFICATE] = Field(default=AuthProviderKind.CERTIFICATE)
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    handshake: HandshakeResult


ProviderDetail = Annotated[CertificateSessionDetail, Field(discriminator="kind")]


class AeatLoginAssertion(BaseModel):
    """Structured outcome of a single live AEAT verification attempt."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    target_url: str
    is_valid: bool
    handshake_success: bool
    certificate_recognised: bool
    parsed_nif: str | None
    parsed_subject: str | None
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None = None


class AeatSession(BaseModel):
    """Record describing an authenticated live AEAT session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    identity_nif: str = Field(min_length=1)
    provider_detail: ProviderDetail

    @property
    def provider_kind(self) -> AuthProviderKind:
        return self.provider_detail.kind

    def is_stale(self, now: datetime | None = None) -> bool:
        """Return True when the session's idle deadline has elapsed."""
        reference = now if now is not None else datetime.now(UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return reference > self.idle_deadline
