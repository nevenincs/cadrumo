"""Smoke tests for the auth subpackage."""

import pytest

from .. import (
    AeatAuthenticator,
    AuthError,
    ClaveMovilAuthProvider,
    select_provider,
)
from .. import __all__ as auth_all

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REQUIRED_SYMBOLS = [
    "AeatAuthenticator",
    "AeatSession",
    "AeatLoginAssertionError",
    "AeatSessionExpiredError",
    "AuthError",
    "AuthConfigurationError",
    "ClaveMovilAuthProvider",
    "ClaveMovilApprovalTimeoutError",
    "ClaveMovilConfigurationError",
    "select_provider",
    "LoadedCertificate",
    "load_certificate",
    "verify_handshake",
    "health",
]


def test_smoke_auth_public_surface_is_complete() -> None:
    """Every required public symbol is exported in __all__ and importable."""
    missing = [sym for sym in _REQUIRED_SYMBOLS if sym not in auth_all]
    assert not missing, f"auth __all__ is missing symbols: {missing}"


def test_smoke_auth_key_symbols_are_importable() -> None:
    """Key concrete symbols are importable and have the expected types."""
    import inspect

    assert inspect.isclass(AeatAuthenticator), "AeatAuthenticator must be a class"
    assert inspect.isclass(ClaveMovilAuthProvider), "ClaveMovilAuthProvider must be a class"
    assert inspect.isclass(AuthError), "AuthError must be a class"
    assert issubclass(AuthError, Exception), "AuthError must inherit from Exception"
    assert callable(select_provider), "select_provider must be callable"
