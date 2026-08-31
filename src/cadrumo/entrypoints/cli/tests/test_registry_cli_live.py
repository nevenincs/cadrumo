"""Live-read guard and filed-state registry CLI tests."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError
from typer.core import TyperGroup

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ....adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue
from ....application.live.errors import LiveIvaAcquisitionFailureMode
from ....application.live.filed_data import (
    FiledDataListingRow,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from ....application.live.filed_data_capture import (
    capture_source_filed_data,
    filed_data_capture_failure_row,
)
from ....application.live.remote_state_models import (
    IvaCompensationCarryForwardLotRow,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaWalletAuthorityDecisionRow,
    IvaWalletCaptureReport,
    LiveIvaReadStatus,
)
from ....application.registry.filed_state import verify_filed_state
from ....core import CasillaValueKind, IvaCompensationStateProvenance
from ....core.auth_provider import AuthProviderKind
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.access_gate import AeatLiveReadNotEnabledError
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from .. import _app_live
from .._app_live import (
    _filed_list_result_and_lines,
    _iva_wallet_history_lines,
    _iva_wallet_history_result,
    _iva_wallet_pull_lines,
)
from ._registry_cli_fixtures import (
    _isolated_registry_cli_backend,
    _isolated_secure_backend,
)
from ._registry_cli_support import (
    _ENGLISH_CLI_ENV,
    _REGISTRY_ROOT,
    _child,
    _command_path,
    _command_tree_paths,
    _first_registry_modelo,
    invoke_cached_cli,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_REGISTRY_CLI_FIXTURES = (_isolated_registry_cli_backend, _isolated_secure_backend)

_DECLARATIONS_LISTING_URL = aeat_url("www6", configured_path("sede_paths", "declarations_listing"))
_EXPIRED_LIVE_SESSION_REFERENCE = datetime(2026, 5, 28, 16, 0, tzinfo=UTC)
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")
_M100_SOURCE_0224_CASILLA: CasillaId = validated_casilla_id("0224", surface="_M100_SOURCE_0224_CASILLA")
_M100_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479", surface="_M100_SOURCE_1479_CASILLA")
_M100_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553", surface="_M100_SOURCE_1553_CASILLA")
_M100_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577", surface="_M100_SOURCE_1577_CASILLA")


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
    assert _M130_RESULTADO_FINAL_CASILLA in report.comparison.compared_casilla_ids
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
            str(_M130_RESULTADO_FINAL_CASILLA),
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.verify_filed_state"
    comparison = envelope["result"]["comparison"]
    assert comparison["status"] == "satisfied"
    assert comparison["modelo"] == "130"
    assert comparison["compared_casilla_ids"] == [str(_M130_RESULTADO_FINAL_CASILLA)]
    assert comparison["drifts"] == []


def test_verify_filed_state_cli_rejects_required_casilla_absent_from_revision(tmp_path: Path) -> None:
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
            "99999",
        ],
    )

    assert result.exit_code != 0
    assert "canonical casilla.id" in result.output
    assert "99999" in result.output


def test_verify_filed_state_reports_drift_from_encrypted_observation(tmp_path: Path) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "observations")
    primary, source = _modelo_130_filed_state_observations()
    casillas = tuple(
        item.model_copy(update={"value": str(Decimal(item.value) + Decimal("0.01"))})
        if item.casilla_id == _M130_RESULTADO_FINAL_CASILLA
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
        required_casilla_ids=(_M130_RESULTADO_FINAL_CASILLA,),
    )

    assert report.comparison.status == "failed"
    assert report.comparison.drifts[0].casilla_id == _M130_RESULTADO_FINAL_CASILLA
    assert report.comparison.drifts[0].delta == Decimal("-0.01")


def test_verify_filed_state_cli_help_resolves_locale_keys() -> None:
    result = invoke_cached_cli(
        ["app", "registry", "verify-filed-state", "--help"],
        env=_ENGLISH_CLI_ENV,
    )

    assert result.exit_code == 0
    assert "cli.registry.verify_filed_state_help" not in result.output
    assert "--source-observation" in result.output


def test_live_filed_capture_sources_cli_help_resolves_without_registry_alias() -> None:
    result = invoke_cached_cli(
        ["app", "live", "filed", "pull-sources", "--help"],
        env=_ENGLISH_CLI_ENV,
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
        env=_ENGLISH_CLI_ENV,
    )

    assert result.exit_code == 0
    assert "--year" in result.output
    assert "--from-year" in result.output
    assert "--to-year" in result.output
    assert "--modelo" in result.output

    filed_group = _command_path("app", "live", "filed")
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
        env=_ENGLISH_CLI_ENV,
    )

    assert result.exit_code == 0, result.output
    assert "mode=bulk" in result.output
    assert "failed_count=1" in result.output
    assert "pull-all" not in result.output


def test_live_notifications_latest_cli_help_resolves() -> None:
    result = invoke_cached_cli(
        ["app", "live", "notifications", "latest", "--help"],
        env=_ENGLISH_CLI_ENV,
    )

    assert result.exit_code == 0
    assert "latest" in result.output.lower()

    latest = _command_path("app", "live", "notifications", "latest")
    assert latest is not None
    assert hasattr(latest, "callback")


def test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all() -> None:
    result = invoke_cached_cli(
        ["app", "live", "expedientes", "pull", "--help"],
        env=_ENGLISH_CLI_ENV,
    )

    assert result.exit_code == 0
    assert "--year" in result.output
    assert "--from-year" in result.output
    assert "--to-year" in result.output
    assert "--modelo" in result.output

    expedientes_group = _command_path("app", "live", "expedientes")
    pull = _child(expedientes_group, "pull")
    assert pull is not None
    assert hasattr(pull, "callback")
    assert _child(expedientes_group, "pull-all") is None


def test_live_command_tree_rejects_pull_all_and_capture_all_aliases() -> None:
    live_group = _command_path("app", "live")
    assert isinstance(live_group, TyperGroup)

    paths = _command_tree_paths(live_group)
    disallowed = sorted(" ".join(("app", "live", *path)) for path in paths if path[-1] in {"capture-all", "pull-all"})

    assert not disallowed
    assert ("filed", "pull") in paths
    assert ("expedientes", "pull") in paths
    assert all("capture" not in exported for exported in _app_live.__all__ if exported.endswith("_cmd"))


def test_live_pull_help_locale_keys_do_not_use_capture_all_names() -> None:
    checked_paths = (
        Path("src/cadrumo/entrypoints/cli/_app_live.py"),
        Path("src/cadrumo/entrypoints/cli/_app_live_expedientes_cli.py"),
        Path("src/cadrumo/locales/en.yml"),
        Path("src/cadrumo/locales/es.yml"),
        Path("src/cadrumo/locales/ca.yml"),
        Path("src/cadrumo/locales/hu.yml"),
    )

    assert all("capture_all_modelo_help" not in path.read_text(encoding="utf-8") for path in checked_paths)


def test_live_iva_wallet_read_verbs_expose_help_without_leaking_internals() -> None:
    """Every iva-wallet read verb renders help, offers its axis, and leaks no internal term.

    This previously also asserted that the help NAMES the fail-closed
    no-submit policy, matching that prose in English or Spanish. Those
    assertions are RETIRED, and the property is currently unchecked.

    They were retired for two reasons. The help language is fixed when the
    Typer tree is built and the tree is cached, so an alternation only ever
    executed its Spanish half here -- which is how a misspelt Spanish
    alternative survived in it undetected. And matching operator prose to
    check a safety property is the shape the no-localized-prose discipline
    exists to prevent.

    The property is now checked structurally, surface-wide, rather than here:
    every exposed command must carry a risk ASSESSMENT and must declare no AEAT
    live write. The assessment half is what makes the claim falsifiable -- a
    live-write value of False holds for every command, so on its own it cannot
    tell a verb judged safe from one nobody has looked at.

    That check covers these five verbs along with the rest of the surface, in
    every language, which is strictly more than the retired prose assertion
    gave. What remains below is the operator-facing surface itself.

    What remains is language-independent: every read verb is wired and renders
    help, ``history`` offers the ``--as-of-year`` axis, and ``remote-state`` --
    an internal term absent from every locale catalogue, so it would leak
    verbatim -- stays out of operator help.
    """
    group = invoke_cached_cli(["app", "live", "iva-wallet", "--help"])
    pull = invoke_cached_cli(["app", "live", "iva-wallet", "pull", "--help"])
    capture_history = invoke_cached_cli(["app", "live", "iva-wallet", "pull-history", "--help"])
    history = invoke_cached_cli(["app", "live", "iva-wallet", "history", "--help"])
    pull_evidence = invoke_cached_cli(["app", "live", "iva-wallet", "pull-evidence", "--help"])

    assert group.exit_code == 0
    assert pull.exit_code == 0
    assert capture_history.exit_code == 0
    assert history.exit_code == 0
    assert pull_evidence.exit_code == 0
    assert "--as-of-year" in history.output
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
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                register_status="ALTA",
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
                reason_identity=IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED,
                operator_explanation=None,
                wallet_captured_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                decided_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
                authority_sources=("aeat_wallet amount=60.00 ref=wallet:2026:2T",),
            ),
        ),
    )

    lines = _iva_wallet_history_lines(report)
    result = _iva_wallet_history_result(report)

    assert "carry_forward_lot_count=1" in lines
    assert any(
        line.startswith("carry_forward_lot=")
        and "2022\t4T" in line
        and "remaining=60.00" in line
        and "expiry_review_state=expiry_review_due" in line
        for line in lines
    )
    assert any(
        line.startswith("authority_decision=")
        and "selected_authority=aeat_wallet" in line
        and "blocked=False" in line
        and "reason_identity=aeat_wallet_validated" in line
        and "reason=The latest valid AEAT wallet observation matches the local recurrence" in line
        and "wallet_captured_at=2026-05-21T12:00:00+00:00" in line
        and "decided_at=2026-05-21T12:00:00+00:00" in line
        for line in lines
    )
    assert any(line.startswith("authority_source=2026\t2T\taeat_wallet") for line in lines)
    payload_decision = result.authority_decisions[0]
    assert payload_decision.reason_identity == "aeat_wallet_validated"
    assert payload_decision.reason.startswith("The latest valid AEAT wallet observation matches")
    assert payload_decision.operator_explanation is None


def test_live_iva_wallet_history_payload_preserves_typed_periods() -> None:
    report = IvaCompensationHistoryReport(
        row_count=1,
        rows=(
            IvaCompensationHistoryRow(
                year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                register_status="ALTA",
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


def test_live_iva_auth_payload_preserves_only_a_redacted_diagnostic_reference() -> None:
    """A failed acquisition exposes correlation without disclosing diagnostic storage keys."""

    from .._app_live_iva_wallet_payloads import LiveIvaAuthOutcomePayload, LiveIvaSurfaceOutcomePayload

    accepted = LiveIvaAuthOutcomePayload(
        status=LiveIvaReadStatus.FAILED,
        outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
        failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
        failure_type="AuthError",
        diagnostic_ref="sha256:0123456789ab",
        provider_kind=None,
        reused_persisted_session=None,
        fresh=None,
    )
    assert accepted.diagnostic_ref == "sha256:0123456789ab"

    with pytest.raises(ValidationError):
        LiveIvaAuthOutcomePayload(
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_type="AuthError",
            diagnostic_ref="diagnostic-private-object-key",
            provider_kind=None,
            reused_persisted_session=None,
            fresh=None,
        )

    with pytest.raises(ValidationError):
        LiveIvaSurfaceOutcomePayload(
            surface="bogus",
            status=LiveIvaReadStatus.FAILED,
            outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_type="AuthError",
            failure_context=None,
            captured_count=None,
            calculation_observation_count=None,
        )


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


_LIVE_GATE_MODELO_ARG = "{modelo}"
_LIVE_GATE_OUTPUT_ROOT_ARG = "{output_root}"
_LIVE_GATE_CLI_CASES = (
    pytest.param(
        (
            "app",
            "live",
            "filed",
            "list",
            "--modelo",
            _LIVE_GATE_MODELO_ARG,
            "--from-year",
            "2024",
            "--to-year",
            "2025",
        ),
        None,
        id="filed-list",
    ),
    pytest.param(
        (
            "app",
            "live",
            "filed",
            "pull",
            "--modelo",
            _LIVE_GATE_MODELO_ARG,
            "--year",
            "2024",
            "--period",
            "1T",
            "--limit",
            "1",
            "--output-root",
            _LIVE_GATE_OUTPUT_ROOT_ARG,
        ),
        "captured",
        id="filed-pull",
    ),
    pytest.param(
        (
            "app",
            "live",
            "iva-wallet",
            "pull-history",
            "--from-year",
            "2024",
            "--to-year",
            "2025",
            "--output-root",
            _LIVE_GATE_OUTPUT_ROOT_ARG,
        ),
        "iva-history",
        id="iva-history-pull",
    ),
)


def _expired_live_session_env(tmp_path: Path) -> dict[str, str]:
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=_EXPIRED_LIVE_SESSION_REFERENCE - timedelta(hours=2),
        idle_deadline=_EXPIRED_LIVE_SESSION_REFERENCE - timedelta(minutes=1),
    )
    return {
        "CADRUMO_TOKEN_DIR": str(tmp_path),
        "CADRUMO_ACTIVE_PROFILE": "default",
        "CADRUMO_OUTPUT_LANGUAGE": "en",
    }


def _live_gate_cli_args(template: tuple[str, ...], *, output_root: Path | None) -> list[str]:
    args: list[str] = []
    for token in template:
        if token == _LIVE_GATE_MODELO_ARG:
            args.append(_first_registry_modelo())
        elif token == _LIVE_GATE_OUTPUT_ROOT_ARG:
            assert output_root is not None
            args.append(str(output_root))
        else:
            args.append(token)
    return args


@pytest.mark.parametrize(("args_template", "output_root_name"), _LIVE_GATE_CLI_CASES)
def test_live_cli_requires_live_gate_before_remote_read_or_local_writes(
    tmp_path: Path,
    args_template: tuple[str, ...],
    output_root_name: str | None,
) -> None:
    output_root = tmp_path / output_root_name if output_root_name is not None else None

    result = invoke_cached_cli(
        _live_gate_cli_args(args_template, output_root=output_root),
        env=_expired_live_session_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "live AEAT reads require CADRUMO_LIVE_TESTS_ENABLED" in result.output
    if output_root is not None:
        assert not output_root.exists()


def test_capture_source_filed_data_requires_live_gate_before_local_writes(tmp_path: Path) -> None:
    _seed_session(
        tmp_path,
        AuthProviderKind.CLAVE_MOVIL,
        authenticated_at=_EXPIRED_LIVE_SESSION_REFERENCE - timedelta(hours=2),
        idle_deadline=_EXPIRED_LIVE_SESSION_REFERENCE - timedelta(minutes=1),
    )
    output_root = tmp_path / "captured-sources"

    with pytest.raises(AeatLiveReadNotEnabledError, match=r"live AEAT reads require CADRUMO_LIVE_TESTS_ENABLED"):
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


@cache
def _modelo_130_filed_state_observations() -> tuple[FiledDeclaracionObservation, FiledDeclaracionObservation]:
    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
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
                _M100_SOURCE_0224_CASILLA: Decimal("3000"),
                _M100_SOURCE_1479_CASILLA: Decimal("4000"),
                _M100_SOURCE_1553_CASILLA: Decimal("2000"),
                _M100_SOURCE_1577_CASILLA: Decimal("4000"),
            },
        ),
    )


def _modelo_130_inputs() -> dict[CasillaId, Decimal]:
    return {
        _M130_INGRESOS_CASILLA: Decimal("10000"),
        _M130_GASTOS_CASILLA: Decimal("4000"),
        _M130_RETENCIONES_CASILLA: Decimal("100"),
        _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
        _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
        _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
        _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
    }


def _filed_observation(
    *,
    modelo: str,
    ejercicio: int,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
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
                value_kind=CasillaValueKind.NUMERIC,
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
