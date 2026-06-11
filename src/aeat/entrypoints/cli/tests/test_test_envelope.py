"""Tests for the shared CLI ``--json`` envelope-unwrapping helper."""

from __future__ import annotations

import json

import pytest

from .envelope_helpers import unwrap_schema_envelope

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
    """Pre-migration bare payloads (no ``schema_version``) pass through unchanged."""
    payload = json.dumps({"key": "value"})
    assert unwrap_schema_envelope(payload) == {"key": "value"}


def test_unwrap_passes_through_payload_missing_result_field() -> None:
    """A SchemaEnvelope-shaped payload missing ``result`` is not unwrapped."""
    payload = json.dumps({"schema_version": 1, "command": "x"})
    assert unwrap_schema_envelope(payload) == {"schema_version": 1, "command": "x"}
