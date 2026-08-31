"""Provider-neutral records for authenticated AEAT sessions and probes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...core.auth_provider import AuthProviderKind
from ...core.config import AEAT_CERTIFICATE_PROTECTED_URL, assert_canonical_protected_resource
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now as clock_now
from ...core.time.utc import coerce_utc_aware


class CertificateSessionDetail(BaseModel):
    """Certificate identity and protected-resource proof for one session."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    protected_resource_url: str = AEAT_CERTIFICATE_PROTECTED_URL

    @field_validator("protected_resource_url")
    @classmethod
    def _protected_resource_is_canonical(cls, value: str) -> str:
        return assert_canonical_protected_resource(value, subject="certificate session proof")


class _ClaveSessionDetailBase[ProviderKindT: AuthProviderKind](BaseModel):
    """Identity and landing facts common to Cl@ve-backed sessions."""

    model_config = STRICT_FROZEN_CONFIG

    kind: ProviderKindT
    dni_nie: str = Field(
        min_length=1,
        description="DNI/NIE used for the Cl@ve login (authoritative identity).",
    )
    landing_url: str | None = Field(
        default=None,
        description=(
            "Concrete authenticated AEAT URL observed after login. "
            "Used by live verification and resume probes so the provider "
            "does not re-enter the auth selector when a session is already live."
        ),
    )


class ClaveMovilSessionDetail(_ClaveSessionDetailBase[Literal[AuthProviderKind.CLAVE_MOVIL]]):
    """Session facts unique to a Cl@ve Móvil authentication."""

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL
    used_non_qr_fallback: bool = Field(
        default=False,
        description="True when the DNI/NIE + contraste fallback form was used rather than the QR code.",
    )
    verification_code: str | None = Field(
        default=None,
        description=(
            "Three-letter confirmation code shown on the AEAT QR page at "
            "login; recorded for audit only. Not reused on resume."
        ),
    )


class ClavePermanenteSessionDetail(_ClaveSessionDetailBase[Literal[AuthProviderKind.CLAVE_PERMANENTE]]):
    """Session facts unique to a Cl@ve Permanente authentication."""

    kind: Literal[AuthProviderKind.CLAVE_PERMANENTE] = AuthProviderKind.CLAVE_PERMANENTE


class CertificateLoginAssertionDetail(BaseModel):
    """Observed certificate proof for a protected-resource probe."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[AuthProviderKind.CERTIFICATE] = AuthProviderKind.CERTIFICATE
    final_url: str | None = None
    response_successful: bool
    parsed_subject: str | None = None


class _ClaveLoginAssertionDetailBase[ProviderKindT: AuthProviderKind](BaseModel):
    """Probe facts common to Cl@ve-backed login assertions."""

    model_config = STRICT_FROZEN_CONFIG

    kind: ProviderKindT
    session_cookie_present: bool = Field(
        default=False,
        description=(
            "True when the probe response carried an AEAT session cookie; "
            "primary signal that the Cl@ve login is still live."
        ),
    )
    landing_url: str | None = Field(
        default=None,
        description="Final URL Playwright landed on after following redirects.",
    )


class ClaveMovilLoginAssertionDetail(
    _ClaveLoginAssertionDetailBase[Literal[AuthProviderKind.CLAVE_MOVIL]],
):
    """Probe facts for a Cl@ve Móvil session."""

    kind: Literal[AuthProviderKind.CLAVE_MOVIL] = AuthProviderKind.CLAVE_MOVIL


class ClavePermanenteLoginAssertionDetail(
    _ClaveLoginAssertionDetailBase[Literal[AuthProviderKind.CLAVE_PERMANENTE]],
):
    """Probe facts for a Cl@ve Permanente session."""

    kind: Literal[AuthProviderKind.CLAVE_PERMANENTE] = AuthProviderKind.CLAVE_PERMANENTE


type AuthSessionDetail = CertificateSessionDetail | ClaveMovilSessionDetail | ClavePermanenteSessionDetail
type AuthLoginAssertionDetail = (
    CertificateLoginAssertionDetail | ClaveMovilLoginAssertionDetail | ClavePermanenteLoginAssertionDetail
)


class AeatLoginAssertion(BaseModel):
    """Structured outcome of one live AEAT verification attempt."""

    model_config = STRICT_FROZEN_CONFIG

    target_url: str
    is_valid: bool
    identity_nif: str | None
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None = None
    assertion_detail: AuthLoginAssertionDetail = Field(discriminator="kind")

    @property
    def provider_kind(self) -> AuthProviderKind:
        """Return the provider kind declared by the assertion detail."""
        return self.assertion_detail.kind

    @property
    def response_successful(self) -> bool | None:
        """Return the certificate protected-resource response signal."""
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.response_successful
        return None

    @property
    def final_url(self) -> str | None:
        """Return the final protected-resource URL for certificate assertions."""
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.final_url
        return None

    @property
    def parsed_nif(self) -> str | None:
        """Return the identity observed by the verification probe."""
        return self.identity_nif

    @property
    def parsed_subject(self) -> str | None:
        """Return the certificate subject when certificate auth produced the assertion."""
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.parsed_subject
        return None


class AeatSession(BaseModel):
    """Authenticated live AEAT session record without secret material."""

    model_config = STRICT_FROZEN_CONFIG

    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    identity_nif: str = Field(min_length=1)
    provider_detail: AuthSessionDetail = Field(discriminator="kind")

    @property
    def provider_kind(self) -> AuthProviderKind:
        """Return the provider kind declared by the session detail."""
        return self.provider_detail.kind

    @property
    def certificate_thumbprint(self) -> str | None:
        """Return the certificate thumbprint for certificate-backed sessions."""
        if isinstance(self.provider_detail, CertificateSessionDetail):
            return self.provider_detail.certificate_thumbprint
        return None

    @property
    def certificate_subject(self) -> str | None:
        """Return the certificate subject for certificate-backed sessions."""
        if isinstance(self.provider_detail, CertificateSessionDetail):
            return self.provider_detail.certificate_subject
        return None

    def is_stale(self, now: datetime | None = None) -> bool:
        """Return whether the idle deadline has elapsed at ``now``."""
        reference = coerce_utc_aware(now) if now is not None else clock_now()
        return reference > self.idle_deadline


def is_exact_active_provider_session(
    session: AeatSession,
    active_session: AeatSession | None,
    *,
    provider_kind: AuthProviderKind,
    detail_type: type[BaseModel],
) -> bool:
    """Return whether ``session`` is the provider's exact retained session."""
    return (
        active_session is not None
        and session is active_session
        and active_session.provider_kind is provider_kind
        and isinstance(active_session.provider_detail, detail_type)
    )


__all__ = [
    "AeatLoginAssertion",
    "AeatSession",
    "AuthLoginAssertionDetail",
    "AuthSessionDetail",
    "CertificateLoginAssertionDetail",
    "CertificateSessionDetail",
    "ClaveMovilLoginAssertionDetail",
    "ClaveMovilSessionDetail",
    "ClavePermanenteLoginAssertionDetail",
    "ClavePermanenteSessionDetail",
    "is_exact_active_provider_session",
]
