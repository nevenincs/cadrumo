"""Combined IVA remote-state acquisition report tests."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright._impl._errors import TargetClosedError

from aeat.adapters.outbound.aeat.auth import ClaveMovilApprovalTimeoutError
from aeat.adapters.outbound.aeat.sede import SedeFailureMode, SedeNavigationError
from aeat.adapters.persistence.storage import LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE
from aeat.adapters.persistence.storage.errors import StorageValidationError
from aeat.application.auth import AuthenticatedAeatSessionResult, AuthProviderKind
from aeat.tests.secure_sql import isolated_runtime_profile, isolated_sessionless_storage_root

from . import (
    IvaCompensationHistoryCaptureReport,
    IvaRemoteStateAcquisitionManifest,
    IvaRemoteStateAcquisitionReport,
    LiveIvaAcquisitionFailureMode,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
    LiveIvaSurfaceTimeoutError,
    _await_live_iva_surface,
    _suppress_live_iva_playwright_cancellation_noise,
    build_iva_remote_state_acquisition_report,
    classify_live_iva_acquisition_failure,
    list_iva_remote_state_acquisition_manifests,
    load_iva_remote_state,
    load_iva_remote_state_acquisition_manifest,
    persist_iva_remote_state_acquisition_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CAPTURED_AT = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def test_combined_acquisition_records_authenticated_success_outcome(tmp_path: Path) -> None:
    auth_result = AuthenticatedAeatSessionResult(
        provider_kind=AuthProviderKind.CLAVE_MOVIL,
        session=object(),
        assertion=object(),
        reused_persisted_session=True,
        fresh=False,
    )
    filed_history = IvaCompensationHistoryCaptureReport(
        output_root=str(tmp_path / "filed-history"),
        year_from=2022,
        year_to=2024,
        captured_count=12,
        observation_paths=("observations/303-2022-1T.json",),
        artefact_refs=("secure-object:artefact",),
        casilla_count=948,
        calculation_observation_count=12,
        calculation_observation_keys=("303:2022:1T",),
        reloaded_history_count=12,
        reloaded_rows=(),
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2022,
        year_to=2024,
        target_year=2026,
        target_period="2T",
        auth_result=auth_result,
        filed_history=filed_history,
    )

    assert report.auth.status is LiveIvaReadStatus.SUCCEEDED
    assert report.auth.outcome_mode is LiveIvaAcquisitionFailureMode.AUTHENTICATED
    assert report.auth.provider_kind == AuthProviderKind.CLAVE_MOVIL.value
    assert report.auth.reused_persisted_session is True
    filed_outcome, wallet_outcome = report.outcomes
    assert filed_outcome.status is LiveIvaReadStatus.SUCCEEDED
    assert filed_outcome.outcome_mode is LiveIvaAcquisitionFailureMode.AUTHENTICATED
    assert wallet_outcome.failure_type == "MissingSurfaceReport"


def test_auth_failure_blocks_surface_outcomes_with_typed_mode(tmp_path: Path) -> None:
    diagnostic_id = "clave-diagnostic-private-object-key"
    auth_error = ClaveMovilApprovalTimeoutError(
        "operator reported no prompt",
        failure_mode="auth_completion_timeout",
        context={
            "phone_state": "app_did_not_prompt",
            "auth_mode": "non_qr",
            "diagnostic_id": diagnostic_id,
        },
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2024,
        year_to=2024,
        target_year=2026,
        target_period="1T",
        auth_error=auth_error,
    )

    assert report.auth.status is LiveIvaReadStatus.FAILED
    assert report.filed_history_succeeded is False
    assert report.wallet_succeeded is False
    assert report.auth.failure_mode is LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT
    assert report.auth.outcome_mode is not LiveIvaAcquisitionFailureMode.AUTHENTICATED
    assert report.auth.outcome_mode is not LiveIvaAcquisitionFailureMode.UNKNOWN
    assert report.auth.diagnostic_ref is not None
    assert report.auth.diagnostic_ref.startswith("sha256:")
    assert diagnostic_id not in report.model_dump_json()
    assert tuple(outcome.failure_mode for outcome in report.outcomes) == (
        LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
        LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
    )
    assert tuple(outcome.failure_type for outcome in report.outcomes) == (
        "ClaveMovilApprovalTimeoutError",
        "ClaveMovilApprovalTimeoutError",
    )
    assert all(outcome.status is LiveIvaReadStatus.FAILED for outcome in report.outcomes)
    assert all(outcome.outcome_mode is LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT for outcome in report.outcomes)


def test_combined_acquisition_preserves_filed_history_when_wallet_auth_gate_fails(tmp_path: Path) -> None:
    filed_history = IvaCompensationHistoryCaptureReport(
        output_root=str(tmp_path / "filed-history"),
        year_from=2022,
        year_to=2024,
        captured_count=12,
        observation_paths=("observations/303-2022-1T.json",),
        artefact_refs=("secure-object:artefact",),
        casilla_count=948,
        calculation_observation_count=12,
        calculation_observation_keys=("303:2022:1T",),
        reloaded_history_count=12,
        reloaded_rows=(),
    )
    wallet_error = SedeNavigationError(
        "AEAT wallet auth gate",
        failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
        context={"captured_at": _CAPTURED_AT.isoformat()},
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2022,
        year_to=2024,
        target_year=2026,
        target_period="2T",
        filed_history=filed_history,
        wallet_error=wallet_error,
    )

    assert isinstance(report, IvaRemoteStateAcquisitionReport)
    assert report.filed_history_succeeded is True
    assert report.wallet_succeeded is False
    assert report.filed_history is filed_history
    assert report.wallet is None
    filed_outcome, wallet_outcome = report.outcomes
    assert filed_outcome.surface is LiveIvaReadSurface.FILED_HISTORY
    assert filed_outcome.status is LiveIvaReadStatus.SUCCEEDED
    assert filed_outcome.captured_count == 12
    assert filed_outcome.calculation_observation_count == 12
    assert wallet_outcome.surface is LiveIvaReadSurface.WALLET_CARTERA
    assert wallet_outcome.status is LiveIvaReadStatus.FAILED
    assert wallet_outcome.status is not LiveIvaReadStatus.SUCCEEDED
    assert wallet_outcome.failure_mode is LiveIvaAcquisitionFailureMode.AEAT_403
    assert wallet_outcome.outcome_mode is LiveIvaAcquisitionFailureMode.AEAT_403
    assert wallet_outcome.outcome_mode is not LiveIvaAcquisitionFailureMode.AUTHENTICATED
    assert wallet_outcome.captured_count is None
    assert wallet_outcome.failure_type == "SedeNavigationError"
    assert "AEAT wallet auth gate" not in report.model_dump_json()


def test_combined_acquisition_reports_missing_surface_as_typed_failure(tmp_path: Path) -> None:
    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2024,
        year_to=2024,
        target_year=2026,
        target_period="1T",
    )

    assert report.filed_history_succeeded is False
    assert report.wallet_succeeded is False
    assert tuple(outcome.status for outcome in report.outcomes) == (
        LiveIvaReadStatus.FAILED,
        LiveIvaReadStatus.FAILED,
    )
    assert tuple(outcome.failure_type for outcome in report.outcomes) == (
        "MissingSurfaceReport",
        "MissingSurfaceReport",
    )


def test_live_surface_timeout_is_typed_and_classified() -> None:
    async def slow_read() -> str:
        await asyncio.sleep(0.05)
        return "unreachable"

    async def run() -> None:
        with pytest.raises(LiveIvaSurfaceTimeoutError) as raised:
            await _await_live_iva_surface(
                slow_read(),
                surface=LiveIvaReadSurface.FILED_HISTORY,
                timeout_ms=1,
            )

        assert raised.value.surface == LiveIvaReadSurface.FILED_HISTORY.value
        assert raised.value.timeout_ms == 1
        assert (
            classify_live_iva_acquisition_failure(raised.value)
            is LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
        )

    asyncio.run(run())


def test_surface_timeout_does_not_collapse_to_success(tmp_path: Path) -> None:
    timeout = LiveIvaSurfaceTimeoutError(
        "filed-history read did not finish",
        surface=LiveIvaReadSurface.FILED_HISTORY.value,
        timeout_ms=1,
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2024,
        year_to=2024,
        target_year=2026,
        target_period="1T",
        filed_history_error=timeout,
    )

    filed_outcome, wallet_outcome = report.outcomes
    assert filed_outcome.status is LiveIvaReadStatus.FAILED
    assert filed_outcome.outcome_mode is LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    assert filed_outcome.failure_type == "LiveIvaSurfaceTimeoutError"
    assert filed_outcome.captured_count is None
    assert wallet_outcome.status is LiveIvaReadStatus.FAILED


def test_live_surface_timeout_suppresses_playwright_target_closed_loop_noise() -> None:
    async def run() -> list[dict[str, object]]:
        loop = asyncio.get_running_loop()
        delegated: list[dict[str, object]] = []

        def previous_handler(_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
            delegated.append(context)

        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(previous_handler)
        try:
            async with _suppress_live_iva_playwright_cancellation_noise():
                loop.call_exception_handler(
                    {
                        "exception": TargetClosedError(
                            "Target page, context or browser has been closed\nCall log:\n  - navigating"
                        )
                    }
                )
                loop.call_exception_handler({"exception": RuntimeError("unrelated live exception")})
        finally:
            loop.set_exception_handler(original_handler)
        return delegated

    delegated = asyncio.run(run())

    assert len(delegated) == 1
    assert isinstance(delegated[0]["exception"], RuntimeError)


def test_combined_acquisition_manifest_persists_redacted_surface_outcomes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="session") as profile:
        filed_history = IvaCompensationHistoryCaptureReport(
            output_root=str(tmp_path / "filed-history"),
            year_from=2022,
            year_to=2024,
            captured_count=12,
            observation_paths=("observations/303-2022-1T.json",),
            artefact_refs=("secure-object:artefact",),
            casilla_count=948,
            calculation_observation_count=12,
            calculation_observation_keys=("303:2022:1T",),
            reloaded_history_count=12,
            reloaded_rows=(),
        )
        wallet_error = SedeNavigationError(
            "AEAT wallet auth gate",
            failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
            context={"captured_at": _CAPTURED_AT.isoformat()},
        )
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "remote-state",
            year_from=2022,
            year_to=2024,
            target_year=2026,
            target_period="2T",
            filed_history=filed_history,
            wallet_error=wallet_error,
        )

        manifest = persist_iva_remote_state_acquisition_report(report, captured_at=_CAPTURED_AT)
        reloaded = load_iva_remote_state_acquisition_manifest(manifest.acquisition_id)
        listed = list_iva_remote_state_acquisition_manifests()
        remote_state = load_iva_remote_state(as_of_year=2026)
        manifest_json = manifest.model_dump_json()

        assert reloaded == manifest
        assert listed == (manifest,)
        assert remote_state.acquisition_manifest_count == 1
        acquisition_row = remote_state.acquisition_manifests[0]
        assert acquisition_row.acquisition_ref.startswith("sha256:")
        assert acquisition_row.target_year == manifest.target_year
        assert acquisition_row.target_period == manifest.target_period
        assert acquisition_row.auth_status == "failed"
        assert acquisition_row.auth_outcome_mode == "unknown"
        assert acquisition_row.auth_failure_mode == "unknown"
        assert acquisition_row.auth_failure_type == "MissingAuthResult"
        assert acquisition_row.auth_diagnostic_ref is None
        assert acquisition_row.filed_history_succeeded is True
        assert acquisition_row.wallet_succeeded is False
        assert any(
            "outcome=aeat_403" in surface and "failure_mode=aeat_403" in surface
            for surface in acquisition_row.surfaces
        )
        assert manifest.acquisition_id not in remote_state.model_dump_json()
        assert manifest.acquisition_id.startswith("live-iva-acquisition:2026:2T:20260527T120000000000Z:")
        assert len(manifest.acquisition_id.rsplit(":", 1)[-1]) == 64
        assert manifest.filed_history_succeeded is True
        assert manifest.wallet_succeeded is False
        filed_surface, wallet_surface = manifest.surfaces
        assert filed_surface.surface is LiveIvaReadSurface.FILED_HISTORY
        assert filed_surface.reloaded_history_count == filed_history.reloaded_history_count
        assert wallet_surface.surface is LiveIvaReadSurface.WALLET_CARTERA
        assert wallet_surface.failure_mode is LiveIvaAcquisitionFailureMode.AEAT_403
        assert wallet_surface.failure_type == "SedeNavigationError"
        assert "AEAT wallet auth gate" not in manifest_json
        assert "remote-state" not in manifest_json

        db_path = profile.paths.db_dir / "aeat.db"
        assert _secure_object_namespace_count(db_path, LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE.namespace) == 1
        database_bytes = db_path.read_bytes()
        assert b"AEAT wallet auth gate" not in database_bytes
        assert b"remote-state" not in database_bytes


def test_acquisition_manifest_persists_redacted_auth_diagnostic_ref(tmp_path: Path) -> None:
    diagnostic_id = "clave-diagnostic-private-object-key"
    auth_error = ClaveMovilApprovalTimeoutError(
        "operator reported no prompt",
        failure_mode="auth_completion_timeout",
        context={
            "phone_state": "app_did_not_prompt",
            "auth_mode": "non_qr",
            "diagnostic_id": diagnostic_id,
        },
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="session"):
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "remote-state",
            year_from=2024,
            year_to=2024,
            target_year=2026,
            target_period="1T",
            auth_error=auth_error,
        )

        manifest = persist_iva_remote_state_acquisition_report(report, captured_at=_CAPTURED_AT)
        remote_state = load_iva_remote_state(as_of_year=2026)

    assert manifest.auth.diagnostic_ref is not None
    assert manifest.auth.diagnostic_ref.startswith("sha256:")
    assert remote_state.acquisition_manifests[0].auth_diagnostic_ref == manifest.auth.diagnostic_ref
    assert diagnostic_id not in manifest.model_dump_json()
    assert diagnostic_id not in remote_state.model_dump_json()


def test_legacy_acquisition_manifest_without_auth_outcome_still_loads() -> None:
    legacy = IvaRemoteStateAcquisitionReport(
        output_root="legacy-output",
        year_from=2024,
        year_to=2024,
        target_year=2026,
        target_period="1T",
        filed_history=None,
        wallet=None,
        outcomes=(),
    )

    manifest = IvaRemoteStateAcquisitionManifest.model_validate(
        {
            "acquisition_id": "legacy",
            "captured_at": _CAPTURED_AT,
            "year_from": 2024,
            "year_to": 2024,
            "target_year": 2026,
            "target_period": "1T",
            "filed_history_succeeded": False,
            "wallet_succeeded": False,
            "surfaces": [
                {"surface": "filed_history", "status": "failed", "failure_type": "MissingSurfaceReport"},
                {"surface": "wallet_cartera", "status": "failed", "failure_type": "MissingSurfaceReport"},
            ],
        }
    )

    assert legacy.auth.failure_type == "MissingAuthResult"
    assert manifest.auth.failure_type == "LegacyManifestAuthOutcome"
    assert tuple(surface.outcome_mode for surface in manifest.surfaces) == (
        LiveIvaAcquisitionFailureMode.UNKNOWN,
        LiveIvaAcquisitionFailureMode.UNKNOWN,
    )


def test_combined_acquisition_manifest_requires_ready_active_profile_runtime(tmp_path: Path) -> None:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "operator-private-output-root",
            year_from=2024,
            year_to=2024,
            target_year=2026,
            target_period="1T",
        )

        with pytest.raises(StorageValidationError):
            persist_iva_remote_state_acquisition_report(report, captured_at=_CAPTURED_AT)


def _secure_object_namespace_count(database_path: Path, namespace: str) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM secure_objects WHERE namespace = ?",
            (namespace,),
        ).fetchone()
    return int(row[0])
