"""Tests for ``aeat submission export`` (EPIC #201 C3c, wave 81)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()


def _write_draft(tmp_path: Path, *, modelo: str = "130", period: str = "2024Q1", status: str = "DRAFT") -> Path:
    draft = {
        "draft_id": "TEST-0001",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": status,
        "values": {
            "01": "10000.00",
            "02": "3000.00",
            "03": "7000.00",
            "04": "1400.00",
            "05": "0.00",
            "06": "0.00",
            "07": "1400.00",
            "08": "0.00",
            "09": "0.00",
            "10": "0.00",
            "11": "0.00",
            "12": "1400.00",
            "13": "0.00",
            "14": "1400.00",
            "15": "0.00",
            "16": "0.00",
            "17": "1400.00",
            "18": "0.00",
            "19": "1400.00",
        },
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(draft), encoding="utf-8")
    return path


class TestExportCommand:
    def test_modelo_130_q1_2024_writes_880_byte_file(self, tmp_path: Path) -> None:
        draft = _write_draft(tmp_path)
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(output_dir),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE RODRIGUEZ",
                "--tipo",
                "I",
            ],
        )
        assert result.exit_code == 0, result.stdout
        assert "export OK" in result.stdout
        assert "BORRADOR" in result.stdout
        filename = "X1234567L20241T.130"
        output_path = output_dir / filename
        assert output_path.exists()
        payload = output_path.read_bytes()
        # 878 content + 2 CRLF = 880 bytes per the Modelo 130 spec.
        assert len(payload) == 880
        # Spot-check header bytes.
        assert payload[0:3] == b"130"  # MODELO literal
        assert payload[6:7] == b"I"  # TIPO_DECLARACION
        assert payload[12:21] == b"X1234567L"  # NIF
        assert payload[70:74] == b"2024"  # EJERCICIO
        assert payload[74:76] == b"1T"  # PERIODO
        assert payload.endswith(b"\r\n")

    def test_modelo_130_2025_routes_to_clone_schema(self, tmp_path: Path) -> None:
        draft = _write_draft(tmp_path, period="2025Q3")
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(output_dir),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE RODRIGUEZ",
            ],
        )
        assert result.exit_code == 0, result.stdout
        output_path = output_dir / "X1234567L20253T.130"
        assert output_path.exists()

    def test_modelo_303_2024_q1_writes_envelope_file(self, tmp_path: Path) -> None:
        """Wave 92: 303 dispatches through the multi-segment envelope path."""
        draft = _write_draft(tmp_path, modelo="303")
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(output_dir),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE RODRIGUEZ",
                "--tipo",
                "I",
            ],
        )
        assert result.exit_code == 0, result.stdout
        assert "export OK" in result.stdout
        output_path = output_dir / "X1234567L20241T.303"
        assert output_path.exists()
        payload = output_path.read_bytes()
        # 7994 envelope content + CRLF trailer.
        assert len(payload) == 7994 + 2
        assert payload[0:2] == b"<T"
        assert payload[2:5] == b"303"
        assert payload[6:10] == b"2024"  # ejercicio in envelope header
        # Per-page identification in DP30301 starts at byte 328.
        # DP30301 offsets (1-based in spec): F006 TIPO=13, F007 NIF=14, F010 PERIODO=107.
        # 0-indexed within payload: 328 + (offset - 1).
        dp30301_start = 328
        assert payload[dp30301_start + 12 : dp30301_start + 13] == b"I"  # TIPO_DECLARACION
        assert payload[dp30301_start + 13 : dp30301_start + 22] == b"X1234567L"  # NIF
        assert payload[dp30301_start + 106 : dp30301_start + 108] == b"1T"  # PERIODO
        assert payload.endswith(b"\r\n")

    def test_unsupported_modelo_exits_2(self, tmp_path: Path) -> None:
        """Modelo 390 is not yet registered; export must refuse with exit 2."""
        draft = _write_draft(tmp_path, modelo="390", period="2024Q4")
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(output_dir),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        assert result.exit_code == 2
        assert "UNSUPPORTED" in result.stdout

    def test_invalid_period_rejects(self, tmp_path: Path) -> None:
        draft = _write_draft(tmp_path, period="garbage")
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(output_dir),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        assert result.exit_code != 0

    def test_incomplete_draft_refused(self, tmp_path: Path) -> None:
        """INCOMPLETE drafts fail validation; export refuses."""
        draft = _write_draft(tmp_path, status="INCOMPLETE")
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(output_dir),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        assert result.exit_code == 3
        assert "REFUSED" in result.stdout

    def test_missing_required_flag_fails(self, tmp_path: Path) -> None:
        """--nombre and --apellidos are required."""
        draft = _write_draft(tmp_path)
        output_dir = tmp_path / "out"
        result = _runner.invoke(
            app,
            ["export", str(draft), "--output-dir", str(output_dir)],
        )
        assert result.exit_code != 0
