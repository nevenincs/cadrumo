"""Unit tests for :mod:`aeat-tests._env_loader`."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._env_loader import load_env_file, parse_env_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestParseEnvText:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("FOO=bar", {"FOO": "bar"}, id="simple-pair"),
            pytest.param("A=1\nB=2\nC=3\n", {"A": "1", "B": "2", "C": "3"}, id="multiple-pairs"),
            pytest.param(
                "\n# this is a comment\nFOO=bar\n  # leading-space comment\nBAZ=qux\n",
                {"FOO": "bar", "BAZ": "qux"},
                id="blank-lines-and-comments",
            ),
            pytest.param("PORT=8080 # the dev server port", {"PORT": "8080"}, id="inline-comment"),
            pytest.param("COLOR=#ffaabb", {"COLOR": "#ffaabb"}, id="hash-without-leading-space"),
            pytest.param('NAME="Persona Prueba"', {"NAME": "Persona Prueba"}, id="double-quoted"),
            pytest.param("NAME='Persona Prueba'", {"NAME": "Persona Prueba"}, id="single-quoted"),
            pytest.param('TOKEN="abc#def"', {"TOKEN": "abc#def"}, id="quoted-hash"),
            pytest.param("  FOO  =   bar  ", {"FOO": "bar"}, id="trimmed-key-value"),
            pytest.param("FOO\nBAR=baz\n", {"BAR": "baz"}, id="line-without-equals"),
            pytest.param("=orphan\nA=1", {"A": "1"}, id="blank-key"),
            pytest.param("A=1\nA=2\n", {"A": "2"}, id="later-assignment-wins"),
            pytest.param("FOO=", {"FOO": ""}, id="empty-value"),
        ],
    )
    def test_parse_env_text_cases(self, text: str, expected: dict[str, str]) -> None:
        assert parse_env_text(text) == expected


class TestLoadEnvFile:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_env_file(tmp_path / "nope.env") == {}

    def test_real_file_round_trip(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        cert_path = tmp_path / "cert.p12"
        env.write_text(
            f"# header\nCADRUMO_LIVE_TESTS_ENABLED=1\nCADRUMO_CERTIFICATE_PATH={cert_path}\n",
            encoding="utf-8",
        )
        loaded = load_env_file(env)
        assert loaded["CADRUMO_LIVE_TESTS_ENABLED"] == "1"
        assert loaded["CADRUMO_CERTIFICATE_PATH"] == str(cert_path)
