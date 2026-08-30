"""Combined IVA remote-state acquisition report tests."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright._impl._errors import Error as PlaywrightError
from playwright._impl._errors import TargetClosedError
from pydantic import ValidationError

from ....adapters.outbound.aeat.auth.clave_movil_support import ClaveMovilApprovalTimeoutError
from ....adapters.outbound.aeat.sede.errors import SedeFailureMode, SedeNavigationError
from ....adapters.persistence.storage import (
    LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE,
    SecureObjectRowIdentityError,
)
from ....adapters.persistence.storage.errors import StorageValidationError
from ....core import AuthProviderKind
from ....core.period import Period
from ....core.config import Settings
from ....core.identity import nif_check_letter
from ....tests.secure_sql import isolated_runtime_profile, isolated_sessionless_storage_root, read_db_at_rest_bytes
from ...auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
)
from ...auth.sessions import AuthenticatedAeatSessionResult
from ..errors import (
    LiveIvaAcquisitionFailureMode,
    LiveIvaSurfaceTimeoutError,
    classify_live_iva_acquisition_failure,
)
from ..iva_remote_state import (
    IvaRemoteStateAcquisitionManifestRepository,
    _aggregate_iva_compensation_history_reports,
    _await_live_iva_surface,
    _filed_history_surface_timeout_ms,
    _suppress_live_iva_playwright_cancellation_noise,
    build_iva_remote_state_acquisition_report,
    capture_iva_compensation_history,
    capture_iva_compensation_wallet,
    capture_iva_remote_state,
    list_iva_remote_state_acquisition_manifests,
    load_iva_remote_state,
    load_iva_remote_state_acquisition_manifest,
    persist_iva_remote_state_acquisition_report,
)
from ..remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaRemoteStateAcquisitionManifest,
    IvaRemoteStateAcquisitionReport,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
_TARGET_1T = Period.from_year_and_code(2026, "1T")
_TARGET_2T = Period.from_year_and_code(2026, "2T")
_BUCKET_ID = "62626262-6262-4262-8262-626262626262"


def _clave_movil_session(identity_nif: str = "12345678Z") -> AeatSession:
    """Minimal real session, opaque to these tests beyond its provider kind."""
    return AeatSession(
        authenticated_at=_CAPTURED_AT,
        idle_deadline=_CAPTURED_AT,
        storage_state_path=None,
        identity_nif=identity_nif,
        provider_detail=ClaveMovilSessionDetail(dni_nie=identity_nif),
    )


def _clave_movil_assertion(identity_nif: str = "12345678Z") -> AeatLoginAssertion:
    """Minimal real login assertion, opaque to these tests beyond its provider kind."""
    return AeatLoginAssertion(
        target_url="https://sede.agenciatributaria.gob.es/",
        is_valid=True,
        identity_nif=identity_nif,
        status_code=200,
        elapsed_ms=1,
        attempted_at=_CAPTURED_AT,
        assertion_detail=ClaveMovilLoginAssertionDetail(),
    )


def test_combined_acquisition_records_authenticated_success_outcome(tmp_path: Path) -> None:
    auth_result = AuthenticatedAeatSessionResult(
        provider_kind=AuthProviderKind.CLAVE_MOVIL,
        session=_clave_movil_session(),
        assertion=_clave_movil_assertion(),
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
        target_period=_TARGET_2T,
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


def test_combined_acquisition_marks_partial_filed_history_as_failed(tmp_path: Path) -> None:
    auth_result = AuthenticatedAeatSessionResult(
        provider_kind=AuthProviderKind.CLAVE_MOVIL,
        session=_clave_movil_session(),
        assertion=_clave_movil_assertion(),
        reused_persisted_session=True,
        fresh=False,
    )
    filed_history = IvaCompensationHistoryCaptureReport(
        output_root=str(tmp_path / "filed-history"),
        year_from=2022,
        year_to=2026,
        captured_count=4,
        observation_paths=("observations/303-2026-1T.json",),
        artefact_refs=("secure-object:artefact",),
        casilla_count=316,
        calculation_observation_count=4,
        calculation_observation_keys=("303:2026:1T",),
        reloaded_history_count=4,
        reloaded_rows=(),
        failed_declaration_count=1,
        failed_declarations=("modelo=303;ejercicio=2024;period=1T;failure_type=TimeoutError",),
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2022,
        year_to=2026,
        target_year=2026,
        target_period=_TARGET_1T,
        auth_result=auth_result,
        filed_history=filed_history,
    )

    filed_outcome = report.outcomes[0]
    assert report.filed_history_succeeded is False
    assert filed_outcome.status is LiveIvaReadStatus.FAILED
    assert filed_outcome.failure_type == "FiledHistoryPartialFailure"
    assert filed_outcome.failure_mode is LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    assert filed_outcome.captured_count == 4
    assert filed_outcome.calculation_observation_count == 4
    assert filed_outcome.failure_context == {
        "captured_count": 4,
        "failed_declaration_count": 1,
        "failed_declarations": ("modelo=303;ejercicio=2024;period=1T;failure_type=TimeoutError",),
    }


def test_year_chunked_filed_history_reports_aggregate_into_one_command_report(tmp_path: Path) -> None:
    report_2024 = IvaCompensationHistoryCaptureReport(
        output_root=str(tmp_path / "filed-history"),
        year_from=2024,
        year_to=2024,
        captured_count=4,
        observation_paths=("observations/303-2024-1T.json", "observations/303-2024-2T.json"),
        artefact_refs=("secure-object:2024-1T",),
        casilla_count=316,
        calculation_observation_count=4,
        calculation_observation_keys=("303:2024:1T", "303:2024:2T"),
        reloaded_history_count=4,
        reloaded_rows=(),
    )
    report_2023 = IvaCompensationHistoryCaptureReport(
        output_root=str(tmp_path / "filed-history"),
        year_from=2023,
        year_to=2023,
        captured_count=3,
        observation_paths=("observations/303-2023-1T.json",),
        artefact_refs=("secure-object:2023-1T", "secure-object:2023-2T"),
        casilla_count=237,
        calculation_observation_count=3,
        calculation_observation_keys=("303:2023:1T",),
        reloaded_history_count=7,
        reloaded_rows=(),
        failed_declaration_count=1,
        failed_declarations=("modelo=303;ejercicio=2023;period=4T;failure_type=TimeoutError",),
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        aggregate = _aggregate_iva_compensation_history_reports(
            [report_2024, report_2023],
            output_root=tmp_path / "filed-history",
            year_from=2023,
            year_to=2024,
        )

    assert aggregate.year_from == 2023
    assert aggregate.year_to == 2024
    assert aggregate.captured_count == 7
    assert aggregate.casilla_count == 553
    assert aggregate.calculation_observation_count == 7
    assert aggregate.observation_paths == (
        "observations/303-2024-1T.json",
        "observations/303-2024-2T.json",
        "observations/303-2023-1T.json",
    )
    assert aggregate.artefact_refs == (
        "secure-object:2024-1T",
        "secure-object:2023-1T",
        "secure-object:2023-2T",
    )
    assert aggregate.calculation_observation_keys == ("303:2024:1T", "303:2024:2T", "303:2023:1T")
    assert aggregate.failed_declaration_count == 1
    assert aggregate.failed_declarations == ("modelo=303;ejercicio=2023;period=4T;failure_type=TimeoutError",)


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
        target_period=_TARGET_1T,
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
        target_period=_TARGET_2T,
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
        target_period=_TARGET_1T,
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
            classify_live_iva_acquisition_failure(raised.value) is LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
        )

    asyncio.run(run())


def test_filed_history_surface_timeout_scales_with_requested_years() -> None:
    settings = Settings(cadrumo_live_iva_surface_timeout_ms=180_000)

    assert _filed_history_surface_timeout_ms(settings, year_from=2026, year_to=2026) == 180_000
    assert _filed_history_surface_timeout_ms(settings, year_from=2022, year_to=2026) == 900_000


def test_surface_timeout_does_not_collapse_to_success(tmp_path: Path) -> None:
    timeout = LiveIvaSurfaceTimeoutError(
        "filed-history read did not finish",
        surface=LiveIvaReadSurface.FILED_HISTORY.value,
        timeout_ms=1,
        progress_context={"stage": "walk_declarations_register", "modelo": "303", "ejercicio": 2026},
    )

    report = build_iva_remote_state_acquisition_report(
        output_root=tmp_path,
        year_from=2024,
        year_to=2024,
        target_year=2026,
        target_period=_TARGET_1T,
        filed_history_error=timeout,
    )

    filed_outcome, wallet_outcome = report.outcomes
    assert filed_outcome.status is LiveIvaReadStatus.FAILED
    assert filed_outcome.outcome_mode is LiveIvaAcquisitionFailureMode.LIVE_NAVIGATION_FAILED
    assert filed_outcome.failure_type == "LiveIvaSurfaceTimeoutError"
    assert filed_outcome.captured_count is None
    assert wallet_outcome.status is LiveIvaReadStatus.FAILED
    assert timeout.context is not None
    assert timeout.context["progress"] == {
        "stage": "walk_declarations_register",
        "modelo": "303",
        "ejercicio": 2026,
    }


def test_surface_timeout_context_preserves_wallet_progress() -> None:
    timeout = LiveIvaSurfaceTimeoutError(
        "wallet read did not finish",
        surface=LiveIvaReadSurface.WALLET_CARTERA.value,
        timeout_ms=30_000,
        progress_context={
            "stage": "fetch_iva_compensation_wallet",
            "target_year": 2026,
            "target_period": "1T",
        },
    )

    assert timeout.context is not None
    assert timeout.context["progress"] == {
        "stage": "fetch_iva_compensation_wallet",
        "target_year": 2026,
        "target_period": "1T",
    }


def test_live_surface_timeout_suppresses_playwright_target_closed_loop_noise() -> None:
    async def run() -> list[dict[str, object]]:
        loop = asyncio.get_running_loop()
        delegated: list[dict[str, object]] = []

        def previous_handler(_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
            delegated.append(context)

        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(previous_handler)
        try:
            async with _suppress_live_iva_playwright_cancellation_noise(drain_ms=0):
                loop.call_exception_handler(
                    {
                        "exception": TargetClosedError(
                            "Target page, context or browser has been closed\nCall log:\n  - navigating",
                        ),
                    },
                )
                loop.call_exception_handler(
                    {
                        "exception": PlaywrightError(
                            "net::ERR_ABORTED; maybe frame was detached?\nCall log:\n  - navigating",
                        ),
                    },
                )
                loop.call_exception_handler({"exception": RuntimeError("unrelated live exception")})
        finally:
            loop.set_exception_handler(original_handler)
        return delegated

    delegated = asyncio.run(run())

    assert len(delegated) == 1
    assert isinstance(delegated[0]["exception"], RuntimeError)


def test_live_surface_timeout_can_keep_cancellation_handler_until_loop_shutdown() -> None:
    async def run() -> list[dict[str, object]]:
        loop = asyncio.get_running_loop()
        delegated: list[dict[str, object]] = []

        def previous_handler(_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
            delegated.append(context)

        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(previous_handler)
        try:
            async with _suppress_live_iva_playwright_cancellation_noise(drain_ms=0, restore_on_exit=False):
                pass

            loop.call_exception_handler(
                {
                    "exception": PlaywrightError(
                        "net::ERR_ABORTED; maybe frame was detached?\nCall log:\n  - navigating",
                    ),
                },
            )
            loop.call_exception_handler({"exception": RuntimeError("unrelated live exception")})
        finally:
            loop.set_exception_handler(original_handler)
        return delegated

    delegated = asyncio.run(run())

    assert len(delegated) == 1
    assert isinstance(delegated[0]["exception"], RuntimeError)


def test_combined_acquisition_manifest_persists_redacted_surface_outcomes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
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
            target_period=_TARGET_2T,
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
            "outcome=aeat_403" in surface and "failure_mode=aeat_403" in surface for surface in acquisition_row.surfaces
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

        db_path = profile.paths.database_file
        assert _secure_object_namespace_count(db_path, LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE.namespace) == 1
        database_bytes = read_db_at_rest_bytes(db_path)
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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "remote-state",
            year_from=2024,
            year_to=2024,
            target_year=2026,
            target_period=_TARGET_1T,
            auth_error=auth_error,
        )

        manifest = persist_iva_remote_state_acquisition_report(report, captured_at=_CAPTURED_AT)
        remote_state = load_iva_remote_state(as_of_year=2026)

    assert manifest.auth.diagnostic_ref is not None
    assert manifest.auth.diagnostic_ref.startswith("sha256:")
    assert remote_state.acquisition_manifests[0].auth_diagnostic_ref == manifest.auth.diagnostic_ref
    assert diagnostic_id not in manifest.model_dump_json()
    assert diagnostic_id not in remote_state.model_dump_json()


def test_acquisition_manifest_refuses_an_encrypted_payload_rekeyed_under_another_id(tmp_path: Path) -> None:
    """A valid manifest roundtrips, but cannot answer a foreign acquisition id.

    The foreign row is written through the actual encrypted secure-object
    repository with the repository's real envelope. It is therefore authentic
    ciphertext whose only inconsistency is the object key, which proves the
    live IVA surface refuses a re-key rather than returning a manifest for a
    different acquisition request.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "remote-state",
            year_from=2024,
            year_to=2024,
            target_year=2026,
            target_period=_TARGET_1T,
        )
        repository = IvaRemoteStateAcquisitionManifestRepository(objects=profile.repository)
        manifest = persist_iva_remote_state_acquisition_report(
            report,
            captured_at=_CAPTURED_AT,
            repository=repository,
        )

        assert load_iva_remote_state_acquisition_manifest(manifest.acquisition_id, repository=repository) == manifest

        foreign_acquisition_id = f"{manifest.acquisition_id}:rekeyed"
        _, envelope = repository._identified_envelope(manifest)
        profile.repository.save(
            namespace=repository.namespace,
            object_key=foreign_acquisition_id,
            classification=repository.sensitivity,
            schema_version=repository.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(SecureObjectRowIdentityError) as refusal:
            load_iva_remote_state_acquisition_manifest(foreign_acquisition_id, repository=repository)

    assert refusal.value.expected_identifier == foreign_acquisition_id


def test_acquisition_manifest_redacts_sensitive_surface_failure_context(tmp_path: Path) -> None:
    sensitive_nif = f"12345678{nif_check_letter(12345678)}"
    sensitive_support = "support-number-private-canary"
    sensitive_object_key = "wallet:private-object-key-canary"
    sensitive_profile_id = "123e4567-e89b-12d3-a456-426614174000"
    sensitive_url = "https://example.test/private/path?token=private-query-canary"
    wallet_error = SedeNavigationError(
        "wallet read failed before parser",
        failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
        context={
            "dni_nie": sensitive_nif,
            "num_soporte": sensitive_support,
            "object_key": sensitive_object_key,
            "profile_id": sensitive_profile_id,
            "landing_url": sensitive_url,
            "phone_state": "app_did_not_prompt",
            "nested": {"identity_nif": sensitive_nif, "stage": "wallet_auth_gate"},
            "credentials": {"raw": sensitive_support},
            "attempts": (sensitive_nif, sensitive_support),
        },
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "remote-state",
            year_from=2024,
            year_to=2024,
            target_year=2026,
            target_period=_TARGET_1T,
            wallet_error=wallet_error,
        )
        manifest = persist_iva_remote_state_acquisition_report(report, captured_at=_CAPTURED_AT)
        remote_state = load_iva_remote_state(as_of_year=2026)

        rendered = f"{report.model_dump_json()} {manifest.model_dump_json()} {remote_state.model_dump_json()}"
        database_bytes = read_db_at_rest_bytes(profile.paths.database_file)

    for raw in (
        sensitive_nif,
        sensitive_support,
        sensitive_object_key,
        sensitive_profile_id,
        "private-query-canary",
        "/private/path",
    ):
        assert raw not in rendered
        assert raw.encode() not in database_bytes
    assert "phone_state" in rendered
    assert "app_did_not_prompt" in rendered
    assert "sha256:" in rendered
    assert "https://example.test" in rendered


def test_acquisition_payloads_require_explicit_auth_outcome() -> None:
    # Deliberately omits the required `auth` field to prove pydantic's own
    # validation refuses it; model_validate (not the constructor) is used so
    # the omission is a runtime ValidationError, not a static missing-argument
    # error.
    with pytest.raises(ValidationError) as report_exc:
        IvaRemoteStateAcquisitionReport.model_validate(
            {
                "output_root": "missing-auth-output",
                "year_from": 2024,
                "year_to": 2024,
                "target_year": 2026,
                "target_period": _TARGET_1T,
                "filed_history": None,
                "wallet": None,
                "outcomes": (),
            },
        )

    assert any(error["loc"] == ("auth",) and error["type"] == "missing" for error in report_exc.value.errors())

    with pytest.raises(ValidationError) as manifest_exc:
        IvaRemoteStateAcquisitionManifest.model_validate(
            {
                "acquisition_id": "missing-auth",
                "captured_at": _CAPTURED_AT,
                "year_from": 2024,
                "year_to": 2024,
                "target_year": 2026,
                "target_period": _TARGET_1T,
                "filed_history_succeeded": False,
                "wallet_succeeded": False,
                "surfaces": [
                    {"surface": "filed_history", "status": "failed", "failure_type": "MissingSurfaceReport"},
                    {"surface": "wallet_cartera", "status": "failed", "failure_type": "MissingSurfaceReport"},
                ],
            },
        )

    assert any(error["loc"] == ("auth",) and error["type"] == "missing" for error in manifest_exc.value.errors())


def test_combined_acquisition_manifest_requires_ready_active_profile_runtime(tmp_path: Path) -> None:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        report = build_iva_remote_state_acquisition_report(
            output_root=tmp_path / "operator-private-output-root",
            year_from=2024,
            year_to=2024,
            target_year=2026,
            target_period=_TARGET_1T,
        )

        with pytest.raises(StorageValidationError):
            persist_iva_remote_state_acquisition_report(report, captured_at=_CAPTURED_AT)


def test_remote_state_reload_refuses_without_active_profile(tmp_path: Path) -> None:
    with isolated_sessionless_storage_root(tmp_path=tmp_path), pytest.raises(StorageValidationError):
        load_iva_remote_state(as_of_year=2026)


def test_remote_state_capture_refuses_without_active_profile(tmp_path: Path) -> None:
    async def run() -> None:
        await capture_iva_remote_state(
            year_from=2026,
            year_to=2026,
            target_year=2026,
            target_period=_TARGET_2T,
        )

    with isolated_sessionless_storage_root(tmp_path=tmp_path), pytest.raises(StorageValidationError):
        asyncio.run(run())


def test_standalone_iva_wallet_capture_refuses_without_active_profile(tmp_path: Path) -> None:
    async def run() -> None:
        await capture_iva_compensation_wallet(target_year=2026, target_period=_TARGET_2T)

    with isolated_sessionless_storage_root(tmp_path=tmp_path), pytest.raises(StorageValidationError):
        asyncio.run(run())


def test_standalone_iva_history_capture_refuses_without_active_profile(tmp_path: Path) -> None:
    async def run() -> None:
        await capture_iva_compensation_history(year_from=2026, year_to=2026, output_root=tmp_path / "history")

    with isolated_sessionless_storage_root(tmp_path=tmp_path), pytest.raises(StorageValidationError):
        asyncio.run(run())


def _secure_object_namespace_count(database_path: Path, namespace: str) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM secure_objects WHERE namespace = ?",
            (namespace,),
        ).fetchone()
    return int(row[0])
