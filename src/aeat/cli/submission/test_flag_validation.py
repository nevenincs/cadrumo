"""Flag-level validation for --modelo and --ejercicio (wave 136).

Typer callback validators on verify/diff reject obviously-malformed
flag values BEFORE the registry lookup surfaces a generic
UNSUPPORTED error. The ``--modelo`` flag must be a 3-digit numeric
string; ``--ejercicio`` must be a 4-digit year.

Kent-observable benefit: pasting a short-year form (``--ejercicio
24``) or a letter-containing modelo (``--modelo 130a``) produces
an actionable ``Error: Invalid value for '--modelo': ...`` rather
than a registry lookup error listing the 4 valid pairs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app
from ._schema_registry import validate_ejercicio_flag, validate_modelo_flag

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()


class TestValidatorHelpers:
    def test_none_passes_through_modelo(self) -> None:
        assert validate_modelo_flag(None) is None

    def test_none_passes_through_ejercicio(self) -> None:
        assert validate_ejercicio_flag(None) is None

    @pytest.mark.parametrize("good", ["130", "303", "390", "100", "000"])
    def test_good_modelo_strings(self, good: str) -> None:
        assert validate_modelo_flag(good) == good

    @pytest.mark.parametrize("bad", ["abc", "13", "1304", "130a", ""])
    def test_bad_modelo_strings_raise(self, bad: str) -> None:
        import typer

        with pytest.raises(typer.BadParameter):
            validate_modelo_flag(bad)

    @pytest.mark.parametrize("good", ["2024", "2025", "1999", "2099"])
    def test_good_ejercicio_strings(self, good: str) -> None:
        assert validate_ejercicio_flag(good) == good

    @pytest.mark.parametrize("bad", ["24", "20244", "20x4", "abcd", ""])
    def test_bad_ejercicio_strings_raise(self, bad: str) -> None:
        import typer

        with pytest.raises(typer.BadParameter):
            validate_ejercicio_flag(bad)


class TestVerifyRejectsBadFlags:
    def test_non_numeric_modelo_is_rejected(self, tmp_path: Path) -> None:
        stub = tmp_path / "stub.bin"
        stub.write_bytes(b" ")
        result = _runner.invoke(app, ["verify", str(stub), "--modelo", "ABC", "--ejercicio", "2024"])
        assert result.exit_code != 0
        # typer surfaces the BadParameter message in stderr/stdout mix.
        combined = " ".join((result.stdout + (result.stderr or "")).split()).lower()
        assert "3-digit" in combined or "numeric" in combined

    def test_short_year_ejercicio_is_rejected(self, tmp_path: Path) -> None:
        stub = tmp_path / "stub.bin"
        stub.write_bytes(b" ")
        result = _runner.invoke(app, ["verify", str(stub), "--modelo", "130", "--ejercicio", "24"])
        assert result.exit_code != 0
        combined = " ".join((result.stdout + (result.stderr or "")).split()).lower()
        assert "4-digit" in combined or "year" in combined


class TestDiffRejectsBadFlags:
    def test_non_numeric_modelo_is_rejected(self, tmp_path: Path) -> None:
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b" ")
        b.write_bytes(b" ")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--modelo", "ABC", "--ejercicio", "2024"])
        assert result.exit_code != 0
