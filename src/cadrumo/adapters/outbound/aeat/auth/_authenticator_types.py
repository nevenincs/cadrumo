"""Boundary records and browser protocols for live AEAT authentication.

The concrete auth providers return :class:`AeatSession` when AEAT access is
available and :class:`AeatLoginAssertion` when that access is probed. Both
records are strict, frozen, and secret-free; provider-specific details live in
the discriminated unions of :class:`CertificateSessionDetail`,
:class:`~adapters.outbound.aeat.auth.ClaveMovilSessionDetail`,
:class:`CertificateLoginAssertionDetail`, and
:class:`~adapters.outbound.aeat.auth.ClaveMovilLoginAssertionDetail`
owned by :mod:`adapters.outbound.aeat.auth._providers`.

The browser protocols mirror the subset of
:class:`adapters.outbound.aeat.browser.BrowserSession` that auth providers
need, so tests and adapter callers can satisfy the same structural contract
without importing Playwright directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field, SecretStr

from .....core import STRICT_FROZEN_CONFIG, AuthProviderKind
from .....core.time import coerce_utc_aware
from ._errors import AeatLoginAssertionError
from ._providers import (
    AuthLoginAssertionDetail,
    AuthSessionDetail,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from .certificate import CertificateHealth

if TYPE_CHECKING:
    from .....core.config import Settings


class AeatLoginAssertion(BaseModel):
    """Structured outcome of a single live AEAT verification attempt.

    Certificate and Cl@ve providers use the same envelope while storing their
    provider-specific signals in :class:`CertificateLoginAssertionDetail` or
    :class:`~adapters.outbound.aeat.auth.ClaveMovilLoginAssertionDetail`.
    Negative probes are returned as records with ``is_valid=False`` so callers
    can decide whether to reauthenticate, surface a diagnostic, or stop.
    """

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
        """Return the protected-resource response signal for certificate auth."""
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
        """Return the identity NIF/NIE observed by the verification probe."""
        return self.identity_nif

    @property
    def parsed_subject(self) -> str | None:
        """Return the certificate subject when this assertion came from certificate auth."""
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.parsed_subject
        return None


class AeatSession(BaseModel):
    """Authenticated live AEAT session record without secret material.

    ``storage_state_path`` is the logical persisted-session key used by
    downstream Sede readers to reopen encrypted browser state. ``provider_detail``
    carries either :class:`CertificateSessionDetail` or
    :class:`~adapters.outbound.aeat.auth.ClaveMovilSessionDetail`:
    certificate sessions expose thumbprint/subject/protected-resource data, while Cl@ve
    sessions expose DNI/NIE and landing metadata.
    """

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
        """Return whether ``idle_deadline`` has elapsed at ``now``."""
        reference = coerce_utc_aware(now) if now is not None else datetime.now(UTC)
        return reference > self.idle_deadline


class _PersistedSessionInvalidError(AeatLoginAssertionError):
    """Raised when a persisted AEAT browser session cannot be trusted."""


@runtime_checkable
class BrowserPageLike(Protocol):
    """Minimal Playwright page surface consumed by auth verification flows."""

    @property
    def url(self) -> str:
        """Final page URL after navigation and redirects."""
        ...

    async def goto(
        self,
        url: str,
        *,
        timeout: float | None = None,
    ) -> BrowserResponseLike | None:
        """Navigate to ``url`` and return the observed :class:`BrowserResponseLike`, if any."""
        ...

    async def close(self) -> None:
        """Close the page after the auth probe completes."""
        ...


@runtime_checkable
class BrowserResponseLike(Protocol):
    """Minimal response surface needed to classify an AEAT probe."""

    @property
    def ok(self) -> bool:
        """Whether Playwright classifies the response as successful."""
        ...

    @property
    def status(self) -> int:
        """HTTP status observed by the verification navigation."""
        ...


@runtime_checkable
class BrowserContextLike(Protocol):
    """Minimal Playwright context surface used by auth providers."""

    async def new_page(self) -> BrowserPageLike:
        """Create a :class:`BrowserPageLike` for a live verification or selector flow."""
        ...

    async def storage_state(self) -> Mapping[str, object]:
        """Return Playwright storage state for encrypted session persistence."""
        ...

    async def close(self) -> None:
        """Close the context during provider teardown."""
        ...


@runtime_checkable
class BrowserSessionLike(Protocol):
    """Browser-session factory surface used by certificate and Cl@ve auth.

    The signature mirrors
    :meth:`adapters.outbound.aeat.browser.BrowserSession.create_context`:
    certificate auth may pass a context provisioner, while resume paths pass
    either a storage-state path or an in-memory storage-state mapping.

    Every implementation owns a browser lifecycle and therefore provides
    deterministic asynchronous closure.
    """

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContextLike:
        """Create a :class:`BrowserContextLike` with optional auth provider state."""
        ...

    async def close(self) -> None:
        """Close the owned browser process. Must be safe to call repeatedly."""
        ...


@runtime_checkable
class CertificateHealthCheck(Protocol):
    """Callable shape used to evaluate a loaded certificate's health."""

    def __call__(
        self,
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        friendly_name: str | None = ...,
        now: datetime | None = ...,
    ) -> CertificateHealth:
        """Return :class:`CertificateHealth` for the supplied PKCS#12 bundle."""
        ...


class BrowserSessionFactory(Protocol):
    """Async factory for objects satisfying :class:`BrowserSessionLike`."""

    async def __call__(self, settings: Settings) -> BrowserSessionLike:
        """Create a browser session configured from ``settings``."""
        ...


__all__ = [
    "AeatLoginAssertion",
    "AeatSession",
    "BrowserContextLike",
    "BrowserPageLike",
    "BrowserResponseLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
    "CertificateHealthCheck",
    "_PersistedSessionInvalidError",
]
