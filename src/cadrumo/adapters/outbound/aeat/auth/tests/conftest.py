"""Register real authentication-boundary fixtures for adapter tests."""

from .authenticator_support import isolated_secure_session_backend, settings_factory

__all__ = ["isolated_secure_session_backend", "settings_factory"]
