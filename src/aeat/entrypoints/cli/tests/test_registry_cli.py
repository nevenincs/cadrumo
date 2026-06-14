"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import typer
from pydantic import AnyHttpUrl
from typer.core import TyperGroup

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    ObservedCasillaValue,
)
from ....adapters.persistence.storage.master_key._active_session import activate_session
from ....adapters.persistence.storage.master_key._bucket_session import BucketSession
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.auth import AuthProviderKind
from ....application.live import (
    FiledDataListingRow,
    IvaCompensationCarryForwardLotRow,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaWalletAuthorityDecisionRow,
    IvaWalletCaptureReport,
    capture_source_filed_data,
    filed_data_capture_failure_row,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from ....application.registry import (
    RegistryTreeReport,
    verify_filed_state,
)
from ....core import Period
from ....core.access_gate import AeatLiveReadNotEnabledError
from ....core.config import override_settings
from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import calculate_registry_snapshot
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....tests.cli_runner import aeat_click_command
from ....tests.cli_runner import invoke_cached_cli as _invoke_cached_cli
from ....tests.secure_sql import dev_test_database_password, isolated_runtime_profile
from .. import _app_live
from .._app_live import (
    _filed_list_result_and_lines,
    _iva_wallet_history_lines,
    _iva_wallet_history_result,
    _iva_wallet_pull_lines,
)
from ..registry import _resolve_parity_store_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")
_BUCKET_ID = "registry-cli"
_DECLARATIONS_LISTING_URL = aeat_url("www6", configured_path("sede_paths", "declarations_listing"))
_CLI_ENV: dict[str, str] = {}


@pytest.fixture(scope="module", autouse=True)
def _isolated_registry_cli_backend(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    global _CLI_ENV
    tmp_path = tmp_path_factory.mktemp("registry-cli")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _CLI_ENV = {
            "AEAT_LOCAL_STORAGE_ROOT": str(runtime.storage_root),
            "AEAT_ACTIVE_PROFILE": runtime.bucket_id,
            "AEAT_SECRET_STORE_BACKEND": "file",
            "AEAT_SECRET_STORE_DIR": str(tmp_path / "secrets"),
            "AEAT_BLOB_STORE_DIR": str(tmp_path / "blobs"),
            "AEAT_AUDIT_DIR": str(tmp_path / "audit"),
            "AEAT_SECRET_PASSPHRASE": dev_test_database_password(runtime.settings),
            "AEAT_OUTPUT_LANGUAGE": "en",
        }
        yield
    _CLI_ENV = {}


def invoke_cached_cli(args, **kwargs):
    env = {**_CLI_ENV, **dict(kwargs.pop("env", {}) or {})}
    return _invoke_cached_cli(args, env=env, **kwargs)


def _child(group: object, name: str):
    """Resolve a subcommand from the AEAT command tree.

    ``aeat_click_command()`` returns an ``AeatTyperGroup`` whose MRO is
    ``TyperGroup -> typer._click.core.Command`` and never descends from the
    upstream :class:`click.Group`, so the parent is narrowed to
    :class:`typer.core.TyperGroup` (whose ``get_command`` is typed) rather
    than ``click.Group``. Intermediate nodes are themselves ``TyperGroup``
    instances and leaf nodes are vendored ``Command`` instances; the returned
    value carries the vendored ``Command | None`` type ``get_command``
    declares, exposing the ``help`` / ``callback`` surface the chain asserts.
    """
    assert isinstance(group, TyperGroup)
    return group.get_command(typer.Context(group), name)


def _command_tree_paths(group: TyperGroup, *, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    ctx = typer.Context(group)
    paths: set[tuple[str, ...]] = set()
    for name in group.list_commands(ctx):
        child = group.get_command(ctx, name)
        path = (*prefix, name)
        paths.add(path)
        if isinstance(child, TyperGroup):
            paths.update(_command_tree_paths(child, prefix=path))
    return paths


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


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
def _isolated_secure_backend(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Point encrypted SQL runtime at a per-test active bucket.

    The filed-state verification tests construct a
    :class:`FiledDeclaracionObservationStore`, which opens a
    runtime-routed secure-object repository. Registry-only tests are
    unaffected.
    """

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings,
        activate_session(_session()),
    ):
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


@pytest.fixture(scope="module")
def _registry_inspect_payload() -> RegistryTreeReport:
    """Run ``app registry inspect --format json`` once per module.

    Reused across every test_registry_inspect_* assertion so the CLI
    invocation (registry load + walk + payload synthesis) is paid
    once instead of per-assertion. Module scope is the correct
    bound: nothing in this file mutates the registry under
    ``_REGISTRY_ROOT``. Validating the emitted JSON back into
    ``RegistryTreeReport`` also asserts the CLI payload roundtrips
    against its declared schema.
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
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.inspect"
    return RegistryTreeReport.model_validate(envelope["result"])


def test_registry_inspect_cli_reports_unverified_state(_registry_inspect_payload: RegistryTreeReport) -> None:
    assert _registry_inspect_payload.verified is False


def test_registry_inspect_cli_lists_every_registry_modelo(_registry_inspect_payload: RegistryTreeReport) -> None:
    registry_modelos = _registry_modelos()
    assert _registry_inspect_payload.modelos == registry_modelos
    assert _registry_inspect_payload.modelo_count == len(registry_modelos)


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
    _registry_inspect_payload: RegistryTreeReport,
    count_key: str,
) -> None:
    count = getattr(_registry_inspect_payload, count_key)
    assert count > 0, f"{count_key}={count!r}"


def test_registry_inspect_cli_reports_at_least_one_revision(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert _registry_inspect_payload.revision_count >= 1


def test_registry_inspect_cli_advertises_expected_relation_role(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert "periodic_to_annual_summary" in _registry_inspect_payload.relation_dependency_roles


def test_registry_inspect_cli_matches_registry_application_surfaces(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert set(_registry_inspect_payload.application_link_surfaces) == _registry_application_surfaces()


def test_registry_inspect_cli_revision_details_match_revision_count(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert len(_registry_inspect_payload.revision_details) == _registry_inspect_payload.revision_count


def test_registry_inspect_cli_first_revision_resolves_against_modelo_list(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    assert revision.modelo in _registry_inspect_payload.modelos
    assert revision.revision


def test_registry_inspect_cli_first_revision_carries_legal_and_source_refs(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    assert revision.legal_refs
    assert revision.source_refs


_REVISION_COUNT_PAIRS = (
    ("export_layout_count", "export_layout_ids"),
    ("deadline_window_count", "deadline_periods"),
    ("relation_count", "relation_ids"),
    ("filing_schedule_count", "filing_schedule_ids"),
)


@pytest.mark.parametrize(("count_key", "ids_key"), _REVISION_COUNT_PAIRS)
def test_registry_inspect_cli_first_revision_count_matches_id_list(
    _registry_inspect_payload: RegistryTreeReport,
    count_key: str,
    ids_key: str,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    assert getattr(revision, count_key) == len(getattr(revision, ids_key))


def test_registry_inspect_cli_first_revision_has_workbook_parity(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert _registry_inspect_payload.revision_details[0].workbook_parity


def test_registry_inspect_cli_export_revision_has_record_and_field_counts(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    export_revision = next(
        detail for detail in _registry_inspect_payload.revision_details if detail.export_field_count > 0
    )
    assert export_revision.export_record_count > 0


def test_registry_inspect_cli_guarded_revision_lists_portal_guard_policies(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    guarded_revision = next(
        detail for detail in _registry_inspect_payload.revision_details if detail.portal_guard_policy_ids
    )
    assert guarded_revision.portal_guard_policy_ids


def test_registry_inspect_cli_workbook_reference_resolves_against_revision(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    workbook_reference = revision.workbook_parity[0]
    assert workbook_reference.id
    assert workbook_reference.workbook_source in revision.source_refs
    assert workbook_reference.formula_coverage
    assert workbook_reference.runner_required is False or workbook_reference.output_cell_count > 0


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

    assert result.exit_code == 0, f"CLI command failed:\n{result.output}"
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.verify"
    payload = envelope["result"]
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
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.workbooks.verify"
    payload = envelope["result"]
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
    assert "Backend exists=True" in result.output or "Backend existe=True" in result.output
    assert any(
        line == "Failed count=0" or (line.endswith("=0") and "fallid" in line.lower())
        for line in result.output.splitlines()
    )


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
    envelope = json.loads(second.output)
    assert envelope["command"] == "registry.workbooks.verify"
    payload = envelope["result"]
    assert payload["workbook_count"] >= 1
    assert payload["failed_count"] == 0


def test_registry_parity_default_store_root_comes_from_settings(tmp_path: Path) -> None:
    configured_root = tmp_path / "configured-parity"
    explicit_root = tmp_path / "explicit-parity"

    with override_settings(aeat_registry_parity_store_dir=configured_root):
        assert _resolve_parity_store_root(None) == configured_root
        assert _resolve_parity_store_root(explicit_root) == explicit_root


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
    assert (
        "output format is not supported" in result.output
        or "formato de salida solicitado no es compatible" in result.output
    )
    assert "unexpected internal error" not in result.output.lower()


def test_capture_selector_filters_register_rows_by_period_and_expediente() -> None:
    rows = (
        _declaration(expediente_id="202610013522222A", period="1T"),
        _declaration(expediente_id="202620013522222B", period="2T"),
    )

    selected = select_declarations_for_capture(
        rows,
        period=Period.from_year_and_code(2026, "2T"),
        expediente_id="202620013522222B",
    )

    assert selected == (rows[1],)


def test_filed_data_listing_row_reports_available_read_surfaces() -> None:
    modelo = _first_registry_modelo()
    row = _declaration(expediente_id="202511113520436S", period="1T", modelo=modelo).model_copy(
        update={
            "ejercicio": 2025,
            "period": Period.from_year_and_code(2025, "1T"),
            "declaration_copy_link_text": None,
            "declaration_copy_cell_index": None,
        },
    )

    listed = filed_data_listing_row(row)

    assert listed.modelo == modelo
    assert listed.year == 2025
    assert listed.period == Period.from_year_and_code(2025, "1T")
    assert listed.expediente_id == "202511113520436S"
    assert listed.has_submitted_file is True
    assert listed.has_justificante is True
    assert listed.has_declaration_copy is False


def test_verify_filed_state_compares_local_calculation_to_encrypted_observation(tmp_path: Path) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "observations")
    primary, source = _modelo_130_filed_state_observations()
    primary_path = store.persist_observation(primary)
    source_path = store.persist_observation(source)

    report = verify_filed_state(
        observation_path=primary_path,
        source_observation_paths=(source_path,),
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
    )

    assert report.comparison.status == "satisfied"
    assert report.comparison.modelo == "130"
    assert "19" in report.comparison.compared_casillas
    assert report.comparison.drifts == ()


def test_verify_filed_state_cli_loads_secure_observation_refs(tmp_path: Path) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "observations")
    primary, source = _modelo_130_filed_state_observations()
    primary_path = store.persist_observation(primary)
    source_path = store.persist_observation(source)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "registry",
            "verify-filed-state",
            "--observation",
            str(primary_path),
            "--source-observation",
            str(source_path),
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--source-root",
            str(bundled_path()),
            "--casilla",
            "19",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.verify_filed_state"
    comparison = envelope["result"]["comparison"]
    assert comparison["status"] == "satisfied"
    assert comparison["modelo"] == "130"
    assert comparison["compared_casillas"] == ["19"]
    assert comparison["drifts"] == []


def test_verify_filed_state_reports_drift_from_encrypted_observation(tmp_path: Path) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "observations")
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
        ["app", "live", "filed", "pull-sources", "--help"],
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


def test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all() -> None:
    result = invoke_cached_cli(
        ["app", "live", "filed", "pull", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    assert "--year" in result.output
    assert "--from-year" in result.output
    assert "--to-year" in result.output
    assert "--modelo" in result.output

    root = aeat_click_command()
    app_group = _child(root, "app")
    assert app_group is not None
    live_group = _child(app_group, "live")
    assert live_group is not None
    filed_group = _child(live_group, "filed")
    assert filed_group is not None
    pull = _child(filed_group, "pull")
    assert pull is not None
    assert _child(filed_group, "pull-all") is None


def test_live_filed_bulk_pull_accepts_limit_without_pull_all() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "live",
            "filed",
            "pull",
            "--modelo",
            "151",
            "--from-year",
            "2024",
            "--to-year",
            "2024",
            "--limit",
            "10",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0, result.output
    assert "mode=bulk" in result.output
    assert "failed_count=1" in result.output
    assert "pull-all" not in result.output


def test_live_notifications_latest_cli_help_resolves() -> None:
    result = invoke_cached_cli(
        ["app", "live", "notifications", "latest", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    assert "latest" in result.output.lower()

    root = aeat_click_command()
    app_group = _child(root, "app")
    assert app_group is not None
    live_group = _child(app_group, "live")
    assert live_group is not None
    notifications_group = _child(live_group, "notifications")
    assert notifications_group is not None
    latest = _child(notifications_group, "latest")
    assert latest is not None
    assert hasattr(latest, "callback")


def test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all() -> None:
    result = invoke_cached_cli(
        ["app", "live", "expedientes", "pull", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code == 0
    assert "--year" in result.output
    assert "--from-year" in result.output
    assert "--to-year" in result.output
    assert "--modelo" in result.output

    root = aeat_click_command()
    app_group = _child(root, "app")
    assert app_group is not None
    live_group = _child(app_group, "live")
    assert live_group is not None
    expedientes_group = _child(live_group, "expedientes")
    assert expedientes_group is not None
    pull = _child(expedientes_group, "pull")
    assert pull is not None
    assert hasattr(pull, "callback")
    assert _child(expedientes_group, "pull-all") is None


def test_live_command_tree_rejects_pull_all_and_capture_all_aliases() -> None:
    root = aeat_click_command()
    app_group = _child(root, "app")
    assert app_group is not None
    live_group = _child(app_group, "live")
    assert isinstance(live_group, TyperGroup)

    paths = _command_tree_paths(live_group)
    disallowed = sorted(" ".join(("app", "live", *path)) for path in paths if path[-1] in {"capture-all", "pull-all"})

    assert not disallowed
    assert ("filed", "pull") in paths
    assert ("expedientes", "pull") in paths
    assert all("capture" not in exported for exported in _app_live.__all__ if exported.endswith("_cmd"))


def test_live_pull_help_locale_keys_do_not_use_capture_all_names() -> None:
    checked_paths = (
        Path("src/aeat/entrypoints/cli/_app_live.py"),
        Path("src/aeat/entrypoints/cli/_app_live_expedientes_cli.py"),
        Path("src/aeat/locales/en.yml"),
        Path("src/aeat/locales/es.yml"),
        Path("src/aeat/locales/ca.yml"),
        Path("src/aeat/locales/hu.yml"),
    )

    assert all("capture_all_modelo_help" not in path.read_text(encoding="utf-8") for path in checked_paths)


def test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy() -> None:
    group = invoke_cached_cli(
        ["app", "live", "iva-wallet", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    pull = invoke_cached_cli(
        ["app", "live", "iva-wallet", "pull", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    capture_history = invoke_cached_cli(
        ["app", "live", "iva-wallet", "pull-history", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    history = invoke_cached_cli(
        ["app", "live", "iva-wallet", "history", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    pull_evidence = invoke_cached_cli(
        ["app", "live", "iva-wallet", "pull-evidence", "--help"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert group.exit_code == 0
    assert pull.exit_code == 0
    assert capture_history.exit_code == 0
    assert history.exit_code == 0
    assert pull_evidence.exit_code == 0
    assert "read-only" in group.output or "solo lectura" in group.output
    assert "read query" in pull.output or "lectura" in pull.output
    assert "own-name" in pull.output or "nombre propio" in pull.output
    assert (
        "No AEAT filing or wallet form choices are submitted" in capture_history.output
        or "No se envia ninguna declaracion" in capture_history.output
    )
    assert "--as-of-year" in history.output
    assert "read-only" in pull_evidence.output or "solo lectura" in pull_evidence.output
    assert "acquisition" in pull_evidence.output or "adquisicion" in pull_evidence.output
    assert "remote-state" not in pull_evidence.output.lower()


def test_live_iva_wallet_pull_evidence_resolves_target_period_before_backend(tmp_path: Path) -> None:
    result = invoke_cached_cli(
        [
            "app",
            "live",
            "iva-wallet",
            "pull-evidence",
            "--from-year",
            "2026",
            "--to-year",
            "2026",
            "--target-year",
            "2026",
            "--target-period",
            "2T",
            "--output-root",
            str(tmp_path / "iva-evidence"),
        ],
    )

    assert result.exit_code != 0
    assert "AttributeError" not in result.output
    assert "filing_year" not in result.output
    assert "auth_preflight" in result.output


def test_live_iva_wallet_pull_output_lines_name_guarded_read_query_policy() -> None:
    report = IvaWalletCaptureReport(
        taxpayer_ref="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        observation_path="secure://wallet-observation",
        decision_key="iva-wallet-decision:12345678Z:2026:2T",
        row_count=1,
        total_pending="1200.00",
        selected_authority="aeat_wallet",
        selected_amount="1200.00",
        local_recurrence_amount="1200.00",
        divergence="match",
        blocked=False,
        captured_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
    )

    lines = _iva_wallet_pull_lines(report)

    assert "safety_policy=read_only_fail_closed" in lines
    assert "representation_gate_policy=own_name_only_no_represented_taxpayer_choice" in lines
    assert "aeat_form_submission_policy=wallet_execute_read_query_only_no_filing_or_represented_taxpayer_data" in lines
    assert "selected_authority=aeat_wallet" in lines


def test_live_iva_wallet_history_output_lines_surface_lots_and_authority_decisions() -> None:
    report = IvaCompensationHistoryReport(
        row_count=1,
        rows=(
            IvaCompensationHistoryRow(
                year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                status="ALTA",
                presented_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                prior_pending_amount="100.00",
                applied_amount="40.00",
                pending_for_later_amount="60.00",
                period_result_amount="0.00",
                final_result_amount="0.00",
                generated_amount="0",
                available_end_amount="60.00",
            ),
        ),
        as_of_year=2026,
        carry_forward_lot_count=1,
        carry_forward_lots=(
            IvaCompensationCarryForwardLotRow(
                taxpayer_ref="sha256:abc123",
                source_filing_year=2022,
                source_period=Period.from_year_and_code(2022, "4T"),
                generated_amount="100.00",
                applied_amount="40.00",
                remaining_amount="60.00",
                age_years=4,
                expiry_review_state="expiry_review_due",
                source_observation_key="303:2022:4T:EXP",
            ),
        ),
        unallocated_applied_amount="0",
        authority_decision_count=1,
        authority_decisions=(
            IvaWalletAuthorityDecisionRow(
                taxpayer_ref="sha256:abc123",
                target_year=2026,
                target_period=Period.from_year_and_code(2026, "2T"),
                selected_authority="aeat_wallet",
                selected_amount="60.00",
                wallet_amount="60.00",
                local_recurrence_amount="60.00",
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason="matched",
                wallet_captured_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                decided_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                authority_sources=("aeat_wallet amount=60.00 ref=wallet:2026:2T",),
            ),
        ),
    )

    lines = _iva_wallet_history_lines(report)

    assert "carry_forward_lot_count=1" in lines
    assert any(
        line.startswith("carry_forward_lot=")
        and "2022\t4T" in line
        and "remaining=60.00" in line
        and "expiry_review_state=expiry_review_due" in line
        for line in lines
    )
    assert any(
        line.startswith("authority_decision=") and "selected_authority=aeat_wallet" in line and "blocked=False" in line
        for line in lines
    )
    assert any(line.startswith("authority_source=2026\t2T\taeat_wallet") for line in lines)


def test_live_iva_wallet_history_payload_preserves_typed_periods() -> None:
    report = IvaCompensationHistoryReport(
        row_count=1,
        rows=(
            IvaCompensationHistoryRow(
                year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                status="ALTA",
                presented_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                prior_pending_amount="100.00",
                applied_amount="0.00",
                pending_for_later_amount="100.00",
                period_result_amount="0.00",
                final_result_amount="0.00",
                generated_amount="100.00",
                available_end_amount="100.00",
            ),
        ),
        as_of_year=2026,
        carry_forward_lot_count=0,
        unallocated_applied_amount="0",
        authority_decision_count=0,
    )

    payload = _iva_wallet_history_result(report)

    assert payload.rows[0].period == Period.from_year_and_code(2024, "1T")


def test_live_filed_list_payload_and_text_use_registry_period_tokens() -> None:
    row = FiledDataListingRow(
        modelo="303",
        year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202610013522222A",
        status="ALTA",
        presented_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
        has_submitted_file=True,
        has_declaration_copy=False,
        has_justificante=True,
    )
    failure = filed_data_capture_failure_row(
        modelo="303",
        year=2026,
        error=ValueError("period-token-smoke"),
        declaration=_declaration(expediente_id="202620013522222B", period="2T", modelo="303"),
    )

    payload, lines = _filed_list_result_and_lines(
        modelo_filter=None,
        year_from=2026,
        year_to=2026,
        row_count=1,
        rows=(row,),
        failures=(failure,),
    )

    assert payload.rows[0].period == "1T"
    assert payload.failures[0].period == "2T"
    assert any(line.startswith("row=303\t2026\t1T\t") for line in lines)
    assert any(line.startswith("failure=303\t2026\t2T\t") for line in lines)
    assert all("2026 1T" not in line and "2026 2T" not in line for line in lines)


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
    assert "live AEAT reads require AEAT_LIVE_TESTS_ENABLED" in result.output


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
            "pull",
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
    assert "live AEAT reads require AEAT_LIVE_TESTS_ENABLED" in result.output
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
            "pull-history",
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
    assert "live AEAT reads require AEAT_LIVE_TESTS_ENABLED" in result.output
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

    with pytest.raises(AeatLiveReadNotEnabledError, match=r"live AEAT reads require AEAT_LIVE_TESTS_ENABLED"):
        asyncio.run(
            capture_source_filed_data(
                modelo="180",
                year=2026,
                period=Period.from_year_and_code(2026, "0A"),
                output_root=output_root,
                registry_root=_REGISTRY_ROOT,
                source_root=bundled_path(),
            ),
        )

    assert not output_root.exists()


def _modelo_130_filed_state_observations() -> tuple[FiledDeclaracionObservation, FiledDeclaracionObservation]:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=_modelo_130_inputs(),
        date_context={"filing_period": datetime(2026, 3, 31, tzinfo=UTC).date()},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
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
        period=Period.from_year_and_code(ejercicio, period),
        expediente_id=f"{ejercicio}{modelo}13522222A",
        status="ALTA",
        presented_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
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
        period=Period.from_year_and_code(2026, period),
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
