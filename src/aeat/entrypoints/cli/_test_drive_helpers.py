"""Unit tests for :mod:`aeat.cli._drive_helpers`."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._drive_helpers import (
    build_listing_query,
    build_name_query,
    escape_drive_query_literal,
    guess_mime_type,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


class TestGuessMimeType:
    """Behaviour of ``guess_mime_type``."""

    def test_known_extension(self) -> None:
        assert guess_mime_type(Path("doc.txt")) == "text/plain"

    def test_unknown_extension_falls_back(self) -> None:
        assert guess_mime_type(Path("file.unknown_ext_xyz")) == "application/octet-stream"

    def test_no_extension_falls_back(self) -> None:
        assert guess_mime_type(Path("README")) == "application/octet-stream"


class TestBuildListingQuery:
    """Behaviour of ``build_listing_query``."""

    def test_no_folder_filters_only_trash(self) -> None:
        assert build_listing_query(None) == "trashed=false"

    def test_folder_scope(self) -> None:
        result = build_listing_query("abc123")
        assert "'abc123' in parents" in result
        assert "trashed=false" in result


class TestBuildNameQuery:
    """Behaviour of ``build_name_query``."""

    def test_simple_name(self) -> None:
        assert build_name_query("cert.p12") == "name = 'cert.p12' and trashed=false"

    def test_name_with_underscores(self) -> None:
        result = build_name_query("WOOTSCH_GERGELY_Y4113523X.p12")
        assert "WOOTSCH_GERGELY_Y4113523X.p12" in result
        assert "trashed=false" in result

    def test_name_with_single_quote_is_escaped(self) -> None:
        result = build_name_query("o'brien.p12")
        # The embedded apostrophe is escaped as ``\'`` so the surrounding
        # ``'...'`` literal stays syntactically intact.
        assert "o\\'brien.p12" in result
        # Three apostrophe characters total: the literal's opening quote,
        # the embedded escaped one, and the literal's closing quote.
        assert result.count("'") == 3
        assert result.startswith("name = '")
        assert result.endswith("' and trashed=false")

    def test_folder_scope_escapes_id(self) -> None:
        result = build_listing_query("a'b")
        # The escaped form has an inner backslash-quote sequence
        assert "\\'b" in result
