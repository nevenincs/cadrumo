from __future__ import annotations

from typing import TYPE_CHECKING

from ..._browser import BrowserSessionLike
from ..._models import AeatLoginAssertion, AeatSession, AuthProviderKind
from ..._protocols import AuthProviderDescription
from .certificate import (
    CertificateBundle,
)

if TYPE_CHECKING:
    from ....config import Settings


class CertificateAuthProvider:
    """Authentication provider for PKCS#12 certificates."""

    @property
    def kind(self) -> AuthProviderKind:
        return AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            name="Certificate",
            kind=self.kind,
            is_configured=True,
        )

    def _require_bundle(self, settings: Settings) -> CertificateBundle:
        path = settings.aeat_certificate_path
        if path is None:
            raise ValueError("AEAT_CERTIFICATE_PATH is not set; cannot build CertificateBundle")
        return CertificateBundle(
            path=path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106
            friendly_name=settings.aeat_certificate_friendly_name,
            backend=settings.aeat_certificate_backend,
        )

    async def authenticate(
        self,
        browser_session: BrowserSessionLike,
        settings: Settings,
    ) -> AeatSession:
        # Note: This is a placeholder for the protocol if AeatAuthenticator delegates to it entirely.
        # But actually, since tests expect AeatAuthenticator to remain identical, we will refactor
        # AeatAuthenticator to use this provider or we will move logic here.
        raise NotImplementedError("Delegated to AeatAuthenticator for now")

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        raise NotImplementedError()
