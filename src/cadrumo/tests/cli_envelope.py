"""Canonical CLI envelope decoders for cross-package tests.

The success-side helper validates the shared outer contract through the
production ``SchemaEnvelope`` model while allowing each command's registered
result fields. The error-side helper validates the same outer spine through
the production ``ErrorEnvelope`` model nested under ``error``. Tests that need
a command-specific payload schema continue to validate that schema
separately; this module owns only transport-envelope decoding and unwrapping.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ..core.errors.error_codes import ErrorEnvelope
from ..core.json_contract import ENVELOPE_SCHEMA_VERSION, EnvelopeStatus, Notice, OutputSchema, SchemaEnvelope


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


_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


def parse_json_object(text: str) -> dict[str, object]:
    """Parse ``text`` as a JSON object, typed at the boundary rather than left ``Any``.

    For callers that need a raw top-level JSON object outside the envelope
    contract (a full response body, a non-envelope payload) rather than the
    unwrapped ``result`` mapping the helpers above return.
    """
    return _JSON_OBJECT_ADAPTER.validate_python(json.loads(text))


class _ErrorDocument(BaseModel):
    """Stable outer envelope wrapping a failed command's error body.

    Mirrors :class:`SchemaEnvelope`'s outer spine, but nests the production
    :class:`ErrorEnvelope` under ``error`` instead of a command ``result``. An
    error document carries no ``result`` key, so :class:`SchemaEnvelope`
    structurally cannot validate it — this is that missing counterpart.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str = Field(min_length=1)
    command: str | None
    active_profile: str | None = None
    status: EnvelopeStatus
    error: ErrorEnvelope
    notices: list[Notice] = Field(default_factory=list)


def require_error_document(output: str) -> dict[str, Any]:
    """Return the validated stderr/stdout error document as a plain mapping.

    CLI output mixes prose, Rich panels, and log lines around the single-line
    JSON document; each candidate line is stripped before the ``{`` probe so a
    document indented by a surrounding frame is still found — a bare
    ``line.startswith("{")`` silently misses indented JSON. The full outer
    spine plus the nested ``error`` body is validated through the real
    :class:`_ErrorDocument`/:class:`ErrorEnvelope` models, not a two-key
    presence check.
    """
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith("{"):
            raw = json.loads(candidate)
            if not isinstance(raw, dict):
                raise TypeError("CLI JSON error document must be an object")
            document = _ErrorDocument.model_validate_json(candidate)
            if document.schema_version != ENVELOPE_SCHEMA_VERSION:
                raise ValueError(
                    "Unsupported CLI error envelope schema version "
                    f"{document.schema_version!r}; expected {ENVELOPE_SCHEMA_VERSION!r}",
                )
            return raw
    raise AssertionError(f"no JSON error document found in output:\n{output}")


__all__ = [
    "parse_json_object",
    "require_error_document",
    "require_schema_envelope",
    "unwrap_cli_result",
    "unwrap_envelope_notices",
    "unwrap_schema_envelope",
]
