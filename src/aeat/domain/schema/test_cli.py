"""Unit tests for :mod:`aeat.cli.schema`.

Every test exercises the real Typer app (no mocks). Network fetches
go through :func:`aeat.schema.fetch_boe_pdf` whose unit tests rely
on ``file://`` URLs served from ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...entrypoints.cli.schema import app
from .testing import build_fake_boe_pdf

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_ANNEX_LINES: tuple[str, ...] = (
    "# Rendimiento de la actividad",
    "01 Base imponible 1T",
    "03 Ingresos computables 1T",
    "07 Rendimiento neto 1T",
    "13 Pago fraccionado 1T",
    "Casilla 07 = Casilla 01 - Casilla 03",
    "Casilla 13 = Casilla 07 x 0,20",
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "boe.pdf"
    build_fake_boe_pdf(pdf_path, annex_lines=_ANNEX_LINES)
    return pdf_path


def test_refresh_with_override_writes_cache(
    runner: CliRunner,
    tmp_path: Path,
    sample_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "schema-cache"
    monkeypatch.setenv("AEAT_SCHEMA_CACHE_DIR", str(cache_dir))
    result = runner.invoke(
        app,
        [
            "refresh",
            "--modelo",
            "MODELO_130",
            "--boe-ref",
            "BOE-A-2023-15412",
            "--period",
            "2025Q4",
            "--_pdf-path-override",
            str(sample_pdf),
        ],
    )
    assert result.exit_code == 0, result.output
    expected = cache_dir / "modelo_130" / "BOE-A-2023-15412.json"
    assert expected.exists()


def test_refresh_by_value_also_accepted(
    runner: CliRunner,
    tmp_path: Path,
    sample_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "schema-cache"
    monkeypatch.setenv("AEAT_SCHEMA_CACHE_DIR", str(cache_dir))
    result = runner.invoke(
        app,
        [
            "refresh",
            "--modelo",
            "130",
            "--boe-ref",
            "BOE-A-2023-15412",
            "--period",
            "2025Q4",
            "--_pdf-path-override",
            str(sample_pdf),
        ],
    )
    assert result.exit_code == 0, result.output


def test_show_prints_cached_json(
    runner: CliRunner,
    tmp_path: Path,
    sample_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "schema-cache"
    monkeypatch.setenv("AEAT_SCHEMA_CACHE_DIR", str(cache_dir))
    runner.invoke(
        app,
        [
            "refresh",
            "--modelo",
            "MODELO_130",
            "--boe-ref",
            "BOE-A-2023-15412",
            "--period",
            "2025Q4",
            "--_pdf-path-override",
            str(sample_pdf),
        ],
    )
    result = runner.invoke(
        app,
        [
            "show",
            "--modelo",
            "MODELO_130",
            "--boe-ref",
            "BOE-A-2023-15412",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["modelo_code"] == "130"
    assert payload["period"] == "2025Q4"


def test_refresh_unknown_modelo_is_rejected(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "refresh",
            "--modelo",
            "MODELO_NOPE",
            "--boe-ref",
            "BOE-A-FAKE",
            "--period",
            "2025Q4",
        ],
    )
    assert result.exit_code != 0


def test_refresh_via_file_url_override(
    runner: CliRunner,
    tmp_path: Path,
    sample_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "schema-cache"
    monkeypatch.setenv("AEAT_SCHEMA_CACHE_DIR", str(cache_dir))
    file_url = sample_pdf.resolve().as_uri()
    override = json.dumps({"130": {"BOE-A-2023-15412": file_url}})
    monkeypatch.setenv("AEAT_SCHEMA_SOURCE_URLS_OVERRIDE", override)
    result = runner.invoke(
        app,
        [
            "refresh",
            "--modelo",
            "MODELO_130",
            "--boe-ref",
            "BOE-A-2023-15412",
            "--period",
            "2025Q4",
        ],
    )
    assert result.exit_code == 0, result.output
    expected = cache_dir / "modelo_130" / "BOE-A-2023-15412.json"
    assert expected.exists()
