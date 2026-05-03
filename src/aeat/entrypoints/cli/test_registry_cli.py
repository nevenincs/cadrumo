"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _write_formula_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Modelo"
    worksheet["A1"] = 1
    worksheet["A2"] = 2
    worksheet["B1"] = "=A1+A2"
    workbook.save(path)


def _write_registry_tree(root: Path, source_root: Path, *, write_source: bool = True) -> None:
    source_path = source_root / "corpus" / "aeat_official" / "disenos_registro" / "modelo_303" / "example.xlsx"
    if write_source:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"x")
    sha = hashlib.sha256(b"x").hexdigest()
    legal_dir = root / "legal"
    modelos_dir = root / "modelos"
    legal_dir.mkdir(parents=True, exist_ok=True)
    modelos_dir.mkdir(parents=True, exist_ok=True)
    (legal_dir / "base.toml").write_text(
        f"""
[legal."ley-37-1992:art-90"]
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/ley-37-1992.json#art-90"
document_id = "BOE-A-1992-28740"
article = "90"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90"
effective_from = 1992-12-29
review_status = "reviewed"

[sources."aeat-dr-303"]
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/aeat_official/disenos_registro/modelo_303/example.xlsx"
sha256 = "{sha}"
bytes = 1
retrieved_at = 2026-05-03
source_url = "https://sede.agenciatributaria.gob.es/example.xlsx"
review_status = "reviewed"
""",
        encoding="utf-8",
    )
    (modelos_dir / "303.toml").write_text(
        """
[modelo]
id = "303"
title = "IVA autoliquidacion"
official_name = "Impuesto sobre el Valor Anadido. Autoliquidacion"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303"]

[revisions."2026"]
valid_from = 2026-01-01
period_selector = { years = [2026], periods = ["1T"] }
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303"]

[[revisions."2026".bindings]]
id = "vat.output"
source = "vat"
selector = { fact = "output_quota" }
aggregation = { op = "sum" }
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303"]

[[revisions."2026".casillas]]
id = "03"
number = "03"
label = "IVA devengado"
section = ["iva"]
data_type = "money"
required = true
input_kind = "bound"
binding = "vat.output"
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["aeat-dr-303"]
""",
        encoding="utf-8",
    )


def test_registry_inspect_cli_reports_tree_inventory(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _write_registry_tree(registry_root, tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(registry_root),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verified"] is False
    assert payload["modelo_count"] == 1
    assert payload["revision_count"] == 1
    assert payload["modelos"] == ["303"]


def test_registry_verify_cli_validates_sources_and_catalogues(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _write_registry_tree(registry_root, tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(registry_root),
            "--source-root",
            str(tmp_path),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verified"] is True
    assert payload["source_reference_count"] == 1


def test_registry_verify_cli_fails_fast_on_missing_corpus_source(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _write_registry_tree(registry_root, tmp_path, write_source=False)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(registry_root),
            "--source-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "missing corpus file" in str(result.exception)


def test_registry_workbook_verify_cli_reports_json(tmp_path: Path) -> None:
    _write_formula_workbook(tmp_path / "modelo_303" / "files" / "303-test.xlsx")

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(tmp_path),
            "--limit",
            "10",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["workbook_count"] == 1
    assert payload["scanned_count"] == 1
    assert payload["formula_workbook_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["modelo_coverage"][0]["modelo"] == "303"


def test_registry_workbook_verify_cli_reports_text(tmp_path: Path) -> None:
    _write_formula_workbook(tmp_path / "modelo_390" / "files" / "390-test.xlsx")

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(tmp_path),
            "--limit",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert "backend_exists=True" in result.output
    assert "formula_workbook_count=1" in result.output


def test_registry_workbook_verify_cli_writes_json_report(tmp_path: Path) -> None:
    _write_formula_workbook(tmp_path / "modelo_303" / "files" / "303-test.xlsx")
    output = tmp_path / "reports" / "workbooks.json"

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(tmp_path),
            "--limit",
            "10",
            "--per-file-timeout",
            "1",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["workbook_count"] == 1
    assert payload["formula_workbook_count"] == 1


def test_registry_workbook_verify_cli_resumes_from_json_report(tmp_path: Path) -> None:
    _write_formula_workbook(tmp_path / "modelo_303" / "files" / "303-test.xlsx")
    output = tmp_path / "reports" / "workbooks.json"
    first = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(tmp_path),
            "--limit",
            "10",
            "--output",
            str(output),
        ],
    )
    assert first.exit_code == 0

    second = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(tmp_path),
            "--limit",
            "10",
            "--resume-from",
            str(output),
            "--json",
        ],
    )

    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload["workbook_count"] == 1
    assert payload["formula_workbook_count"] == 1
