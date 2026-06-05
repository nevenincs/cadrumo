"""Unit tests for :mod:`aeat.tests._env_loader`."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._env_loader import load_env_file, parse_env_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestParseEnvText:
    def test_simple_pair(self) -> None:
        assert parse_env_text("FOO=bar") == {"FOO": "bar"}

    def test_multiple_pairs(self) -> None:
        text = "A=1\nB=2\nC=3\n"
        assert parse_env_text(text) == {"A": "1", "B": "2", "C": "3"}

    def test_blank_lines_and_comments_ignored(self) -> None:
        text = "\n# this is a comment\nFOO=bar\n  # leading-space comment\nBAZ=qux\n"
        assert parse_env_text(text) == {"FOO": "bar", "BAZ": "qux"}

    def test_inline_comment_stripped_from_value(self) -> None:
        # The ``#`` must be preceded by whitespace to count as a comment.
        assert parse_env_text("PORT=8080 # the dev server port") == {"PORT": "8080"}

    def test_hash_inside_value_preserved_when_no_leading_space(self) -> None:
        # ``COLOR=#ffaabb`` is a hex value, not a comment.
        assert parse_env_text("COLOR=#ffaabb") == {"COLOR": "#ffaabb"}

    def test_double_quoted_value_unquoted(self) -> None:
        assert parse_env_text('NAME="Persona Prueba"') == {"NAME": "Persona Prueba"}

    def test_single_quoted_value_unquoted(self) -> None:
        assert parse_env_text("NAME='Persona Prueba'") == {"NAME": "Persona Prueba"}

    def test_quoted_value_preserves_inline_hash(self) -> None:
        # Inside quotes, ``#`` is not a comment marker.
        assert parse_env_text('TOKEN="abc#def"') == {"TOKEN": "abc#def"}

    def test_whitespace_trimmed_around_key_and_value(self) -> None:
        assert parse_env_text("  FOO  =   bar  ") == {"FOO": "bar"}

    def test_line_without_equals_ignored(self) -> None:
        text = "FOO\nBAR=baz\n"
        assert parse_env_text(text) == {"BAR": "baz"}

    def test_blank_key_ignored(self) -> None:
        # ``=value`` produces an empty key.
        assert parse_env_text("=orphan\nA=1") == {"A": "1"}

    def test_later_assignment_wins(self) -> None:
        text = "A=1\nA=2\n"
        assert parse_env_text(text) == {"A": "2"}

    def test_empty_value_is_empty_string(self) -> None:
        assert parse_env_text("FOO=") == {"FOO": ""}


class TestLoadEnvFile:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_env_file(tmp_path / "nope.env") == {}

    def test_real_file_round_trip(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        cert_path = tmp_path / "cert.p12"
        env.write_text(
            f"# header\nAEAT_LIVE_TESTS_ENABLED=1\nAEAT_CERTIFICATE_PATH={cert_path}\n",
            encoding="utf-8",
        )
        loaded = load_env_file(env)
        assert loaded["AEAT_LIVE_TESTS_ENABLED"] == "1"
        assert loaded["AEAT_CERTIFICATE_PATH"] == str(cert_path)
