"""Google auth path identifiers."""

from __future__ import annotations

from enum import StrEnum


class GoogleAuthPath(StrEnum):
    DESKTOP_OAUTH_LOCAL_DEV = "desktop-oauth-local-dev"
    SERVICE_ACCOUNT_AUTOMATION = "service-account-automation"
