"""Unit tests for the .env file reader and writer in
:mod:`aeat.core.env_io`.

Locks down the parsing rules (key=value, comment skipping, blank lines,
malformed-line detection) and the in-place rewrite semantics that
preserve comments and ordering when updating individual variables.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..env_io import read_env_file, write_env_var, write_env_vars

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestReadEnvFile:
    """Behaviour of :func:`aeat.core.env_io.read_env_file`."""

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert read_env_file(tmp_path / "missing.env") == {}

    def test_parses_simple_key_value_pairs(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        assert read_env_file(path) == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_blank_lines_and_comments(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text(
            "# header comment\n\nFOO=bar\n# inline comment\nBAZ=qux\n",
            encoding="utf-8",
        )
        assert read_env_file(path) == {"FOO": "bar", "BAZ": "qux"}

    def test_empty_value_yields_empty_string(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("FOO=\n", encoding="utf-8")
        assert read_env_file(path) == {"FOO": ""}

    def test_malformed_line_raises(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("not-a-key-value-line\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed env line"):
            read_env_file(path)


class TestWriteEnvVars:
    """Behaviour of :func:`aeat.core.env_io.write_env_var` and
    :func:`aeat.core.env_io.write_env_vars`.
    """

    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "subdir" / ".env"
        write_env_var(path, "FOO", "bar")
        assert path.read_text(encoding="utf-8") == "FOO=bar\n"

    def test_appends_new_key(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("FOO=bar\n", encoding="utf-8")
        write_env_var(path, "BAZ", "qux")
        assert path.read_text(encoding="utf-8") == "FOO=bar\nBAZ=qux\n"

    def test_rewrites_existing_key_in_place(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("FOO=old\nBAZ=qux\n", encoding="utf-8")
        write_env_var(path, "FOO", "new")
        assert path.read_text(encoding="utf-8") == "FOO=new\nBAZ=qux\n"

    def test_preserves_comments_and_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        original = "# top comment\n\n# section\nFOO=bar\n\nBAZ=qux\n"
        path.write_text(original, encoding="utf-8")
        write_env_var(path, "FOO", "new")
        result = path.read_text(encoding="utf-8")
        assert "# top comment" in result
        assert "# section" in result
        assert "FOO=new" in result
        assert "BAZ=qux" in result
        # blank lines preserved
        assert result.count("\n\n") >= 1

    def test_multi_var_write_appends_in_order(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        write_env_vars(path, {"A": "1", "B": "2", "C": "3"})
        assert path.read_text(encoding="utf-8") == "A=1\nB=2\nC=3\n"

    def test_multi_var_write_mixes_update_and_append(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("EXISTING=old\n", encoding="utf-8")
        write_env_vars(path, {"EXISTING": "new", "FRESH": "value"})
        assert path.read_text(encoding="utf-8") == "EXISTING=new\nFRESH=value\n"
