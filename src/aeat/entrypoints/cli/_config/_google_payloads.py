"""Typed ``--json`` payload schemas for google config CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every google-config command surface this module covers.

Field sets match the production payload dicts constructed in ``_google.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


@register_schema("config.google.register")
class GoogleRegisterResult(OutputSchema):
    """JSON envelope for ``aeat config google register``."""

    operation: str = "config.google.register"
    profile: str
    client_id: str
    project_id: str


@register_schema("config.google.login")
class GoogleLoginResult(OutputSchema):
    """JSON envelope for ``aeat config google login``."""

    operation: str = "config.google.login"
    profile: str
    mode: str
    account_email: str
    granted_scopes: list[str] = []


@register_schema("config.google.status")
class GoogleStatusResult(OutputSchema):
    """JSON envelope for ``aeat config google status``."""

    operation: str = "config.google.status"
    profile: str
    client_registered: bool
    client_id: str | None = None
    session_present: bool
    account_email: str | None = None
    granted_scopes: list[str] = []
    issued_at: str | None = None
    last_refresh_at: str | None = None
    reauth_required: bool | None = None


@register_schema("config.google.logout")
class GoogleLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config google logout``."""

    operation: str = "config.google.logout"
    profile: str
    token_removed: bool
    metadata_removed: bool
    client_preserved: bool
