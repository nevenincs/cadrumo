from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import Settings
    from ._browser import BrowserContextLike, BrowserSessionLike
    from ._models import AeatLoginAssertion, AeatSession


AEAT_CERTIFICATE_THUMBPRINT_MARKER: Final[str] = "_aeat_certificate_thumbprint"


class AuthProviderKind(StrEnum):
    """Closed catalogue of AEAT auth-provider identifiers."""

    CERTIFICATE = "certificate"
    CLAVE_PERMANENTE = "clave_permanente"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PIN = "clave_pin"


class AuthProviderDescription(BaseModel):
    """Safe, loggable description of one auth provider's current state."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: AuthProviderKind
    label: str = Field(min_length=1)
    configured: bool
    available: bool
    identity_nif: str | None = None
    subject: str | None = None
    expires_on: date | None = None
    health_severity: str | None = None
    days_until_expiry: int | None = None
    health_summary: str | None = None


def describe_provider_operator_impact(description: AuthProviderDescription) -> str:
    """Explain what ``description`` means for Kent's CLI workflow today."""

    if not description.configured:
        return (
            "Kent can still produce, verify, and export filings locally, but "
            "AEAT-backed reads and live submit stay unavailable until an auth "
            "provider is configured."
        )
    if not description.available:
        return (
            f"{description.label} is configured but not ready yet. Kent can still "
            "produce, verify, and export filings locally, but AEAT-backed reads "
            "and live submit stay unavailable until auth is fixed."
        )
    if description.kind == AuthProviderKind.CERTIFICATE:
        return (
            "Certificate auth is ready. Kent keeps the same CLI filing flow for "
            "AEAT-backed reads, live submit remains separately gated, and future "
            "providers can plug into the same commands without changing the workflow."
        )
    return (
        f"{description.label} is ready. Kent keeps the same CLI filing flow while "
        "this provider plugs into the shared auth protocol."
    )


@runtime_checkable
class AuthProvider(Protocol):
    """Provider-agnostic protocol for AEAT authentication."""

    @property
    def kind(self) -> AuthProviderKind: ...

    async def authenticate(
        self,
        browser_session: BrowserSessionLike,
        settings: Settings,
    ) -> tuple[AeatSession, BrowserContextLike]: ...

    async def resume(
        self,
        browser_session: BrowserSessionLike,
        storage_state_path: Path,
        metadata: dict[str, Any],
        settings: Settings,
    ) -> tuple[AeatSession, BrowserContextLike]: ...

    async def verify(
        self,
        context: BrowserContextLike,
        session: AeatSession,
        settings: Settings,
    ) -> AeatLoginAssertion: ...

    def describe(self, settings: Settings) -> AuthProviderDescription: ...


__all__ = [
    "AEAT_CERTIFICATE_THUMBPRINT_MARKER",
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
    "describe_provider_operator_impact",
]
