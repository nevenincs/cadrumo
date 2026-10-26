"""Canonical Desktop Google OAuth client and endpoint validation."""

from __future__ import annotations

import json
from typing import Annotated, Any
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, BaseModel, Field, ValidationError, field_validator

from .config_google import CLIENT_METADATA_MAX_BYTES
from .errors.hierarchy import pydantic_validation_boundary
from .models import STRICT_FROZEN_CONFIG


def _google_oauth_endpoint_has_https_hostname(parsed: SplitResult) -> bool:
    """Require the endpoint transport and a hostname before later checks."""
    return parsed.scheme == "https" and parsed.hostname is not None


def _google_oauth_endpoint_has_no_userinfo_or_port(parsed: SplitResult, port: int | None) -> bool:
    """Reject credentials and explicit ports before matching the host."""
    return parsed.username is None and parsed.password is None and port is None


def _google_oauth_endpoint_matches_host(parsed: SplitResult, expected_host: str) -> bool:
    """Compare the normalised parsed hostname with its canonical Google host."""
    hostname = parsed.hostname
    return hostname is not None and hostname.lower() == expected_host


def _google_oauth_endpoint_has_clean_path(parsed: SplitResult) -> bool:
    """Require a path while refusing query and fragment components."""
    if not parsed.path:
        return False
    return not parsed.query and not parsed.fragment


def _validate_google_oauth_endpoint(value: str, *, field_name: str, expected_host: str) -> str:
    """Validate one persisted OAuth endpoint before an upstream library consumes it."""
    endpoint = value.strip()
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} must use a valid canonical Google HTTPS endpoint") from exc
    if (
        not _google_oauth_endpoint_has_https_hostname(parsed)
        or not _google_oauth_endpoint_has_no_userinfo_or_port(parsed, port)
        or not _google_oauth_endpoint_matches_host(parsed, expected_host)
        or not _google_oauth_endpoint_has_clean_path(parsed)
    ):
        raise ValueError(
            f"{field_name} must be an absolute HTTPS endpoint on {expected_host!r} "
            "without userinfo, port, query, or fragment",
        )
    return endpoint


def _validate_token_uri(value: str) -> str:
    return _validate_google_oauth_endpoint(value, field_name="token_uri", expected_host="oauth2.googleapis.com")


OAuthTokenUri = Annotated[str, Field(min_length=1), AfterValidator(_validate_token_uri)]
"""A Google OAuth token endpoint, refused unless it is the canonical HTTPS host."""


class OAuthClient(BaseModel):
    """The publisher's Google OAuth Desktop client metadata.

    Carries the fields of a Desktop client download from the Google Cloud
    Console. It is installation data, the same for every profile, and is
    never persisted as a profile record. Google does not treat an installed
    application's ``client_secret`` as confidential, so the record is not a
    stored secret either; it still never enters command output or logs.
    """

    model_config = STRICT_FROZEN_CONFIG

    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    auth_uri: str = Field(min_length=1)
    token_uri: OAuthTokenUri
    auth_provider_x509_cert_url: str = Field(min_length=1)
    redirect_uris: tuple[str, ...] = Field(default=())

    @field_validator("auth_uri")
    @classmethod
    @pydantic_validation_boundary
    def _validate_auth_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(value, field_name="auth_uri", expected_host="accounts.google.com")

    @field_validator("auth_provider_x509_cert_url")
    @classmethod
    @pydantic_validation_boundary
    def _validate_cert_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(
            value,
            field_name="auth_provider_x509_cert_url",
            expected_host="www.googleapis.com",
        )


class _DesktopClientEnvelope(BaseModel):
    """The ``installed`` wrapper Google puts around a Desktop client download."""

    model_config = STRICT_FROZEN_CONFIG
    # ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING: irreducible Cloud Console JSON,
    # narrowed through the canonical OAuthClient before credential use.
    installed: dict[str, Any]


def decode_desktop_client(encoded: str) -> OAuthClient | None:
    """Validate bounded Desktop JSON without surfacing credential-bearing errors."""
    if len(encoded) > CLIENT_METADATA_MAX_BYTES:
        return None
    try:
        if len(encoded.encode("utf-8")) > CLIENT_METADATA_MAX_BYTES:
            return None
    except UnicodeEncodeError:
        return None
    try:
        envelope = _DesktopClientEnvelope.model_validate(json.loads(encoded))
    except (json.JSONDecodeError, RecursionError, ValidationError):
        return None
    fields = dict(envelope.installed)
    if isinstance(fields.get("redirect_uris"), list):
        fields["redirect_uris"] = tuple(fields["redirect_uris"])
    try:
        return OAuthClient.model_validate(fields)
    except ValidationError:
        return None
