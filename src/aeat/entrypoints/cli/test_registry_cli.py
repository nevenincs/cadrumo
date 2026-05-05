"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import typer
from pydantic import AnyHttpUrl
from typer.testing import CliRunner

from aeat.adapters.outbound.aeat.sede import (
    Declaration,
    FiledDeclarationArtefact,
    FiledDeclarationObservation,
    FiledDeclarationObservationStore,
    ObservedCasillaValue,
)
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.application.auth import AuthProviderKind
from aeat.core.paths import PROJECT_ROOT
from aeat.domain.calculations.registry import build_snapshot, calculate_registry_snapshot, load_registry_tree

from . import app
from .registry import (
    _filed_data_listing_row,
    capture_source_filed_data,
    select_declarations_for_capture,
    verify_filed_state,
)

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
    assert payload["relation_count"] > 0
    assert "periodic_to_annual_summary" in payload["relation_dependency_roles"]
    assert payload["filing_schedule_count"] > 0
    assert set(payload["application_link_surfaces"]) == registry_surfaces
    assert len(payload["revision_details"]) == payload["revision_count"]
    revision = payload["revision_details"][0]
    assert revision["modelo"] in payload["modelos"]
    assert revision["revision"]
    assert revision["legal_refs"]
    assert revision["source_refs"]
    assert revision["export_layout_count"] == len(revision["export_layout_ids"])
    assert revision["deadline_window_count"] == len(revision["deadline_periods"])
    assert revision["relation_count"] == len(revision["relation_ids"])
    assert revision["filing_schedule_count"] == len(revision["filing_schedule_ids"])
    assert revision["workbook_parity"]
    export_revision = next(detail for detail in payload["revision_details"] if detail["export_field_count"] > 0)
    assert export_revision["export_record_count"] > 0
    guarded_revision = next(detail for detail in payload["revision_details"] if detail["portal_guard_policy_ids"])
    assert guarded_revision["portal_guard_policy_ids"]
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
    assert payload["relation_count"] > 0
    assert "periodic_to_annual_summary" in payload["relation_dependency_roles"]
    assert payload["filing_schedule_count"] > 0
    assert any(detail["export_field_count"] > 0 for detail in payload["revision_details"])
    modelo_180 = next(detail for detail in payload["revision_details"] if detail["modelo"] == "180")
    assert modelo_180["relation_count"] > 0
    assert modelo_180["relation_dependency_roles"] == ["periodic_to_annual_summary"]


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


def test_verify_filed_state_compares_local_calculation_to_encrypted_observation(tmp_path: Path) -> None:
    provider = EphemeralMasterKeyProvider()
    store = FiledDeclarationObservationStore(tmp_path / "observations", master_key_provider=provider)
    primary, source = _modelo_130_filed_state_observations()
    primary_path = store.persist_observation(primary)
    source_path = store.persist_observation(source)

    report = verify_filed_state(
        observation_path=primary_path,
        source_observation_paths=(source_path,),
        registry_root=_REGISTRY_ROOT,
        source_root=PROJECT_ROOT,
        master_key_provider=provider,
    )

    assert report.comparison.status == "satisfied"
    assert report.comparison.modelo == "130"
    assert "19" in report.comparison.compared_casillas
    assert report.comparison.drifts == ()


def test_verify_filed_state_reports_drift_from_encrypted_observation(tmp_path: Path) -> None:
    provider = EphemeralMasterKeyProvider()
    store = FiledDeclarationObservationStore(tmp_path / "observations", master_key_provider=provider)
    primary, source = _modelo_130_filed_state_observations()
    casillas = tuple(
        item.model_copy(update={"value": str(Decimal(item.value) + Decimal("0.01"))})
        if item.casilla_id == "19"
        else item
        for item in primary.casillas
    )
    primary_path = store.persist_observation(primary.model_copy(update={"casillas": casillas}))
    source_path = store.persist_observation(source)

    report = verify_filed_state(
        observation_path=primary_path,
        source_observation_paths=(source_path,),
        registry_root=_REGISTRY_ROOT,
        source_root=PROJECT_ROOT,
        required_casillas=("19",),
        master_key_provider=provider,
    )

    assert report.comparison.status == "failed"
    assert report.comparison.drifts[0].casilla_id == "19"
    assert report.comparison.drifts[0].delta == Decimal("-0.01")


def test_verify_filed_state_cli_help_uses_locale_strings() -> None:
    result = _RUNNER.invoke(
        app,
        ["app", "registry", "verify-filed-state", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    assert "estado presentado capturado" in result.output
    assert "cli.registry.verify_filed_state_help" not in result.output
    assert "--source-observation" in result.output


def test_capture_source_filed_data_cli_help_uses_locale_strings() -> None:
    result = _RUNNER.invoke(
        app,
        ["app", "registry", "capture-source-filed-data", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    assert "observaciones fuente presentadas" in result.output
    assert "cli.registry.capture_source_filed_data_help" not in result.output
    assert "--source-root" in result.output


def test_list_filed_data_cli_refuses_expired_session_before_remote_read(tmp_path: Path) -> None:
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
    assert "AEAT session is expired" in result.output


def test_capture_filed_data_cli_refuses_expired_session_before_local_writes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
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
    assert "AEAT session is expired" in result.output
    assert not output_root.exists()


def test_capture_source_filed_data_refuses_expired_session_before_local_writes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )
    output_root = tmp_path / "captured-sources"

    with pytest.raises(typer.BadParameter, match="AEAT session is expired"):
        asyncio.run(
            capture_source_filed_data(
                modelo="180",
                year=2026,
                period="0A",
                output_root=output_root,
                registry_root=_REGISTRY_ROOT,
                source_root=PROJECT_ROOT,
            )
        )

    assert not output_root.exists()


def _modelo_130_filed_state_observations() -> tuple[FiledDeclarationObservation, FiledDeclarationObservation]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "130")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="1T")
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=_modelo_130_inputs(),
        date_context={"filing_period": datetime(2026, 3, 31, tzinfo=UTC).date()},
        binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("13000")},
    )
    primary_values = {**_modelo_130_inputs(), **calculation.values}
    return (
        _filed_observation(
            modelo="130",
            ejercicio=2026,
            period="1T",
            casilla_values=primary_values,
        ),
        _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={
                "0224": Decimal("3000"),
                "1479": Decimal("4000"),
                "1553": Decimal("2000"),
                "1577": Decimal("4000"),
            },
        ),
    )


def _modelo_130_inputs() -> dict[str, Decimal]:
    return {
        "01": Decimal("10000"),
        "02": Decimal("4000"),
        "05": Decimal("250"),
        "06": Decimal("100"),
        "08": Decimal("2000"),
        "10": Decimal("10"),
        "15": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }


def _filed_observation(
    *,
    modelo: str,
    ejercicio: int,
    period: str,
    casilla_values: dict[str, Decimal],
) -> FiledDeclarationObservation:
    return FiledDeclarationObservation(
        modelo=modelo,
        ejercicio=ejercicio,
        period=period,
        expediente_id=f"{ejercicio}{modelo}13522222A",
        status="ALTA",
        presented_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclarationArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
                content_type="application/octet-stream",
                byte_count=1,
                sha256="0" * 64,
                captured_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
            ),
        ),
        casillas=tuple(
            ObservedCasillaValue(
                casilla_id=casilla_id,
                value=str(value),
                source_artefact_kind="submitted_file",
                source_locator=f"field:{casilla_id}",
                confidence=1.0,
            )
            for casilla_id, value in casilla_values.items()
        ),
        extraction_coverage={"submitted_file": 1.0},
    )


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
