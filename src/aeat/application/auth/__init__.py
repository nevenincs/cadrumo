"""Compatibility exports for AEAT auth contracts.

Canonical contracts now live in :mod:`aeat.domain.auth`.
"""

from ...domain.auth import *  # noqa: F403
from ...domain.auth import AuthProvider, AuthProviderKind


def select_provider(
    kind: AuthProviderKind,
    *,
    settings,
    browser_session_factory=None,
) -> AuthProvider:
    if kind is AuthProviderKind.CERTIFICATE:
        from ...adapters.outbound.aeat.auth._authenticator import AeatAuthenticator

        return AeatAuthenticator(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_MOVIL:
        from ...adapters.outbound.aeat.auth._clave_movil import ClaveMovilAuthProvider

        return ClaveMovilAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_PERMANENTE:
        raise NotImplementedError(
            "auth provider 'clave_permanente' is not offered by AEAT Sede Electrónica today; "
            "use clave_movil (push approval via the Cl@ve app) or certificate."
        )
    raise NotImplementedError(f"auth provider {kind.value!r} is not implemented yet")
