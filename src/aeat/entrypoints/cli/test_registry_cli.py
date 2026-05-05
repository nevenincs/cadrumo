"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.outbound.aeat.sede import Declaration
from aeat.application.auth import AuthProviderKind
from aeat.core.paths import PROJECT_ROOT
from aeat.domain.calculations.registry import load_registry_tree

from . import app
from .registry import _filed_data_listing_row, select_declarations_for_capture

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()
_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_WORKBOOK_ROOT = PROJECT_ROOT / "corpus" / "aeat_official" / "disenos_registro"


def _registry_modelos() -> tuple[str, ...]:
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    return tuple(sorted(modelo.id for modelo in modelos))


def _registry_application_surfaces() -> set[str]:
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    return {
        link.surface
        for modelo in modelos
        for revision in modelo.revisions.values()
        for link in revision.application_links
    }


def _first_registry_modelo() -> str:
    return _registry_modelos()[0]


def test_registry_inspect_cli_reports_tree_inventory() -> None:
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
    registry_modelos = _registry_modelos()
    registry_surfaces = _registry_application_surfaces()
    assert payload["verified"] is False
    assert payload["modelos"] == list(registry_modelos)
    assert payload["modelo_count"] == len(registry_modelos)
    assert payload["revision_count"] >= 1
    assert payload["casilla_count"] > 0
    assert payload["formula_count"] > 0
    assert payload["extraction_profile_count"] > 0
    assert payload["cross_reference_count"] > 0
    assert payload["workbook_parity_ref_count"] > 0
    assert payload["verification_expectation_count"] > 0
    assert payload["application_link_count"] > 0
    assert payload["filing_schedule_count"] > 0
    assert set(payload["application_link_surfaces"]) == registry_surfaces
    assert len(payload["revision_details"]) == payload["revision_count"]
    revision = payload["revision_details"][0]
    assert revision["modelo"] in payload["modelos"]
    assert revision["revision"]
    assert revision["legal_refs"]
    assert revision["source_refs"]
    assert revision["export_layout_count"] == len(revision["export_layout_ids"])
    assert revision["export_record_count"] > 0
    assert revision["export_field_count"] > 0
    assert revision["deadline_window_count"] == len(revision["deadline_periods"])
    assert revision["filing_schedule_count"] == len(revision["filing_schedule_ids"])
    assert revision["portal_guard_policy_ids"]
    assert revision["workbook_parity"]
    workbook_reference = revision["workbook_parity"][0]
    assert workbook_reference["id"]
    assert workbook_reference["workbook_source"] in revision["source_refs"]
    assert workbook_reference["formula_coverage"]
    assert workbook_reference["runner_required"] is False or workbook_reference["output_cell_count"] > 0


def test_registry_verify_cli_validates_sources_and_catalogues() -> None:
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
    registry_surfaces = _registry_application_surfaces()
    assert payload["verified"] is True
    assert payload["source_reference_count"] > 0
    assert set(payload["application_link_surfaces"]) == registry_surfaces
    assert payload["filing_schedule_count"] > 0
    assert payload["revision_details"][0]["export_field_count"] > 0


def test_registry_verify_cli_fails_fast_on_missing_corpus_source(tmp_path) -> None:
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
    assert payload["failed_count"] == 0
    assert payload["runner"]["status"] == "available"
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
    assert "failed_count=0" in result.output


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
    assert payload["failed_count"] == 0


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
    assert payload["failed_count"] == 0


def test_capture_selector_filters_register_rows_by_period_and_expediente() -> None:
    rows = (
        _declaration(expediente_id="202610013522222A", period="1T"),
        _declaration(expediente_id="202620013522222B", period="2T"),
    )

    selected = select_declarations_for_capture(
        rows,
        period="2T",
        expediente_id="202620013522222B",
    )

    assert selected == (rows[1],)


def test_filed_data_listing_row_reports_available_read_surfaces() -> None:
    modelo = _first_registry_modelo()
    row = _declaration(expediente_id="202511113520436S", period="1T", modelo=modelo).model_copy(
        update={
            "ejercicio": 2025,
            "declaration_copy_link_text": None,
            "declaration_copy_cell_index": None,
        }
    )

    listed = _filed_data_listing_row(row)

    assert listed.modelo == modelo
    assert listed.year == 2025
    assert listed.period == "1T"
    assert listed.expediente_id == "202511113520436S"
    assert listed.has_submitted_file is True
    assert listed.has_justificante is True
    assert listed.has_declaration_copy is False


def test_list_filed_data_cli_refuses_expired_clave_session_before_remote_read(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "list-filed-data",
            "--modelo",
            _first_registry_modelo(),
            "--from-year",
            "2024",
            "--to-year",
            "2025",
        ],
        env={
            "AEAT_TOKEN_DIR": str(tmp_path),
            "AEAT_DEFAULT_PROFILE_NAME": "default",
            "AEAT_OUTPUT_LANGUAGE": "en",
        },
    )

    assert result.exit_code != 0
    assert "Cl@ve Movil AEAT session is expired" in result.output


def test_capture_filed_data_cli_refuses_expired_clave_session_before_local_writes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CERTIFICATE,
        authenticated_at=now,
        idle_deadline=now + timedelta(minutes=20),
    )
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )
    output_root = tmp_path / "captured"

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "registry",
            "capture-filed-data",
            "--modelo",
            _first_registry_modelo(),
            "--year",
            "2024",
            "--period",
            "1T",
            "--limit",
            "1",
            "--output-root",
            str(output_root),
        ],
        env={
            "AEAT_TOKEN_DIR": str(tmp_path),
            "AEAT_DEFAULT_PROFILE_NAME": "default",
            "AEAT_OUTPUT_LANGUAGE": "en",
        },
    )

    assert result.exit_code != 0
    assert "Cl@ve Movil AEAT session is expired" in result.output
    assert not output_root.exists()


def _declaration(*, expediente_id: str, period: str, modelo: str | None = None) -> Declaration:
    return Declaration(
        modelo=modelo or _first_registry_modelo(),
        ejercicio=2026,
        period=period,
        expediente_id=expediente_id,
        estado="ALTA",
        presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        justificante_link_text="Ver",
        archive_link_text="Ver",
    )


def _seed_session(
    token_dir: Path,
    kind: AuthProviderKind,
    *,
    authenticated_at: datetime,
    idle_deadline: datetime,
) -> None:
    stem = "clave-movil-storage" if kind is AuthProviderKind.CLAVE_MOVIL else "storage"
    storage = token_dir / f"default-{stem}.json"
    metadata = storage.with_suffix(".meta.json")
    storage.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
    metadata.write_text(
        json.dumps(
            {
                "provider_kind": kind.value,
                "identity_nif": "12345678Z",
                "authenticated_at": authenticated_at.isoformat(),
                "idle_deadline": idle_deadline.isoformat(),
            },
        ),
        encoding="utf-8",
    )
