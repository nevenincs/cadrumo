from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ._protocols import AuthProviderKind
from ._providers._certificate.certificate import HandshakeResult

AEAT_SESSION_IDLE_TTL: timedelta = timedelta(minutes=18)


class ProviderDetail(BaseModel):
    """Base for provider-specific session metadata."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class CertificateSessionDetail(ProviderDetail):
    """Metadata specific to a certificate-based session."""

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    handshake: HandshakeResult


class ClavePermanenteSessionDetail(ProviderDetail):
    """Metadata specific to a Cl@ve Permanente session."""

    kind: Literal[AuthProviderKind.CLAVE_PERMANENTE] = AuthProviderKind.CLAVE_PERMANENTE
    dni_nie: str = Field(min_length=1)


class ClaveMovilSessionDetail(ProviderDetail):
    """Metadata specific to a Cl@ve Móvil session."""

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL
    dni_nie: str = Field(min_length=1)
    approved_at: datetime


class ClavePinSessionDetail(ProviderDetail):
    """Metadata specific to a Cl@ve PIN session."""

    kind: Literal[AuthProviderKind.CLAVE_PIN] = AuthProviderKind.CLAVE_PIN
    dni_nie: str = Field(min_length=1)


AeatProviderDetail = Annotated[
    CertificateSessionDetail | ClavePermanenteSessionDetail | ClaveMovilSessionDetail | ClavePinSessionDetail,
    Field(discriminator="kind"),
]


class AeatSession(BaseModel):
    """Snapshot of an AEAT-authenticated browser session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None = None
    provider_detail: AeatProviderDetail

    @property
    def provider_kind(self) -> AuthProviderKind:
        """The kind of provider that produced this session."""
        return self.provider_detail.kind

    def is_stale(self, now: datetime | None = None) -> bool:
        """Return True if the session's idle deadline has elapsed."""
        reference = now if now is not None else datetime.now(UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return reference > self.idle_deadline


class AeatLoginAssertion(BaseModel):
    """Results of a 'live' verification probe of an AEAT session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    target_url: str
    is_valid: bool
    handshake_success: bool
    certificate_recognised: bool
    parsed_nif: str
    parsed_subject: str
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None = None
