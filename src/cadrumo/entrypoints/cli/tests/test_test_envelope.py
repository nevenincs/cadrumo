"""Tests for the shared CLI ``--json`` envelope-unwrapping helper."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from .envelope_helpers import require_schema_envelope, unwrap_schema_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_unwrap_returns_result_mapping_when_envelope_present() -> None:
    """SchemaEnvelope payloads yield the inner ``result`` mapping."""
    payload = json.dumps(
        {
            "schema_version": "2",
            "command": "test.cmd",
            "status": "success",
            "result": {"key": "value", "count": 3},
            "notices": [],
        },
    )
    assert unwrap_schema_envelope(payload) == {"key": "value", "count": 3}


def test_unwrap_passes_through_when_envelope_absent() -> None:
    """Documented bare payloads (no ``schema_version``) pass through unchanged."""
    payload = json.dumps({"key": "value"})
    assert unwrap_schema_envelope(payload) == {"key": "value"}


def test_require_rejects_documented_bare_payload() -> None:
    """Known envelope-emitting commands cannot accept a bare result mapping."""
    with pytest.raises(ValueError, match="Expected a versioned CLI success envelope"):
        require_schema_envelope('{"work_unit_id": "bare-result"}')


def test_unwrap_rejects_envelope_missing_result_field() -> None:
    """A versioned document must satisfy the complete SchemaEnvelope shape."""
    payload = json.dumps({"schema_version": 1, "command": "x"})
    with pytest.raises(ValidationError):
        unwrap_schema_envelope(payload)


def test_unwrap_rejects_unsupported_envelope_schema_version() -> None:
    """A structurally valid future envelope is rejected by exact version."""
    payload = json.dumps(
        {
            "schema_version": "999",
            "command": "test.cmd",
            "status": "success",
            "result": {},
            "notices": [],
        },
    )
    with pytest.raises(ValueError, match="Unsupported CLI envelope schema version"):
        unwrap_schema_envelope(payload)


def test_unwrap_rejects_non_mapping_envelope_result() -> None:
    """Success-envelope helpers reject a result with the wrong root type."""
    payload = json.dumps(
        {
            "schema_version": "2",
            "command": "test.cmd",
            "status": "success",
            "result": ["not", "a", "mapping"],
            "notices": [],
        },
    )
    with pytest.raises(ValidationError):
        unwrap_schema_envelope(payload)
