from __future__ import annotations

from typing import TYPE_CHECKING

from ..._authenticator import AeatAuthenticator
from ..._providers import AuthProviderDescription, AuthProviderKind

if TYPE_CHECKING:
    from ....config import Settings
    from ..._authenticator import AeatLoginAssertion, AeatSession, BrowserSessionLike


class CertificateAuthProvider:
    """Authentication provider for PKCS#12 certificates."""

    def __init__(self, settings: Settings) -> None:
        self._delegate = AeatAuthenticator(settings)

    @property
    def kind(self) -> AuthProviderKind:
        return AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return self._delegate.describe()

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        return await self._delegate.authenticate(
            browser_session=browser_session,
            target_url=target_url,
        )

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        return await self._delegate.verify(
            session,
            target_url=target_url,
        )
