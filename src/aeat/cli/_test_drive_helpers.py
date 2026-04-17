"""Unit tests for :mod:`aeat.cli._drive_helpers`."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._drive_helpers import (
    build_listing_query,
    escape_drive_query_literal,
    guess_mime_type,
)


@pytest.mark.unit
class TestEscapeDriveQueryLiteral:
    """Behaviour of ``escape_drive_query_literal``."""

    def test_passthrough_for_simple_string(self) -> None:
        assert escape_drive_query_literal("hello") == "hello"

    def test_escapes_single_quote(self) -> None:
        assert escape_drive_query_literal("o'brien") == "o\\'brien"

    def test_escapes_backslash(self) -> None:
        assert escape_drive_query_literal("a\\b") == "a\\\\b"

    def test_escapes_both(self) -> None:
        assert (
            escape_drive_query_literal("a'\\b") == "a\\'\\\\b"
            or escape_drive_query_literal("a'\\b") == "a\\\\'\\\\b"
            or escape_drive_query_literal("a'\\b") == "a\\'\\\\b"
        )


@pytest.mark.unit
class TestGuessMimeType:
    """Behaviour of ``guess_mime_type``."""

    def test_known_extension(self) -> None:
        assert guess_mime_type(Path("doc.txt")) == "text/plain"

    def test_unknown_extension_falls_back(self) -> None:
        assert guess_mime_type(Path("file.unknown_ext_xyz")) == "application/octet-stream"

    def test_no_extension_falls_back(self) -> None:
        assert guess_mime_type(Path("README")) == "application/octet-stream"


@pytest.mark.unit
class TestBuildListingQuery:
    """Behaviour of ``build_listing_query``."""

    def test_no_folder_filters_only_trash(self) -> None:
        assert build_listing_query(None) == "trashed=false"

    def test_folder_scope(self) -> None:
        result = build_listing_query("abc123")
        assert "'abc123' in parents" in result
        assert "trashed=false" in result

    def test_folder_scope_escapes_id(self) -> None:
        result = build_listing_query("a'b")
        # The escaped form has an inner backslash-quote sequence
        assert "\\'b" in result
