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

    @pytest.mark.parametrize(
        ("text", "expected"),
        (
            pytest.param("FOO=bar\nBAZ=qux\n", {"FOO": "bar", "BAZ": "qux"}, id="simple-pairs"),
            pytest.param(
                "# header comment\n\nFOO=bar\n# inline comment\nBAZ=qux\n",
                {"FOO": "bar", "BAZ": "qux"},
                id="comments-and-blanks",
            ),
            pytest.param("FOO=\n", {"FOO": ""}, id="empty-value"),
        ),
    )
    def test_parses_supported_env_lines(self, tmp_path: Path, text: str, expected: dict[str, str]) -> None:
        path = tmp_path / ".env"
        path.write_text(text, encoding="utf-8")
        assert read_env_file(path) == expected

    def test_malformed_line_raises(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("not-a-key-value-line\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed env line"):
            read_env_file(path)


class TestWriteEnvVars:
    """Behaviour of :func:`aeat.core.env_io.write_env_var` and
    :func:`aeat.core.env_io.write_env_vars`.
    """

    @pytest.mark.parametrize(
        ("path_parts", "initial", "key", "value", "expected"),
        (
            pytest.param(("subdir", ".env"), None, "FOO", "bar", "FOO=bar\n", id="create-missing"),
            pytest.param((".env",), "FOO=bar\n", "BAZ", "qux", "FOO=bar\nBAZ=qux\n", id="append-new-key"),
            pytest.param(
                (".env",),
                "FOO=old\nBAZ=qux\n",
                "FOO",
                "new",
                "FOO=new\nBAZ=qux\n",
                id="rewrite-existing-key",
            ),
        ),
    )
    def test_write_env_var_materializes_and_updates_file(
        self,
        tmp_path: Path,
        path_parts: tuple[str, ...],
        initial: str | None,
        key: str,
        value: str,
        expected: str,
    ) -> None:
        path = tmp_path.joinpath(*path_parts)
        if initial is not None:
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

    @pytest.mark.parametrize(
        ("initial", "updates", "expected"),
        (
            pytest.param(None, {"A": "1", "B": "2", "C": "3"}, "A=1\nB=2\nC=3\n", id="append-in-order"),
            pytest.param(
                "EXISTING=old\n",
                {"EXISTING": "new", "FRESH": "value"},
                "EXISTING=new\nFRESH=value\n",
                id="update-and-append",
            ),
        ),
    )
    def test_multi_var_write_materializes_updates_in_order(
        self,
        tmp_path: Path,
        initial: str | None,
        updates: dict[str, str],
        expected: str,
    ) -> None:
        path = tmp_path / ".env"
        if initial is not None:
            path.write_text(initial, encoding="utf-8")
        write_env_vars(path, updates)
        assert path.read_text(encoding="utf-8") == expected
