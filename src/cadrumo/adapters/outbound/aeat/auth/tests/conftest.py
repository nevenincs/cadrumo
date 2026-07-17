"""Register real authentication-boundary fixtures for adapter tests."""

from ._authenticator_support import _isolated_secure_session_backend, _settings_factory

__all__ = ["_isolated_secure_session_backend", "_settings_factory"]
