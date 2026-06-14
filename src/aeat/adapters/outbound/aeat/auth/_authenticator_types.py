"""Boundary records and protocols for the AEAT authenticator."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field, SecretStr

from .....core import STRICT_FROZEN_CONFIG
from .....core.time._utc import coerce_utc_aware
from ._errors import AeatLoginAssertionError
from ._providers import (
    AuthLoginAssertionDetail,
    AuthProviderKind,
    AuthSessionDetail,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
)
from .certificate import CertificateBackend, CertificateHealth, HandshakeResult

if TYPE_CHECKING:
    from .....core.config import Settings


class AeatLoginAssertion(BaseModel):
    """Structured outcome of a single live AEAT verification attempt."""

    model_config = STRICT_FROZEN_CONFIG

    target_url: str
    is_valid: bool
    provider_kind: AuthProviderKind
    identity_nif: str | None
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None = None
    assertion_detail: AuthLoginAssertionDetail = Field(discriminator="kind")

    @property
    def handshake_success(self) -> bool | None:
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.handshake_success
        return None

    @property
    def certificate_recognised(self) -> bool | None:
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.certificate_recognised
        return None

    @property
    def parsed_nif(self) -> str | None:
        return self.identity_nif

    @property
    def parsed_subject(self) -> str | None:
        if isinstance(self.assertion_detail, CertificateLoginAssertionDetail):
            return self.assertion_detail.parsed_subject
        return None


class AeatSession(BaseModel):
    """Record describing an authenticated live AEAT session without secret material."""

    model_config = STRICT_FROZEN_CONFIG

    provider_kind: AuthProviderKind
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    identity_nif: str = Field(min_length=1)
    provider_detail: AuthSessionDetail = Field(discriminator="kind")

    @property
    def certificate_thumbprint(self) -> str | None:
        if isinstance(self.provider_detail, CertificateSessionDetail):
            return self.provider_detail.certificate_thumbprint
        return None

    @property
    def certificate_subject(self) -> str | None:
        if isinstance(self.provider_detail, CertificateSessionDetail):
            return self.provider_detail.certificate_subject
        return None

    @property
    def handshake(self) -> HandshakeResult | None:
        if isinstance(self.provider_detail, CertificateSessionDetail):
            return self.provider_detail.handshake
        return None

    def is_stale(self, now: datetime | None = None) -> bool:
        reference = coerce_utc_aware(now) if now is not None else datetime.now(UTC)
        return reference > self.idle_deadline


class _PersistedSessionInvalidError(AeatLoginAssertionError):
    """Raised when a persisted AEAT browser session cannot be trusted."""


@runtime_checkable
class BrowserPageLike(Protocol):
    async def goto(
        self,
        url: str,
        *,
        timeout: float | None = None,
    ) -> BrowserResponseLike | None: ...
    async def close(self) -> None: ...


@runtime_checkable
class BrowserResponseLike(Protocol):
    @property
    def status(self) -> int: ...


@runtime_checkable
class BrowserContextLike(Protocol):
    async def new_page(self) -> BrowserPageLike: ...
    async def storage_state(self) -> Mapping[str, object]: ...
    async def close(self) -> None: ...


@runtime_checkable
class BrowserSessionLike(Protocol):
    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContextLike: ...


@runtime_checkable
class CertificateHealthCheck(Protocol):
    def __call__(
        self,
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        backend: CertificateBackend = ...,
        friendly_name: str | None = ...,
        now: datetime | None = ...,
    ) -> CertificateHealth: ...


class BrowserSessionFactory(Protocol):
    async def __call__(self, settings: Settings) -> BrowserSessionLike: ...


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
