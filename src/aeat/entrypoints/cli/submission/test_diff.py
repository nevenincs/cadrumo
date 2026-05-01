"""Tests for ``aeat submission diff`` (EPIC #305 +)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()


def _unwrap_result(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output)["result"])


def _write_draft_and_export(
    tmp_path: Path,
    *,
    modelo: str,
    period: str,
    values: dict[str, str],
    out_name: str,
) -> Path:
    draft = {
        "draft_id": f"DIFF-{out_name}",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": values,
        "findings": [],
    }
    draft_path = tmp_path / f"{out_name}-draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    output_dir = tmp_path / out_name
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


_BASE_130_VALUES: dict[str, str] = {
    "01": "10000.00",
    "02": "3000.00",
    "03": "7000.00",
    "04": "1400.00",
    "07": "1400.00",
    "12": "1400.00",
    "14": "1400.00",
    "17": "1400.00",
    "19": "1400.00",
}


class TestDiffCommand:
    def test_diff_identical_files_exits_0(self, tmp_path: Path) -> None:
        a = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=_BASE_130_VALUES, out_name="a")
        b = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=_BASE_130_VALUES, out_name="b")
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 0, result.stdout
        assert "byte-identical" in result.stdout

    def test_diff_different_casilla_exits_1_and_names_the_delta(self, tmp_path: Path) -> None:
        a = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=_BASE_130_VALUES, out_name="a")
        tweaked = {**_BASE_130_VALUES, "01": "99999.00"}
        b = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=tweaked, out_name="b")
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 1, result.stdout
        assert "MISMATCH" in result.stdout
        # Casilla 01 changed 10000 -> 99999; both numbers should appear.
        assert "01" in result.stdout
        assert "10000" in result.stdout or "10 000" in result.stdout
        assert "99999" in result.stdout or "99 999" in result.stdout

    def test_diff_modelo_303_envelope_field_delta(self, tmp_path: Path) -> None:
        """envelope field_values diff (NIF / PERIODO etc.) surfaces."""
        # Two 303 filings at different periods — DP30301_F010_DEVENGO_PER_ODO
        # differs, and diff must name it.
        a = _write_draft_and_export(tmp_path, modelo="303", period="2024Q1", values=_BASE_130_VALUES, out_name="a")
        b = _write_draft_and_export(tmp_path, modelo="303", period="2024Q2", values=_BASE_130_VALUES, out_name="b")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--modelo", "303", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 1, result.stdout
        doc = _unwrap_result(result.stdout)
        field_deltas = cast(list[dict[str, Any]], doc["field_deltas"])
        field_ids = {d["field_id"] for d in field_deltas}
        assert "DP30301_F010_DEVENGO_PER_ODO" in field_ids

    def test_diff_modelo_303_envelope_casilla_delta(self, tmp_path: Path) -> None:
        base = {"01": "10000.00", "86": "500.00"}
        a = _write_draft_and_export(tmp_path, modelo="303", period="2024Q1", values=base, out_name="a")
        tweaked = {"01": "10000.00", "86": "1500.00"}
        b = _write_draft_and_export(tmp_path, modelo="303", period="2024Q1", values=tweaked, out_name="b")
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 1, result.stdout
        assert "MISMATCH" in result.stdout
        assert "86" in result.stdout

    def test_diff_unsupported_modelo_exits_2(self, tmp_path: Path) -> None:
        a = tmp_path / "fake_a.390"
        b = tmp_path / "fake_b.390"
        a.write_bytes(b"  ")
        b.write_bytes(b"  ")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--modelo", "390", "--ejercicio", "2024"])
        assert result.exit_code == 2
        assert "UNSUPPORTED" in result.stdout

    def test_diff_cant_infer_from_nonstandard_filename(self, tmp_path: Path) -> None:
        a = tmp_path / "kent.bin"
        b = tmp_path / "kent2.bin"
        a.write_bytes(b"  ")
        b.write_bytes(b"  ")
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 2
        assert "cannot infer" in result.stdout

    def test_diff_json_identical_files(self, tmp_path: Path) -> None:
        """--json on identical files emits status=identical."""
        a = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=_BASE_130_VALUES, out_name="a")
        b = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=_BASE_130_VALUES, out_name="b")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_result(result.stdout)
        assert doc["status"] == "identical"
        assert doc["bytes"] == 880  # Modelo 130 content + CRLF
        assert doc["casilla_deltas"] == []

    def test_diff_json_casilla_mismatch(self, tmp_path: Path) -> None:
        """--json on semantic diff returns casilla_deltas list."""
        a = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=_BASE_130_VALUES, out_name="a")
        tweaked = {**_BASE_130_VALUES, "01": "99999.00"}
        b = _write_draft_and_export(tmp_path, modelo="130", period="2024Q1", values=tweaked, out_name="b")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--json"])
        assert result.exit_code == 1
        doc = _unwrap_result(result.stdout)
        assert doc["status"] == "mismatch"
        casilla_deltas = cast(list[dict[str, Any]], doc["casilla_deltas"])
        deltas_by_casilla = {d["casilla"]: d for d in casilla_deltas}
        assert "01" in deltas_by_casilla
        assert deltas_by_casilla["01"]["a"] == "10000.00"
        assert deltas_by_casilla["01"]["b"] == "99999.00"

    def test_diff_json_unsupported_modelo(self, tmp_path: Path) -> None:
        a = tmp_path / "fake_a.390"
        b = tmp_path / "fake_b.390"
        a.write_bytes(b"  ")
        b.write_bytes(b"  ")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--modelo", "390", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 2
        doc = json.loads(result.stderr)["error"]
        assert doc["category"] == "REFUSED"
        assert doc["context"]["modelo"] == "390"

    def test_diff_auto_detects_modelo_and_ejercicio_from_filename(self, tmp_path: Path) -> None:
        a = _write_draft_and_export(tmp_path, modelo="303", period="2024Q1", values=_BASE_130_VALUES, out_name="a")
        b = _write_draft_and_export(tmp_path, modelo="303", period="2024Q1", values=_BASE_130_VALUES, out_name="b")
        # No --modelo / --ejercicio passed.
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 0, result.stdout
        assert "byte-identical" in result.stdout
