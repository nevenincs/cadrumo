"""CLI bridge for exact-profile combined IVA remote-state capture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

import typer

from ...application.live.iva_remote_state_capture_operation import (
    IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
    IvaRemoteStateCapturePublicResultV1,
    IvaRemoteStateCaptureRequest,
    LiveIvaAuthOutcomePublicV1,
    LiveIvaSurfaceOutcomePublicV1,
)
from ...application.live.remote_state_models import (
    IvaRemoteStateAcquisitionReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import reject_duplicate_json_members
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class IvaRemoteStateCaptureRead:
    """Keep the settled receipt with the reconstructed redacted report."""

    completion: RegisteredOperationCompletion[IvaRemoteStateCapturePublicResultV1]
    projection: IvaRemoteStateCapturePublicResultV1
    report: IvaRemoteStateAcquisitionReport


def _failure_context(value: str | None) -> dict[str, object] | None:
    if value is None:
        return None
    decoded = json.loads(value, object_pairs_hook=reject_duplicate_json_members)
    if not isinstance(decoded, dict):
        raise ValueError("IVA evidence failure context must be a JSON object")
    return cast(dict[str, object], decoded)


def _auth_report(auth: LiveIvaAuthOutcomePublicV1) -> LiveIvaAuthOutcome:
    return LiveIvaAuthOutcome(
        status=auth.status,
        outcome_mode=auth.outcome_mode,
        failure_mode=auth.failure_mode,
        failure_type=auth.failure_type,
        diagnostic_ref=auth.diagnostic_ref,
        provider_kind=auth.provider_kind,
        reused_persisted_session=auth.reused_persisted_session,
        fresh=auth.fresh,
    )


def _surface_report(outcome: LiveIvaSurfaceOutcomePublicV1) -> LiveIvaReadOutcome:
    return LiveIvaReadOutcome(
        surface=outcome.surface,
        status=outcome.status,
        outcome_mode=outcome.outcome_mode,
        failure_mode=outcome.failure_mode,
        failure_type=outcome.failure_type,
        failure_context=_failure_context(outcome.failure_context_json),
        captured_count=outcome.captured_count,
        calculation_observation_count=outcome.calculation_observation_count,
    )


def _report(
    projection: IvaRemoteStateCapturePublicResultV1,
    *,
    request: IvaRemoteStateCaptureRequest,
) -> IvaRemoteStateAcquisitionReport:
    if (
        projection.output_root != str(request.output_root)
        or projection.year_from != request.year_from
        or projection.year_to != request.year_to
        or projection.target_year != request.target_year
        or projection.target_period != request.target_period
    ):
        raise ValueError("IVA evidence result does not match its submitted scope")
    report = IvaRemoteStateAcquisitionReport(
        acquisition_manifest_id=projection.acquisition_manifest_id,
        output_root=projection.output_root,
        year_from=projection.year_from,
        year_to=projection.year_to,
        target_year=projection.target_year,
        target_period=Period.from_year_and_code(projection.target_year, projection.target_period),
        auth=_auth_report(projection.auth),
        filed_history=None,
        wallet=None,
        outcomes=tuple(_surface_report(outcome) for outcome in projection.outcomes),
    )
    if (
        report.filed_history_succeeded != projection.filed_history_succeeded
        or report.wallet_succeeded != projection.wallet_succeeded
    ):
        raise ValueError("IVA evidence outcome flags disagree with the reconstructed report")
    return report


def read_iva_remote_state_capture_for_cli(
    ctx: typer.Context,
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None,
) -> IvaRemoteStateCaptureRead:
    """Submit both read surfaces and accept only their exact-profile settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = IvaRemoteStateCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        year_from=year_from,
        year_to=year_to,
        target_year=target_year,
        target_period=target_period.registry_token,
        taxpayer_nif=taxpayer_nif,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=IvaRemoteStateCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, IvaRemoteStateCapturePublicResultV1):
            raise ValueError("IVA evidence projection has an invalid type")
        report = _report(projection, request=request)
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.UPDATED
        ):
            raise ValueError("IVA evidence result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return IvaRemoteStateCaptureRead(completion=completed, projection=projection, report=report)


__all__ = ["IvaRemoteStateCaptureRead", "read_iva_remote_state_capture_for_cli"]
