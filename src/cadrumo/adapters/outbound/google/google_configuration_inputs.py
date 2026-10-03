"""Canonical human Google configuration input decoding and source selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, ValidationError

from ....core.google_credential_source import GoogleCredentialSourceKind
from ....core.hashing import sha256_hex
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import GoogleAuthError, GoogleAuthValidationError
from .impersonation import GoogleCredentialSourceSelection, GoogleImpersonationConfig
from .records import OAuthClient


class _OAuthClientWrapper(BaseModel):
    """The existing Cloud Console Desktop client envelope."""

    model_config = STRICT_FROZEN_CONFIG
    # ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING: irreducible Cloud Console JSON,
    # narrowed through the canonical OAuthClient before credential use.
    installed: dict[str, Any]


def decode_google_client_json(payload: memoryview, *, source: Path, expected_sha256: str) -> OAuthClient:
    """Decode the one protected source witness using the existing Desktop parser."""
    encoded = bytes(payload)
    if sha256_hex(encoded) != expected_sha256:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_invalid",
            context={"path": str(source), "error_type": "SourceDigestMismatch"},
        )
    try:
        raw = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_unreadable",
            context={"path": str(source), "error_type": type(exc).__name__},
        ) from None
    try:
        raw_payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_invalid",
            context={"path": str(source), "error_type": type(exc).__name__},
        ) from None
    try:
        wrapper = _OAuthClientWrapper.model_validate(raw_payload)
    except ValidationError:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_not_desktop", context={"path": str(source)}
        ) from None
    coerced = dict(wrapper.installed)
    if isinstance(coerced.get("redirect_uris"), list):
        coerced["redirect_uris"] = tuple(coerced["redirect_uris"])
    try:
        return OAuthClient.model_validate(coerced)
    except ValidationError as exc:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_schema_invalid",
            context={"path": str(source), "error_type": type(exc).__name__},
        ) from None


class _ImpersonationKwargs(TypedDict, total=False):
    target_principal: str
    target_scopes: tuple[str, ...]
    delegates: tuple[str, ...]
    subject: str | None
    lifetime_s: int


def google_credential_source_selection(
    *,
    kind: GoogleCredentialSourceKind,
    target_principal: str | None,
    scopes: tuple[str, ...],
    delegates: tuple[str, ...],
    subject: str | None,
    lifetime_seconds: int | None,
) -> GoogleCredentialSourceSelection:
    """Retain the current CLI option validation order and canonical config defaults."""
    if kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION:
        if target_principal is None or not target_principal.strip():
            raise GoogleAuthError(
                "credential-source set --kind service-account-impersonation requires --target-principal",
                translated_message="cli.config.google.credential_source.detail.target_principal_required",
                context={"kind": kind.value},
            )
        kwargs: _ImpersonationKwargs = {"target_principal": target_principal.strip()}
        if scopes:
            kwargs["target_scopes"] = scopes
        if delegates:
            kwargs["delegates"] = delegates
        if subject is not None:
            kwargs["subject"] = subject
        if lifetime_seconds is not None:
            kwargs["lifetime_s"] = lifetime_seconds
        try:
            return GoogleCredentialSourceSelection(kind=kind, impersonation=GoogleImpersonationConfig(**kwargs))
        except ValueError as exc:
            raise GoogleAuthError(
                translated_message="cli.config.google.credential_source.detail.impersonation_config_invalid",
                context={"error_type": type(exc).__name__},
            ) from None
    if any(
        (target_principal is not None, bool(scopes), bool(delegates), subject is not None, lifetime_seconds is not None)
    ):
        raise GoogleAuthError(
            "credential-source set --kind oauth-desktop accepts no impersonation options",
            translated_message="cli.config.google.credential_source.detail.oauth_desktop_rejects_impersonation_options",
            context={"kind": kind.value},
        )
    return GoogleCredentialSourceSelection(kind=kind)


__all__ = ["decode_google_client_json", "google_credential_source_selection"]
