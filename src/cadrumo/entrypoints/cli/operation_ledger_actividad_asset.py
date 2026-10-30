"""CLI transport bridge for profile-bound activity-asset operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, NoReturn
from uuid import UUID

import typer
from pydantic import BaseModel

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.actividad_asset.activity_asset_contracts import (
    ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_DISPOSAL_CALCULATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_DISPOSE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID,
    ActivityAssetAcquisitionCandidatesRequest,
    ActivityAssetClaimRequest,
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetDescribeRequest,
    ActivityAssetDisposalCalculateRequest,
    ActivityAssetDisposeRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
    ActivityAssetFormOptionsRequest,
    ActivityAssetInspectRequest,
    ActivityAssetListRequest,
    ActivityAssetPlanRequest,
    ActivityAssetSupersedingClaim,
    ActivityAssetTimelineRequest,
)
from ...application.actividad_asset.activity_asset_projections import (
    ActivityAssetAcquisitionCandidatesProjection,
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
    ActivityAssetDescribeProjection,
    ActivityAssetDisposalCalculateProjection,
    ActivityAssetDisposeProjection,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetForecastProjection,
    ActivityAssetFormOptionsProjection,
    ActivityAssetInspectProjection,
    ActivityAssetListProjection,
    ActivityAssetPlanProjection,
    ActivityAssetTimelineProjection,
)
from ...application.actividad_asset.operation_dtos import (
    ActivityAssetCorrectionRevisionSnapshot,
    ActivityAssetDisposalSnapshot,
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from .common import active_bucket_id_or_refuse

type _ActivityAssetProjection = (
    ActivityAssetCreateProjection
    | ActivityAssetInspectProjection
    | ActivityAssetCorrectProjection
    | ActivityAssetForecastProjection
    | ActivityAssetClaimProjection
    | ActivityAssetFilingHandoffProjection
    | ActivityAssetDescribeProjection
    | ActivityAssetDisposeProjection
    | ActivityAssetDisposalCalculateProjection
    | ActivityAssetListProjection
    | ActivityAssetPlanProjection
    | ActivityAssetTimelineProjection
    | ActivityAssetFormOptionsProjection
    | ActivityAssetAcquisitionCandidatesProjection
)


def _client(ctx: typer.Context) -> FrontendClient:
    """Bind every request to the invocation's exact selected profile."""
    return require_profile_client(ctx, expected_profile_id=UUID(active_bucket_id_or_refuse()))


def _submit[ResultT: _ActivityAssetProjection](
    client: FrontendClient,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ResultT],
) -> RegisteredOperationCompletion[ResultT]:
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    if completed.projection.profile_id != client.profile_id:
        raise invalid_completion_error(completed)
    return completed


def _validate_terminal(
    completed: RegisteredOperationCompletion[Any],
    *,
    success_effect: OperationEffect,
) -> bool:
    """Correlate the registered refusal detail with its terminal receipt."""
    projection = completed.projection
    if not isinstance(
        projection,
        (
            ActivityAssetCreateProjection,
            ActivityAssetInspectProjection,
            ActivityAssetCorrectProjection,
            ActivityAssetForecastProjection,
            ActivityAssetClaimProjection,
            ActivityAssetFilingHandoffProjection,
            ActivityAssetDescribeProjection,
            ActivityAssetDisposeProjection,
            ActivityAssetDisposalCalculateProjection,
            ActivityAssetListProjection,
            ActivityAssetPlanProjection,
            ActivityAssetTimelineProjection,
            ActivityAssetFormOptionsProjection,
            ActivityAssetAcquisitionCandidatesProjection,
        ),
    ):
        raise invalid_completion_error(completed)
    refused = projection.outcome == "refused"
    refusal = projection.refusal
    expected_condition = OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED
    expected_effect = OperationEffect.NONE if refused else success_effect
    if (
        completed.terminal_condition is not expected_condition
        or completed.effect is not expected_effect
        or completed.refusal_code != (refusal.code if refusal is not None else None)
        or refused != (refusal is not None)
    ):
        raise invalid_completion_error(completed)
    return refused


def _raise_refusal(completed: RegisteredOperationCompletion[Any]) -> NoReturn:
    """Rebuild the existing registered domain refusal at the CLI boundary."""
    refusal = completed.projection.refusal
    if refusal is None:
        raise invalid_completion_error(completed)
    context: dict[str, object] = {
        "operation_id": str(completed.operation_id),
        "terminal_condition": completed.terminal_condition.value,
        "effect": completed.effect.value,
        "refusal_code": refusal.code,
    }
    raise refusal.to_domain_error(context=context)


def _finish[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
    *,
    success_effect: OperationEffect,
) -> ResultT:
    if _validate_terminal(completed, success_effect=success_effect):
        _raise_refusal(completed)
    return completed.projection


def create_activity_asset(
    ctx: typer.Context,
    *,
    revision: ActivityAssetRevision,
    descriptor: ActivityAssetDescriptorFacts,
) -> ActivityAssetCreateProjection:
    """Create one revision through the operation bound to this profile."""
    client = _client(ctx)
    request = ActivityAssetCreateRequest(
        profile_id=client.profile_id,
        revision=ActivityAssetRevisionSnapshot.from_domain(revision),
        descriptor=descriptor,
    )
    completed = _submit(
        client,
        request,
        definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetCreateProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.UPDATED)
    if result.history is None or not any(
        item.to_domain().revision_id == revision.revision_id for item in result.history.revisions
    ):
        raise invalid_completion_error(completed)
    return result


def inspect_activity_asset(ctx: typer.Context, *, asset_id: str) -> ActivityAssetInspectProjection:
    """Read one asset's complete immutable revision chain."""
    client = _client(ctx)
    request = ActivityAssetInspectRequest(profile_id=client.profile_id, asset_id=asset_id)
    completed = _submit(
        client,
        request,
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetInspectProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.NONE)
    if result.asset_id != asset_id:
        raise invalid_completion_error(completed)
    return result


def correct_activity_asset(
    ctx: typer.Context,
    *,
    revision: ActivityAssetRevision,
    superseding_claims: tuple[ActivityAssetSupersedingClaim, ...] = (),
) -> ActivityAssetCorrectProjection:
    """Append one correction under the repository's guarded commit."""
    client = _client(ctx)
    request = ActivityAssetCorrectRequest(
        profile_id=client.profile_id,
        revision=ActivityAssetCorrectionRevisionSnapshot.from_domain(revision),
        superseding_claims=superseding_claims,
    )
    completed = _submit(
        client,
        request,
        definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetCorrectProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.UPDATED)
    if result.history is None or not any(
        item.to_domain().revision_id == revision.revision_id for item in result.history.revisions
    ):
        raise invalid_completion_error(completed)
    return result


def forecast_activity_asset(
    ctx: typer.Context,
    *,
    asset_id: str,
    covered_from: date,
    covered_until: date,
    requested_free_amount: Decimal | None,
    supersedes_claim_id: str | None,
) -> ActivityAssetForecastProjection:
    """Request a non-consuming forecast from the pinned calculation authority."""
    client = _client(ctx)
    request = ActivityAssetForecastRequest(
        profile_id=client.profile_id,
        asset_id=asset_id,
        covered_from=covered_from,
        covered_until=covered_until,
        requested_free_amount=(
            PublicDecimal(decimal=str(requested_free_amount)) if requested_free_amount is not None else None
        ),
        supersedes_claim_id=supersedes_claim_id,
    )
    completed = _submit(
        client,
        request,
        definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetForecastProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.NONE)
    forecast = result.forecast
    # The charge covers the part of the requested interval the asset was in
    # service, so it lies inside the request rather than equal to it.
    if (
        forecast is None
        or forecast.asset_id != asset_id
        or forecast.covered_from < covered_from
        or forecast.covered_until > covered_until
        or forecast.covered_from > forecast.covered_until
    ):
        raise invalid_completion_error(completed)
    return result


def claim_activity_asset(
    ctx: typer.Context,
    *,
    forecast: ScheduledAmortizationCharge,
    supersedes_claim_id: str | None,
) -> ActivityAssetClaimProjection:
    """Record or replay one exact forecast as an immutable claim."""
    client = _client(ctx)
    request = ActivityAssetClaimRequest(
        profile_id=client.profile_id,
        forecast=ScheduledAmortizationChargeSnapshot.from_domain(forecast),
        supersedes_claim_id=supersedes_claim_id,
    )
    completed = _submit(
        client,
        request,
        definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetClaimProjection,
    )
    projection = completed.projection
    success_effect = OperationEffect.UPDATED
    if projection.claim_result is not None and projection.claim_result.reused_existing_claim:
        success_effect = OperationEffect.NONE
    result = _finish(completed, success_effect=success_effect)
    claim_result = result.claim_result
    if claim_result is None:
        raise invalid_completion_error(completed)
    history = claim_result.history.to_domain()
    revision = next(
        (item for item in history.revisions if item.revision_id == claim_result.claim.asset_revision_id),
        None,
    )
    if revision is None:
        raise invalid_completion_error(completed)
    expected_claim = AmortizationClaim.from_schedule(
        forecast,
        asset_kind=revision.asset_kind,
        creating_operation=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        supersedes_claim_id=supersedes_claim_id,
    )
    if claim_result.claim.to_domain() != expected_claim or result.claim_id != expected_claim.claim_id:
        raise invalid_completion_error(completed)
    return result


def filing_handoff_activity_asset(
    ctx: typer.Context,
    *,
    tax_year: int,
    m130_period: str,
) -> ActivityAssetFilingHandoffProjection:
    """Read non-consuming M100/M130 claim projections for one filing frame."""
    client = _client(ctx)
    request = ActivityAssetFilingHandoffRequest(
        profile_id=client.profile_id,
        tax_year=tax_year,
        m130_period=m130_period,
    )
    completed = _submit(
        client,
        request,
        definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetFilingHandoffProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.NONE)
    if (result.tax_year, result.m130_period) != (tax_year, m130_period) or result.filing_handoff is None:
        raise invalid_completion_error(completed)
    Period.from_year_and_code(tax_year, m130_period)
    return result


def describe_activity_asset(
    ctx: typer.Context,
    *,
    asset_id: str,
    descriptor: ActivityAssetDescriptorFacts,
) -> ActivityAssetDescribeProjection:
    """Append one element's descriptive facts."""
    client = _client(ctx)
    completed = _submit(
        client,
        ActivityAssetDescribeRequest(profile_id=client.profile_id, asset_id=asset_id, descriptor=descriptor),
        definition_id=ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetDescribeProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.UPDATED)
    if result.history is None:
        raise invalid_completion_error(completed)
    return result


def dispose_activity_asset(
    ctx: typer.Context,
    *,
    asset_id: str,
    disposal: ActivityAssetDisposalSnapshot,
) -> ActivityAssetDisposeProjection:
    """Record one element's baja under the repository's guarded commit."""
    client = _client(ctx)
    completed = _submit(
        client,
        ActivityAssetDisposeRequest(profile_id=client.profile_id, asset_id=asset_id, disposal=disposal),
        definition_id=ACTIVITY_ASSET_DISPOSE_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetDisposeProjection,
    )
    result = _finish(completed, success_effect=OperationEffect.UPDATED)
    if result.history is None:
        raise invalid_completion_error(completed)
    return result


def _read[ResultT: _ActivityAssetProjection](
    ctx: typer.Context,
    build: Callable[[UUID], BaseModel],
    *,
    definition_id: str,
    result_type: type[ResultT],
) -> ResultT:
    client = _client(ctx)
    completed = _submit(client, build(client.profile_id), definition_id=definition_id, result_type=result_type)
    return _finish(completed, success_effect=OperationEffect.NONE)


def list_activity_assets(ctx: typer.Context) -> ActivityAssetListProjection:
    """Summarise the register."""
    return _read(
        ctx,
        lambda profile_id: ActivityAssetListRequest(profile_id=profile_id),
        definition_id=ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetListProjection,
    )


def calculate_activity_asset_disposal(
    ctx: typer.Context,
    *,
    asset_id: str,
    disposal: ActivityAssetDisposalSnapshot | None,
) -> ActivityAssetDisposalCalculateProjection:
    """Work out a baja's figures: the stated one as a preview, or else the recorded one."""
    return _read(
        ctx,
        lambda profile_id: ActivityAssetDisposalCalculateRequest(
            profile_id=profile_id,
            asset_id=asset_id,
            disposal=disposal,
        ),
        definition_id=ACTIVITY_ASSET_DISPOSAL_CALCULATE_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetDisposalCalculateProjection,
    )


def plan_activity_asset(ctx: typer.Context, *, asset_id: str) -> ActivityAssetPlanProjection:
    """Read one element's amortization plan."""
    return _read(
        ctx,
        lambda profile_id: ActivityAssetPlanRequest(profile_id=profile_id, asset_id=asset_id),
        definition_id=ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetPlanProjection,
    )


def timeline_activity_asset(ctx: typer.Context, *, asset_id: str) -> ActivityAssetTimelineProjection:
    """Read one element's ordered history."""
    return _read(
        ctx,
        lambda profile_id: ActivityAssetTimelineRequest(profile_id=profile_id, asset_id=asset_id),
        definition_id=ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetTimelineProjection,
    )


def form_options_activity_asset(
    ctx: typer.Context,
    *,
    asset_kind: AssetKind,
    tax_year: int,
) -> ActivityAssetFormOptionsProjection:
    """Read what the registry admits for an asset kind and tax year."""
    return _read(
        ctx,
        lambda profile_id: ActivityAssetFormOptionsRequest(
            profile_id=profile_id,
            asset_kind=asset_kind,
            tax_year=tax_year,
        ),
        definition_id=ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetFormOptionsProjection,
    )


def acquisition_candidates_activity_asset(ctx: typer.Context) -> ActivityAssetAcquisitionCandidatesProjection:
    """List the ledger payments an element could name as its acquisition."""
    return _read(
        ctx,
        lambda profile_id: ActivityAssetAcquisitionCandidatesRequest(profile_id=profile_id),
        definition_id=ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID,
        result_type=ActivityAssetAcquisitionCandidatesProjection,
    )


__all__ = [
    "acquisition_candidates_activity_asset",
    "calculate_activity_asset_disposal",
    "claim_activity_asset",
    "correct_activity_asset",
    "create_activity_asset",
    "describe_activity_asset",
    "dispose_activity_asset",
    "filing_handoff_activity_asset",
    "forecast_activity_asset",
    "form_options_activity_asset",
    "inspect_activity_asset",
    "list_activity_assets",
    "plan_activity_asset",
    "timeline_activity_asset",
]
