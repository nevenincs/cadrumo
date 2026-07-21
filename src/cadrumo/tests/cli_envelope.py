"""Canonical CLI success-envelope decoder for cross-package tests.

The helper validates the shared outer contract through the production
``SchemaEnvelope`` model while allowing each command's registered result fields.
Tests that need a command-specific payload schema continue to validate that schema
separately; this module owns only transport-envelope decoding and unwrapping.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import ConfigDict

from ..core.json_contract import ENVELOPE_SCHEMA_VERSION, OutputSchema, SchemaEnvelope


class _ArbitraryCommandResult(OutputSchema):
    """Strict mapping root whose fields are supplied by a command schema."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        strict=True,
        validate_assignment=True,
    )


class CliResultLike(Protocol):
    """Captured CLI result exposing stdout for envelope decoding."""

    @property
    def output(self) -> str:
        """Return captured standard output."""
        ...


def _decode_document(output: str) -> tuple[dict[str, Any], bool]:
    """Decode JSON and validate it when it declares an envelope version."""
    raw = json.loads(output)
    if not isinstance(raw, dict):
        raise TypeError("CLI JSON output must be an object")
    if "schema_version" not in raw:
        return raw, False

    # Validate the wire bytes in JSON mode. The production contract uses strict
    # enums, whose JSON string representation is intentionally accepted here.
    envelope = SchemaEnvelope[_ArbitraryCommandResult].model_validate_json(output)
    if envelope.schema_version != ENVELOPE_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported CLI envelope schema version "
            f"{envelope.schema_version!r}; expected {ENVELOPE_SCHEMA_VERSION!r}",
        )
    return raw, True


def unwrap_schema_envelope(output: str) -> dict[str, Any]:
    """Return a validated envelope's result or a documented bare mapping."""
    document, is_envelope = _decode_document(output)
    if is_envelope:
        return _result_from_envelope(document)
    return document


def require_schema_envelope(output: str) -> dict[str, Any]:
    """Return a validated result and reject output without an envelope."""
    document, is_envelope = _decode_document(output)
    if not is_envelope:
        raise ValueError("Expected a versioned CLI success envelope")
    return _result_from_envelope(document)


def _result_from_envelope(document: dict[str, Any]) -> dict[str, Any]:
    """Project the validated mapping-shaped result from an envelope."""
    result = document["result"]
    if not isinstance(result, dict):
        raise TypeError("CLI success-envelope result must be an object")
    return result


def unwrap_envelope_notices(output: str) -> list[dict[str, Any]]:
    """Return validated outer-envelope notices, or none for a bare mapping."""
    document, is_envelope = _decode_document(output)
    if not is_envelope:
        return []
    notices = document.get("notices", [])
    if not isinstance(notices, list):  # The model validation above owns this invariant.
        raise TypeError("CLI success-envelope notices must be a list")
    return notices


def unwrap_cli_result(result: CliResultLike) -> dict[str, Any]:
    """Decode and unwrap stdout from a captured real CLI invocation."""
    return require_schema_envelope(result.output)


__all__ = [
    "require_schema_envelope",
    "unwrap_cli_result",
    "unwrap_envelope_notices",
    "unwrap_schema_envelope",
]
