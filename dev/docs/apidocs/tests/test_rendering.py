"""Tests for API annotation rendering in Sphinx."""

from __future__ import annotations

import pytest

from ..rendering import format_type_hint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_regex_metadata_is_rendered_as_source_literal() -> None:
    annotation = "Annotated[str, Field(min_length=32, pattern=r'^[A-Za-z0-9_-]+$')]"

    assert format_type_hint(annotation) == f"``{annotation}``"


def test_external_api_types_link_to_their_defining_documentation() -> None:
    assert format_type_hint("AllowInfNan") == (
        "`AllowInfNan <https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan>`_"
    )
    assert format_type_hint("mcp.server.lowlevel.server.Server") == (
        "`Server <https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/>`_"
    )


def test_unaffected_annotations_use_the_default_formatter() -> None:
    assert format_type_hint("str") is None
    assert format_type_hint("Annotated[str, Field(min_length=1)]") is None
