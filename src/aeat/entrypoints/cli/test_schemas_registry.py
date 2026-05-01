"""Unit tests for the CLI output-schema registry.

Exercises :func:`aeat.entrypoints.cli.register_schema`,
:class:`aeat.entrypoints.cli.SchemaEnvelope`, and
:func:`aeat.entrypoints.cli.emit_json_document`. Verifies that the
registry rejects duplicates and non-:class:`OutputSchema` classes,
that the public re-exports stay stable, and that set-like payloads
are normalised to JSON arrays at emission time.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest
from pydantic import Field, ValidationError

import aeat.entrypoints.cli as cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@contextmanager
def _preserved_registry() -> Iterator[None]:
    """Snapshot and restore the global schema registry around a test body."""

    snapshot = dict(cli.SCHEMA_REGISTRY)
    try:
        cli.SCHEMA_REGISTRY.clear()
        yield
    finally:
        cli.SCHEMA_REGISTRY.clear()
        cli.SCHEMA_REGISTRY.update(snapshot)


class _DemoOutput(cli.OutputSchema):
    """Minimal strict output payload used by the registry tests."""

    value: str = Field(min_length=1)


def test_register_schema_records_strict_schema_class() -> None:
    """The decorator records the schema under the supplied command path."""

    with _preserved_registry():
        registered = cli.register_schema("status today")(_DemoOutput)
        assert registered is _DemoOutput
        assert {"status today": _DemoOutput} == cli.SCHEMA_REGISTRY

        envelope = cli.SchemaEnvelope[_DemoOutput](command="status today", result=_DemoOutput(value="ok"))
        assert envelope.schema_version == "1"
        assert envelope.warnings == []

        with pytest.raises(ValidationError):
            _DemoOutput(value=cast(Any, 123))


def test_register_schema_rejects_duplicate_command_path() -> None:
    """Duplicate registration fails loudly instead of silently overwriting."""

    class _OtherOutput(cli.OutputSchema):
        value: str

    with _preserved_registry():
        cli.register_schema("status today")(_DemoOutput)
        with pytest.raises(cli.OutputSchemaError, match="duplicate schema registration"):
            cli.register_schema("status today")(_OtherOutput)


def test_register_schema_rejects_non_output_schema_classes() -> None:
    """The registry only accepts strict :class:`OutputSchema` subclasses."""

    class _NotOutput:
        value: str

    with _preserved_registry():
        decorator = cast(Any, cli.register_schema("status today"))
        with pytest.raises(cli.OutputSchemaError, match="must inherit from OutputSchema"):
            decorator(_NotOutput)


def test_public_api_reexports_schema_registry_surface() -> None:
    """Callers import the schema surface from :mod:`aeat.entrypoints.cli` only."""

    assert cli.OutputSchema.__name__ == "OutputSchema"
    assert cli.SchemaEnvelope.__name__ == "SchemaEnvelope"
    assert cli.register_schema.__module__ == "aeat.entrypoints.cli._schemas"
    assert cli.SCHEMA_REGISTRY is not None


def test_emit_json_document_normalises_set_payloads_to_json_arrays() -> None:
    """Machine output serialises set and frozenset payloads as JSON arrays."""

    stream = io.StringIO()
    cli.emit_json_document({"items": {"a", "b"}, "frozen": frozenset({"x"})}, stream=stream)
    payload = json.loads(stream.getvalue())
    assert sorted(payload["items"]) == ["a", "b"]
    assert payload["frozen"] == ["x"]
