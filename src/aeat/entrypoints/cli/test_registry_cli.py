"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from aeat.adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    ObservedCasillaValue,
)
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.application.auth import AuthProviderKind
from aeat.application.live import (
    capture_source_filed_data,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from aeat.application.registry import (
    verify_filed_state,
)
from aeat.core.access_gate import AeatLiveReadNotEnabledError
from aeat.core.resources import bundled_path, resources
from aeat.domain.calculations.registry import calculate_registry_snapshot
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")


def _registry_modelos() -> tuple[str, ...]:
    return tuple(sorted(modelo.id for modelo in resources().modelos.all()))


def _registry_application_surfaces() -> set[str]:
    return {
        link.surface
        for modelo in resources().modelos.all()
        for revision in modelo.revisions.values()
        for link in revision.application_links
    }


def _first_registry_modelo() -> str:
    return _registry_modelos()[0]


@pytest.fixture(autouse=True)
def _isolated_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the encrypted SQL engine at a per-test SQLite database.

    The filed-state verification tests construct a
    :class:`FiledDeclaracionObservationStore`, which opens a
    :class:`SecureObjectRepository` and therefore needs a resolvable
    ``aeat_database_url``. Registry-only tests are unaffected.
    """

    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'registry-cli.db').as_posix()}")
    dispose_engine()


@pytest.fixture(scope="module")
def _registry_inspect_payload() -> dict[str, object]:
    """Run ``app registry inspect --format json`` once per module.

    Reused across every test_registry_inspect_* assertion so the CLI
    invocation (registry load + walk + payload synthesis) is paid
    once instead of per-assertion. Module scope is the correct
    bound: nothing in this file mutates the registry under
    ``_REGISTRY_ROOT``.
    """
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_registry_inspect_cli_reports_unverified_state(_registry_inspect_payload: dict[str, object]) -> None:
    assert _registry_inspect_payload["verified"] is False


def test_registry_inspect_cli_lists_every_registry_modelo(_registry_inspect_payload: dict[str, object]) -> None:
    registry_modelos = _registry_modelos()
    assert _registry_inspect_payload["modelos"] == list(registry_modelos)
    assert _registry_inspect_payload["modelo_count"] == len(registry_modelos)


_INSPECT_PAYLOAD_NON_ZERO_COUNT_KEYS = (
    "casilla_count",
    "formula_count",
    "extraction_profile_count",
    "cross_reference_count",
    "workbook_parity_ref_count",
    "verification_expectation_count",
    "application_link_count",
    "relation_count",
    "filing_schedule_count",
)


@pytest.mark.parametrize("count_key", _INSPECT_PAYLOAD_NON_ZERO_COUNT_KEYS)
def test_registry_inspect_cli_reports_non_zero_count(
    _registry_inspect_payload: dict[str, object], count_key: str
) -> None:
    assert _registry_inspect_payload[count_key] > 0, f"{count_key}={_registry_inspect_payload[count_key]!r}"


def test_registry_inspect_cli_reports_at_least_one_revision(
    _registry_inspect_payload: dict[str, object],
) -> None:
    assert _registry_inspect_payload["revision_count"] >= 1


def test_registry_inspect_cli_advertises_expected_relation_role(
    _registry_inspect_payload: dict[str, object],
) -> None:
    assert "periodic_to_annual_summary" in _registry_inspect_payload["relation_dependency_roles"]


def test_registry_inspect_cli_matches_registry_application_surfaces(
    _registry_inspect_payload: dict[str, object],
) -> None:
    assert set(_registry_inspect_payload["application_link_surfaces"]) == _registry_application_surfaces()


def test_registry_inspect_cli_revision_details_match_revision_count(
    _registry_inspect_payload: dict[str, object],
) -> None:
    assert len(_registry_inspect_payload["revision_details"]) == _registry_inspect_payload["revision_count"]


def test_registry_inspect_cli_first_revision_resolves_against_modelo_list(
    _registry_inspect_payload: dict[str, object],
) -> None:
    revision = _registry_inspect_payload["revision_details"][0]
    assert revision["modelo"] in _registry_inspect_payload["modelos"]
    assert revision["revision"]


def test_registry_inspect_cli_first_revision_carries_legal_and_source_refs(
    _registry_inspect_payload: dict[str, object],
) -> None:
    revision = _registry_inspect_payload["revision_details"][0]
    assert revision["legal_refs"]
    assert revision["source_refs"]


_REVISION_COUNT_PAIRS = (
    ("export_layout_count", "export_layout_ids"),
    ("deadline_window_count", "deadline_periods"),
    ("relation_count", "relation_ids"),
    ("filing_schedule_count", "filing_schedule_ids"),
)


@pytest.mark.parametrize(("count_key", "ids_key"), _REVISION_COUNT_PAIRS)
def test_registry_inspect_cli_first_revision_count_matches_id_list(
    _registry_inspect_payload: dict[str, object], count_key: str, ids_key: str
) -> None:
    revision = _registry_inspect_payload["revision_details"][0]
    assert revision[count_key] == len(revision[ids_key])


def test_registry_inspect_cli_first_revision_has_workbook_parity(
    _registry_inspect_payload: dict[str, object],
) -> None:
    assert _registry_inspect_payload["revision_details"][0]["workbook_parity"]


def test_registry_inspect_cli_export_revision_has_record_and_field_counts(
    _registry_inspect_payload: dict[str, object],
) -> None:
    export_revision = next(
        detail for detail in _registry_inspect_payload["revision_details"] if detail["export_field_count"] > 0
    )
    assert export_revision["export_record_count"] > 0


def test_registry_inspect_cli_guarded_revision_lists_portal_guard_policies(
    _registry_inspect_payload: dict[str, object],
) -> None:
    guarded_revision = next(
        detail for detail in _registry_inspect_payload["revision_details"] if detail["portal_guard_policy_ids"]
    )
    assert guarded_revision["portal_guard_policy_ids"]


def test_registry_inspect_cli_workbook_reference_resolves_against_revision(
    _registry_inspect_payload: dict[str, object],
) -> None:
    revision = _registry_inspect_payload["revision_details"][0]
    workbook_reference = revision["workbook_parity"][0]
    assert workbook_reference["id"]
    assert workbook_reference["workbook_source"] in revision["source_refs"]
    assert workbook_reference["formula_coverage"]
    assert workbook_reference["runner_required"] is False or workbook_reference["output_cell_count"] > 0


def test_registry_verify_cli_validates_sources_and_catalogues() -> None:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--source-root",
            str(bundled_path()),
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
    result = invoke_cached_cli(
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
    assert "missing corpus file" in result.output


def test_registry_workbook_verify_cli_reports_json_from_official_corpus() -> None:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
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
    payload = json.loads(result.output)
    assert payload["workbook_count"] >= 1
    assert payload["scanned_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["runner"]["status"] == "available"
    assert payload["modelo_coverage"][0]["modelo"]


def test_registry_workbook_verify_cli_reports_text_from_official_corpus() -> None:
    result = invoke_cached_cli(
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
    assert "Backend exists=True" in result.output
    assert "Failed count=0" in result.output


def test_registry_workbook_verify_cli_writes_json_report_from_official_corpus(tmp_path) -> None:
    output = tmp_path / "reports" / "workbooks.json"

    result = invoke_cached_cli(
        [
            "--format",
            "json",
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
    first = invoke_cached_cli(
        [
            "--format",
            "json",
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

    second = invoke_cached_cli(
        [
            "--format",
            "json",
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
        ],
    )

    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload["workbook_count"] >= 1
    assert payload["failed_count"] == 0


def test_registry_retained_commands_reject_command_local_json_flag() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_registry_commands_refuse_unsupported_root_output_format() -> None:
    result = invoke_cached_cli(
        [
            "--format",
            "xml",
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
        ],
    )

    assert result.exit_code == 2
    assert "Refused." in result.output
    assert "unsupported output format" in result.output
    assert "unexpected internal error" not in result.output.lower()


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

    listed = filed_data_listing_row(row)

    assert listed.modelo == modelo
    assert listed.year == 2025
    assert listed.period == "1T"
    assert listed.expediente_id == "202511113520436S"
    assert listed.has_submitted_file is True
    assert listed.has_justificante is True
    assert listed.has_declaration_copy is False


def test_verify_filed_state_compares_local_calculation_to_encrypted_observation(tmp_path: Path) -> None:
    provider = EphemeralMasterKeyProvider()
    store = FiledDeclaracionObservationStore(tmp_path / "observations", master_key_provider=provider)
    primary, source = _modelo_130_filed_state_observations()
    primary_path = store.persist_observation(primary)
    source_path = store.persist_observation(source)

    report = verify_filed_state(
        observation_path=primary_path,
        source_observation_paths=(source_path,),
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
        master_key_provider=provider,
    )

    assert report.comparison.status == "satisfied"
    assert report.comparison.modelo == "130"
    assert "19" in report.comparison.compared_casillas
    assert report.comparison.drifts == ()


def test_verify_filed_state_reports_drift_from_encrypted_observation(tmp_path: Path) -> None:
    provider = EphemeralMasterKeyProvider()
    store = FiledDeclaracionObservationStore(tmp_path / "observations", master_key_provider=provider)
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
        source_root=bundled_path(),
        required_casillas=("19",),
        master_key_provider=provider,
    )

    assert report.comparison.status == "failed"
    assert report.comparison.drifts[0].casilla_id == "19"
    assert report.comparison.drifts[0].delta == Decimal("-0.01")


def test_verify_filed_state_cli_help_resolves_locale_keys() -> None:
    result = invoke_cached_cli(
        ["app", "registry", "verify-filed-state", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    # The dot-notated translation key must not leak into operator output —
    # its presence would mean ``tr()`` returned the key path unresolved.
    assert "cli.registry.verify_filed_state_help" not in result.output
    # Option flags are CLI surface, not translated, and must be present.
    assert "--source-observation" in result.output


def test_live_filed_capture_sources_cli_help_resolves_without_registry_alias() -> None:
    result = invoke_cached_cli(
        ["app", "live", "filed", "capture-sources", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    assert "--source-root" in result.output

    old = invoke_cached_cli(["app", "registry", "capture-source-filed-data", "--help"])
    assert old.exit_code != 0
    assert "No such command" in old.output

    old_list = invoke_cached_cli(["app", "registry", "list-filed-data", "--help"])
    old_capture = invoke_cached_cli(["app", "registry", "capture-filed-data", "--help"])
    assert old_list.exit_code != 0
    assert old_capture.exit_code != 0
    assert "No such command" in old_list.output
    assert "No such command" in old_capture.output


def test_list_filed_data_cli_requires_live_gate_before_remote_read(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )

    result = invoke_cached_cli(
        [
            "app",
            "live",
            "filed",
            "list",
            "--modelo",
            _first_registry_modelo(),
            "--from-year",
            "2024",
            "--to-year",
            "2025",
        ],
        env={
            "AEAT_TOKEN_DIR": str(tmp_path),
            "AEAT_ACTIVE_PROFILE": "default",
            "AEAT_OUTPUT_LANGUAGE": "en",
        },
    )

    assert result.exit_code != 0
    assert "live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1" in result.output


def test_capture_filed_data_cli_requires_live_gate_before_local_writes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )
    output_root = tmp_path / "captured"

    result = invoke_cached_cli(
        [
            "app",
            "live",
            "filed",
            "capture",
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
            "AEAT_ACTIVE_PROFILE": "default",
            "AEAT_OUTPUT_LANGUAGE": "en",
        },
    )

    assert result.exit_code != 0
    assert "live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1" in result.output
    assert not output_root.exists()


def test_capture_iva_history_cli_requires_live_gate_before_local_writes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )
    output_root = tmp_path / "iva-history"

    result = invoke_cached_cli(
        [
            "app",
            "live",
            "iva-wallet",
            "capture-history",
            "--from-year",
            "2024",
            "--to-year",
            "2025",
            "--output-root",
            str(output_root),
        ],
        env={
            "AEAT_TOKEN_DIR": str(tmp_path),
            "AEAT_ACTIVE_PROFILE": "default",
            "AEAT_OUTPUT_LANGUAGE": "en",
        },
    )

    assert result.exit_code != 0
    assert "live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1" in result.output
    assert not output_root.exists()


def test_capture_source_filed_data_requires_live_gate_before_local_writes(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=now - timedelta(hours=2),
        idle_deadline=now - timedelta(minutes=1),
    )
    output_root = tmp_path / "captured-sources"

    with pytest.raises(AeatLiveReadNotEnabledError, match="live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1"):
        asyncio.run(
            capture_source_filed_data(
                modelo="180",
                year=2026,
                period="0A",
                output_root=output_root,
                registry_root=_REGISTRY_ROOT,
                source_root=bundled_path(),
            )
        )

    assert not output_root.exists()


def _modelo_130_filed_state_observations() -> tuple[FiledDeclaracionObservation, FiledDeclaracionObservation]:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
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
) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo=modelo,
        ejercicio=ejercicio,
        period=period,
        expediente_id=f"{ejercicio}{modelo}13522222A",
        status="ALTA",
        presented_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclaracionArtefact(
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


def _declaration(*, expediente_id: str, period: str, modelo: str | None = None) -> Declaracion:
    return Declaracion(
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
