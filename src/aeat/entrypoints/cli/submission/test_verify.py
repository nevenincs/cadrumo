"""Tests for ``aeat submission verify`` (EPIC #305 +)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Disable colour codes so the JSON output is parseable by json.loads in tests.
_runner_plain = CliRunner()

_runner = CliRunner()


def _unwrap_result(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output)["result"])


def _export_then_path(tmp_path: Path, *, modelo: str, period: str) -> Path:
    """Export a known-good draft and return the output path."""
    draft = {
        "draft_id": "VERIFY-0001",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {
            "01": "10000.00",
            "02": "3000.00",
            "03": "7000.00",
            "04": "1400.00",
            "07": "1400.00",
            "12": "1400.00",
            "14": "1400.00",
            "17": "1400.00",
            "19": "1400.00",
        },
        "findings": [],
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    output_dir = tmp_path / "out"
    result = _runner.invoke(
        app,
        [
            "export",
            str(draft_path),
            "--output-dir",
            str(output_dir),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "I",
        ],
    )
    assert result.exit_code == 0, result.stdout
    ejercicio = period[:4]
    quarter = period[-2:].replace("Q", "") + "T"
    return output_dir / f"X1234567L{ejercicio}{quarter}.{modelo}"


class TestVerifyCommand:
    def test_verify_modelo_130_exports_round_trip(self, tmp_path: Path) -> None:
        """A Modelo 130 export must decode back through verify."""
        path = _export_then_path(tmp_path, modelo="130", period="2024Q1")
        result = _runner.invoke(app, ["verify", str(path), "--modelo", "130", "--ejercicio", "2024"])
        assert result.exit_code == 0, result.stdout
        assert "verify OK" in result.stdout
        # Casilla 01 = 10 000.00 should appear in the output.
        assert "10000" in result.stdout or "10 000" in result.stdout or "10000.00" in result.stdout

    def test_verify_modelo_303_envelope_round_trip(self, tmp_path: Path) -> None:
        """A Modelo 303 export must decode back through the envelope parser."""
        path = _export_then_path(tmp_path, modelo="303", period="2024Q1")
        result = _runner.invoke(app, ["verify", str(path), "--modelo", "303", "--ejercicio", "2024"])
        assert result.exit_code == 0, result.stdout
        assert "verify OK" in result.stdout
        assert "segments=8" in result.stdout

    def test_verify_unsupported_modelo_exits_2(self, tmp_path: Path) -> None:
        # Create a dummy file so the argument validation passes.
        fake = tmp_path / "fake.390"
        fake.write_bytes(b"  ")
        result = _runner.invoke(app, ["verify", str(fake), "--modelo", "390", "--ejercicio", "2024"])
        assert result.exit_code == 2
        assert "UNSUPPORTED" in result.stdout

    def test_verify_corrupt_payload_exits_2(self, tmp_path: Path) -> None:
        """A wrong-length payload must fail the decoder and surface exit 2."""
        bad = tmp_path / "bad.130"
        bad.write_bytes(b"NOT-A-VALID-MODELO-130-PAYLOAD\r\n")
        result = _runner.invoke(app, ["verify", str(bad), "--modelo", "130", "--ejercicio", "2024"])
        assert result.exit_code == 2
        assert "FAILED" in result.stdout

    def test_verify_missing_file_exits_nonzero(self, tmp_path: Path) -> None:
        """Typer's ``exists=True`` guard refuses missing files."""
        result = _runner.invoke(
            app, ["verify", str(tmp_path / "missing.130"), "--modelo", "130", "--ejercicio", "2024"]
        )
        assert result.exit_code != 0

    def test_verify_auto_detects_modelo_and_ejercicio_from_filename(self, tmp_path: Path) -> None:
        """{NIF}{YYYY}{PERIODO}.{modelo} filename parses without explicit flags."""
        path = _export_then_path(tmp_path, modelo="303", period="2024Q1")
        # No --modelo / --ejercicio passed.
        result = _runner.invoke(app, ["verify", str(path)])
        assert result.exit_code == 0, result.stdout
        assert "verify OK" in result.stdout
        assert "modelo=303" in result.stdout
        assert "ejercicio=2024" in result.stdout

    def test_verify_nonstandard_filename_requires_flags(self, tmp_path: Path) -> None:
        """A renamed file can't be auto-parsed; verify must exit 2."""
        path = _export_then_path(tmp_path, modelo="130", period="2024Q1")
        renamed = path.with_name("kent-archive.bin")
        path.rename(renamed)
        result = _runner.invoke(app, ["verify", str(renamed)])
        assert result.exit_code == 2
        assert "cannot infer" in result.stdout

    def test_verify_json_modelo_130(self, tmp_path: Path) -> None:
        """--json emits a JSON document with the decoded casillas."""
        path = _export_then_path(tmp_path, modelo="130", period="2024Q1")
        result = _runner.invoke(app, ["verify", str(path), "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_result(result.stdout)
        assert doc["status"] == "ok"
        assert doc["kind"] == "record"
        assert doc["modelo"] == "130"
        assert doc["ejercicio"] == "2024"
        assert doc["raw_length"] == 878
        # Casilla 01 = 10 000.00 round-trips as Decimal-string.
        casillas = cast(dict[str, Any], doc["casillas"])
        assert casillas["01"] == "10000.00"

    def test_verify_json_modelo_303(self, tmp_path: Path) -> None:
        """--json works on envelope schemas, listing segment IDs."""
        path = _export_then_path(tmp_path, modelo="303", period="2024Q1")
        result = _runner.invoke(app, ["verify", str(path), "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_result(result.stdout)
        assert doc["status"] == "ok"
        assert doc["kind"] == "envelope"
        assert doc["modelo"] == "303"
        segments = cast(list[str], doc["segments"])
        assert len(segments) == 8
        assert "DP30300" in segments
        assert "DP30301" in segments
        # envelope fields surface the merged NIF / periodo / tipo.
        fields = cast(dict[str, Any], doc["fields"])
        assert fields["DP30301_F007_IDENTIFICACI_N_NIF"] == "X1234567L"
        assert fields["DP30301_F010_DEVENGO_PER_ODO"] == "1T"
        assert fields["DP30301_F006_TIPO_DECLARACI_N"] == "I"

    def test_verify_json_error_on_corrupt_payload(self, tmp_path: Path) -> None:
        """--json emits a status=error document even on decoder failure."""
        bad = tmp_path / "bad.130"
        bad.write_bytes(b"NOT-A-VALID-MODELO-130-PAYLOAD\r\n")
        result = _runner.invoke(app, ["verify", str(bad), "--modelo", "130", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = json.loads(result.stderr)["error"]
        assert doc["category"] == "REFUSED"
        assert doc["context"]["modelo"] == "130"

    def test_verify_explicit_flags_override_filename_inference(self, tmp_path: Path) -> None:
        """Explicit --modelo and --ejercicio win over filename auto-detect."""
        # Export modelo 130, but rename to look like a 303 file; explicit
        # flags must take precedence over the (wrong) filename extension.
        path = _export_then_path(tmp_path, modelo="130", period="2024Q1")
        fake_303 = path.with_suffix(".303")
        path.rename(fake_303)
        result = _runner.invoke(app, ["verify", str(fake_303), "--modelo", "130", "--ejercicio", "2024"])
        assert result.exit_code == 0, result.stdout
