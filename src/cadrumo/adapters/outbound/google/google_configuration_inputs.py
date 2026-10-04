"""Canonical human Google configuration input decoding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ....core.hashing import sha256_hex
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import GoogleAuthValidationError
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


__all__ = ["decode_google_client_json"]
