"""Application-owned authentication output contracts."""

from __future__ import annotations

from ...core.json_contract import OutputSchema
from .catalogue import AuthProviderListing


class AuthProvidersResult(OutputSchema):
    """The typed result of listing the configured authentication providers."""

    providers: list[AuthProviderListing]


__all__ = ["AuthProvidersResult"]
