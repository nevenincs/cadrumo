"""Google Workspace OAuth provider status surface.

The Google adapter is intentionally separated from AEAT authentication.
This module currently exposes only path metadata and a fail-closed
inspection/result contract; it does not fabricate credentials.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import NoReturn

from ....core.errors import AeatError
from ._paths import GoogleAuthPath


class GoogleAuthUnavailableError(AeatError):
    """Raised when Google credentials are requested without a configured backend."""


class GoogleAuthValidationError(GoogleAuthUnavailableError, ValueError):
    """Raised when Google auth parameters (e.g. scopes) fail validation."""


@dataclass(frozen=True)
class GoogleAuthInspection:
    """Current Google auth backend status."""

    supported_paths: tuple[GoogleAuthPath, ...]
    configured: bool
    detail: str


def inspect_google_auth() -> GoogleAuthInspection:
    """Return the concrete Google auth status without touching credential storage."""

    return GoogleAuthInspection(
        supported_paths=tuple(GoogleAuthPath),
        configured=False,
        detail="No Google credential backend is configured in this build.",
    )


def get_credentials_for_scopes(scopes: Iterable[str], *, path: GoogleAuthPath | None = None) -> NoReturn:
    """Fail closed instead of returning credentials without a backend."""

    normalized = tuple(scope.strip() for scope in scopes if scope.strip())
    if not normalized:
        raise GoogleAuthValidationError("at least one Google OAuth scope is required")
    requested_path = path.value if path is not None else "default"
    raise GoogleAuthUnavailableError(
        f"Google credential acquisition is not configured; requested_path={requested_path!r} scopes={normalized!r}"
    )


__all__ = [
    "GoogleAuthInspection",
    "GoogleAuthPath",
    "GoogleAuthUnavailableError",
    "get_credentials_for_scopes",
    "inspect_google_auth",
]
