"""Google Workspace OAuth provider."""

from __future__ import annotations

from ._paths import GoogleAuthPath

__all__ = ["GoogleAuthPath", "get_credentials_for_scopes", "inspect_google_auth"]


def get_credentials_for_scopes(*args, **kwargs):
    raise NotImplementedError


def inspect_google_auth(*args, **kwargs):
    raise NotImplementedError
