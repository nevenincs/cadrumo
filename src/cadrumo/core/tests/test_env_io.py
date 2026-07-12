"""Unit tests for the .env file reader and writer in
:mod:`cadrumo.core.env_io`.

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
    """Behaviour of :func:`cadrumo.core.env_io.read_env_file`."""

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert read_env_file(tmp_path / "missing.env") == {}

    def test_parses_supported_env_lines(self, tmp_path: Path) -> None:
        for case_name, text, expected in (
            ("simple-pairs", "FOO=bar\nBAZ=qux\n", {"FOO": "bar", "BAZ": "qux"}),
            (
                "comments-and-blanks",
                "# header comment\n\nFOO=bar\n# inline comment\nBAZ=qux\n",
                {"FOO": "bar", "BAZ": "qux"},
            ),
            ("empty-value", "FOO=\n", {"FOO": ""}),
        ):
            path = tmp_path / f"{case_name}.env"
            path.write_text(text, encoding="utf-8")
            assert read_env_file(path) == expected

    def test_malformed_line_raises(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("not-a-key-value-line\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed env line"):
            read_env_file(path)


class TestWriteEnvVars:
    """Behaviour of :func:`cadrumo.core.env_io.write_env_var` and
    :func:`cadrumo.core.env_io.write_env_vars`.
    """

    def test_write_env_var_materializes_and_updates_file(self, tmp_path: Path) -> None:
        for case_name, path_parts, initial, key, value, expected in (
            ("create-missing", ("subdir", ".env"), None, "FOO", "bar", "FOO=bar\n"),
            ("append-new-key", (".env",), "FOO=bar\n", "BAZ", "qux", "FOO=bar\nBAZ=qux\n"),
            (
                "rewrite-existing-key",
                (".env",),
                "FOO=old\nBAZ=qux\n",
                "FOO",
                "new",
                "FOO=new\nBAZ=qux\n",
            ),
        ):
            path = tmp_path.joinpath(case_name, *path_parts)
            if initial is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(initial, encoding="utf-8")
            write_env_var(path, key, value)
            assert path.read_text(encoding="utf-8") == expected

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

    def test_multi_var_write_materializes_updates_in_order(self, tmp_path: Path) -> None:
        for case_name, initial, updates, expected in (
            ("append-in-order", None, {"A": "1", "B": "2", "C": "3"}, "A=1\nB=2\nC=3\n"),
            (
                "update-and-append",
                "EXISTING=old\n",
                {"EXISTING": "new", "FRESH": "value"},
                "EXISTING=new\nFRESH=value\n",
            ),
        ):
            path = tmp_path / f"{case_name}.env"
            if initial is not None:
                path.write_text(initial, encoding="utf-8")
            write_env_vars(path, updates)
            assert path.read_text(encoding="utf-8") == expected
