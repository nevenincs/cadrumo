"""Unit tests for the Phase 1 CLI output-schema registry."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest
from pydantic import Field, ValidationError

from ... import cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@contextmanager
def _preserved_registry() -> Iterator[None]:
    """Preserve the global schema registry across tests."""

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
    """The decorator should record the schema under the stable command path."""

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
    """Duplicate registration must fail loudly instead of silently overwriting."""

    class _OtherOutput(cli.OutputSchema):
        value: str

    with _preserved_registry():
        cli.register_schema("status today")(_DemoOutput)
        with pytest.raises(cli.OutputSchemaError, match="duplicate schema registration"):
            cli.register_schema("status today")(_OtherOutput)


def test_register_schema_rejects_non_output_schema_classes() -> None:
    """The registry must only accept strict ``OutputSchema`` subclasses."""

    class _NotOutput:
        value: str

    with _preserved_registry():
        decorator = cast(Any, cli.register_schema("status today"))
        with pytest.raises(cli.OutputSchemaError, match="must inherit from OutputSchema"):
            decorator(_NotOutput)


def test_public_api_reexports_schema_registry_surface() -> None:
    """Callers must import the schema surface from ``aeat.cli`` only."""

    assert cli.OutputSchema.__name__ == "OutputSchema"
    assert cli.SchemaEnvelope.__name__ == "SchemaEnvelope"
    assert cli.register_schema.__module__ == "aeat.entrypoints.cli._schemas"
    assert cli.SCHEMA_REGISTRY is not None


def test_emit_json_document_normalises_set_payloads_to_json_arrays() -> None:
    """Machine output should serialise set-like payloads as JSON arrays."""

    stream = io.StringIO()
    cli.emit_json_document({"items": {"a", "b"}, "frozen": frozenset({"x"})}, stream=stream)
    payload = json.loads(stream.getvalue())
    assert sorted(payload["items"]) == ["a", "b"]
    assert payload["frozen"] == ["x"]
