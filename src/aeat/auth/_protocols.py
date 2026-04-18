from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ..config import Settings
    from ._browser import BrowserSessionLike
    from ._models import AeatLoginAssertion, AeatSession


class AuthProviderKind(StrEnum):
    CERTIFICATE = "CERTIFICATE"
    CLAVE_PERMANENTE = "CLAVE_PERMANENTE"
    CLAVE_MOVIL = "CLAVE_MOVIL"
    CLAVE_PIN = "CLAVE_PIN"


class AuthProviderDescription(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    name: str
    kind: AuthProviderKind
    is_configured: bool
    health_status: str | None = None


@runtime_checkable
class AuthProvider(Protocol):
    """Provider-agnostic protocol for obtaining an AEAT-authenticated session."""

    @property
    def kind(self) -> AuthProviderKind:
        """The kind of provider."""
        ...

    async def authenticate(
        self,
        browser_session: BrowserSessionLike,
        settings: Settings,
    ) -> AeatSession:
        """Produce an authenticated context + session record."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Name, kind, current configuration state, health."""
        ...

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        """Re-probe that the session is still valid for this provider."""
        ...
