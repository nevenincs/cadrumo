"""CLI tests for the casillas command group."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .casillas import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

runner = CliRunner()


def _write_catalogue(root: Path, *, definition_reviewed_by: str = "codex") -> None:
    """Write a minimal valid catalogue file for CLI tests."""
    path = root / "modelo_130" / "2025Q4.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "modelo": "MODELO_130",
                "period": "2025Q4",
                "records": [
                    {
                        "synthetic": False,
                        "modelo": "MODELO_130",
                        "period": "2025Q4",
                        "casilla_id": "01",
                        "label": {"es": "Rendimiento neto", "en": "Net income", "hu": "Netto jovedelem"},
                        "help": {"es": "Importe acumulado", "en": "Accumulated amount", "hu": "Halmozott osszeg"},
                        "data_type": "currency_eur",
                        "select_options": None,
                        "required": True,
                        "computed": False,
                        "formula": None,
                        "references_casillas": [],
                        "references_rules": [],
                        "validation": [],
                        "source_manual_url": "https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html",
                        "source_page": 1,
                        "source_section": "1",
                        "definition_reviewed_by": definition_reviewed_by,
                        "definition_reviewed_at": "2026-04-12",
                        "llm_draft_provenance": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_verify_cli_rejects_records_lacking_reviewer_fields(tmp_path: Path) -> None:
    """The verify command must fail when definition_reviewed_by is blank."""
    root = tmp_path / "casillas"
    _write_catalogue(root, definition_reviewed_by="")

    result = runner.invoke(app, ["verify", "--modelo", "MODELO_130", "--period", "2025Q4", "--root", str(root)])

    assert result.exit_code == 1
    assert "unreviewed_record" in result.stdout


def test_list_command_prints_catalogue(tmp_path: Path) -> None:
    """The list command must print the canonical JSON payload."""
    root = tmp_path / "casillas"
    _write_catalogue(root)

    result = runner.invoke(app, ["list", "--modelo", "MODELO_130", "--period", "2025Q4", "--root", str(root)])

    assert result.exit_code == 0
    assert '"modelo": "MODELO_130"' in result.stdout


def test_extract_and_translate_report_issue21_dependency(tmp_path: Path) -> None:
    """Draft commands must fail clearly until the real LLM client lands."""
    root = tmp_path / "casillas"
    _write_catalogue(root)

    extract_result = runner.invoke(
        app,
        ["extract", "--modelo", "MODELO_130", "--period", "2025Q4", "--root", str(root)],
    )
    translate_result = runner.invoke(
        app,
        ["translate", "--modelo", "MODELO_130", "--period", "2025Q4", "--root", str(root)],
    )

    assert extract_result.exit_code == 2
    assert translate_result.exit_code == 2
    assert "issue-21" in extract_result.stdout
    assert "issue-21" in translate_result.stdout
