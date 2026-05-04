"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from aeat.core.paths import PROJECT_ROOT

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()
_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_WORKBOOK_ROOT = PROJECT_ROOT / "corpus" / "aeat_official" / "disenos_registro"


def test_registry_inspect_cli_reports_committed_tree_inventory() -> None:
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verified"] is False
    assert payload["modelo_count"] == 1
    assert payload["revision_count"] == 1
    assert payload["casilla_count"] == 19
    assert payload["formula_count"] == 9
    assert payload["extraction_profile_count"] == 1
    assert payload["cross_reference_count"] == 1
    assert payload["workbook_parity_ref_count"] == 1
    assert payload["verification_expectation_count"] == 1
    assert payload["application_link_count"] == 5
    assert payload["application_link_surfaces"] == [
        "calculation",
        "extractor",
        "filing",
        "portal",
        "verification",
    ]
    assert payload["modelos"] == ["130"]


def test_registry_verify_cli_validates_committed_sources_and_catalogues() -> None:
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--source-root",
            str(PROJECT_ROOT),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verified"] is True
    assert payload["source_reference_count"] == 1
    assert payload["application_link_surfaces"] == [
        "calculation",
        "extractor",
        "filing",
        "portal",
        "verification",
    ]


def test_registry_verify_cli_fails_fast_on_missing_committed_corpus_source(tmp_path) -> None:
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--source-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "missing corpus file" in str(result.exception)


def test_registry_workbook_verify_cli_reports_json_from_official_corpus() -> None:
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(_WORKBOOK_ROOT),
            "--limit",
            "1",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["workbook_count"] >= 1
    assert payload["scanned_count"] == 1
    assert payload["formula_workbook_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["modelo_coverage"][0]["modelo"]


def test_registry_workbook_verify_cli_reports_text_from_official_corpus() -> None:
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(_WORKBOOK_ROOT),
            "--limit",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "backend_exists=True" in result.output
    assert "formula_workbook_count=1" in result.output


def test_registry_workbook_verify_cli_writes_json_report_from_official_corpus(tmp_path) -> None:
    output = tmp_path / "reports" / "workbooks.json"

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(_WORKBOOK_ROOT),
            "--limit",
            "1",
            "--per-file-timeout",
            "1",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["workbook_count"] >= 1
    assert payload["formula_workbook_count"] == 1


def test_registry_workbook_verify_cli_resumes_from_json_report_from_official_corpus(tmp_path) -> None:
    output = tmp_path / "reports" / "workbooks.json"
    first = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "workbooks",
            "verify",
            "--root",
            str(_WORKBOOK_ROOT),
            "--limit",
            "1",
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
            str(_WORKBOOK_ROOT),
            "--limit",
            "1",
            "--resume-from",
            str(output),
            "--json",
        ],
    )

    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload["workbook_count"] >= 1
    assert payload["formula_workbook_count"] == 1
