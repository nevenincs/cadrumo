"""Smoke tests for the public outbound-auth defining modules."""

import importlib
import inspect

import pytest

from ......core.errors.hierarchy import AuthError
from ..authenticator import AeatAuthenticator
from ..clave_movil import ClaveMovilAuthProvider
from ..provider_selection import select_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_auth_package_initializer_is_inert() -> None:
    """The package root must not expose a compatibility facade."""
    package = importlib.import_module("cadrumo.adapters.outbound.aeat.auth")
    assert package.__all__ == []


def test_smoke_auth_key_symbols_are_importable() -> None:
    """Key concrete symbols are importable from their defining modules."""
    assert inspect.isclass(AeatAuthenticator)
    assert inspect.isclass(ClaveMovilAuthProvider)
    assert inspect.isclass(AuthError)
    assert issubclass(AuthError, Exception)
    assert callable(select_provider)
