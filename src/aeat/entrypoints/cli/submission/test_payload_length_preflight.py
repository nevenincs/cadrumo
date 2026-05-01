"""Test the ``verify`` / ``diff`` pre-flight on payload-length mismatch.

Catches the common operator mistakes — passing the wrong
``--modelo`` / ``--ejercicio`` flags, feeding a truncated file —
with a CLI-sculpted error message naming the likely causes, before
the deserialiser surfaces a generic :class:`ValueError` from deep
in the parser. The error reports expected and actual byte counts so
the operator can see at a glance which flag set is wrong.

See also:
    :mod:`aeat.entrypoints.cli.submission.verify` and
    :mod:`aeat.entrypoints.cli.submission.diff` for the commands
    under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


def _unwrap_error(output: str) -> dict[str, Any]:
    """Extract the ``error`` payload from a JSON-mode CLI failure."""
    return cast(dict[str, Any], json.loads(output)["error"])


class TestVerifyPreflightLength:
    """Length pre-flight in ``aeat submission verify``."""

    def test_short_file_shows_kent_facing_message(self, tmp_path: Path) -> None:
        short = tmp_path / "short.130"
        short.write_bytes(b"SHORT")
        result = _runner.invoke(app, ["verify", str(short), "--modelo", "130", "--ejercicio", "2024"])
        assert result.exit_code == 2
        # Normalise whitespace: rich wraps the message at the test runner's
        # terminal width so phrases can span line-breaks.
        flat = " ".join(result.stdout.split())
        assert "expects exactly" in flat.lower()
        assert "130" in flat and "2024" in flat
        assert "wrong" in flat.lower() or "truncated" in flat.lower()

    def test_short_file_json_carries_length_fields(self, tmp_path: Path) -> None:
        short = tmp_path / "short.130"
        short.write_bytes(b"SHORT")
        result = _runner.invoke(app, ["verify", str(short), "--modelo", "130", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = _unwrap_error(result.stderr)
        assert doc["category"] == "REFUSED"
        context = cast(dict[str, Any], doc["context"])
        assert context["expected_bytes"] == "878"
        assert context["actual_bytes"] == "5"

    def test_wrong_modelo_flag_surfaces_mismatch(self, tmp_path: Path) -> None:
        """Mismatching modelo must surface a length error, not a deep crash.

        A real 130 file fed to ``verify --modelo 303 --ejercicio 2024``
        must produce a length-mismatch error naming the 303 expected
        length, not a deserialiser stack trace.
        """
        # Write an 880-byte payload representing a valid 130 file.
        payload = tmp_path / "synthetic130.303"
        payload.write_bytes(b"X" * 878 + b"\r\n")
        result = _runner.invoke(app, ["verify", str(payload), "--modelo", "303", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = _unwrap_error(result.stderr)
        context = cast(dict[str, Any], doc["context"])
        assert context["expected_bytes"] == "7994"
        assert context["actual_bytes"] == "878"


class TestDiffPreflightLength:
    """Length pre-flight in ``aeat submission diff``."""

    def test_short_file_a_shows_kent_facing_message(self, tmp_path: Path) -> None:
        short_a = tmp_path / "short_a.130"
        healthy_b = tmp_path / "healthy_b.130"
        short_a.write_bytes(b"SHORT")
        healthy_b.write_bytes(b"X" * 878 + b"\r\n")
        result = _runner.invoke(app, ["diff", str(short_a), str(healthy_b), "--modelo", "130", "--ejercicio", "2024"])
        assert result.exit_code == 2
        flat = " ".join(result.stdout.split()).lower()
        assert "file_a" in flat or "short_a" in flat
        assert "expects exactly" in flat

    def test_short_file_b_shows_which_file_failed(self, tmp_path: Path) -> None:
        healthy_a = tmp_path / "healthy_a.130"
        short_b = tmp_path / "short_b.130"
        healthy_a.write_bytes(b"X" * 878 + b"\r\n")
        short_b.write_bytes(b"TINY")
        result = _runner.invoke(
            app,
            [
                "diff",
                str(healthy_a),
                str(short_b),
                "--modelo",
                "130",
                "--ejercicio",
                "2024",
                "--json",
            ],
        )
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = _unwrap_error(result.stderr)
        context = cast(dict[str, Any], doc["context"])
        assert context["which_file"] == "file_b"
