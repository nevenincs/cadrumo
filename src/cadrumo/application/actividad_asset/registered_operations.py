"""Canonical operation definitions and receipt projections for activity assets."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationResultProjector,
)
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .activity_asset_contracts import (
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_REFUSAL_CODES,
    ActivityAssetClaimRequest,
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
    ActivityAssetInspectRequest,
    ActivityAssetOperationPortsFactory,
    ActivityAssetRefusal,
)
from .activity_asset_executors import (
    ActivityAssetClaimExecutor,
    ActivityAssetCorrectExecutor,
    ActivityAssetCreateExecutor,
    ActivityAssetFilingHandoffExecutor,
    ActivityAssetForecastExecutor,
    ActivityAssetInspectExecutor,
)
from .activity_asset_projections import (
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetForecastProjection,
    ActivityAssetInspectProjection,
)
from .activity_asset_results import (
    ActivityAssetClaimResult,
    ActivityAssetCorrectResult,
    ActivityAssetCreateResult,
    ActivityAssetFilingHandoffResult,
    ActivityAssetForecastResult,
    ActivityAssetInspectResult,
    ActivityAssetOperationResult,
    ActivityAssetRefusalResult,
)
from .operation_dtos import (
    ActivityAssetFilingHandoffSnapshot,
    ActivityAssetHistoryClaimResultSnapshot,
    ActivityAssetHistorySnapshot,
    ScheduledAmortizationChargeSnapshot,
)


def _require_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    request_type: type[BaseModel],
    mutation: bool,
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id or not isinstance(request.payload, request_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = cast(Any, request.payload)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset(),
    )
    if not mutation:
        return resolved
    return with_commit_action(resolved)


def resolve_activity_asset_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind every asset operation to the exact complete profile history."""
    targets: dict[str, tuple[type[BaseModel], bool]] = {
        ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID: (ActivityAssetCreateRequest, True),
        ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID: (ActivityAssetInspectRequest, False),
        ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID: (ActivityAssetCorrectRequest, True),
        ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID: (ActivityAssetForecastRequest, False),
        ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID: (ActivityAssetClaimRequest, True),
        ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID: (ActivityAssetFilingHandoffRequest, False),
    }
    target = targets.get(request.definition_id)
    if target is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    request_type, mutation = target
    return _require_access(
        request,
        context,
        definition_id=request.definition_id,
        request_type=request_type,
        mutation=mutation,
    )


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type,
    ports_factory: ActivityAssetOperationPortsFactory,
    sensitive_input: bool,
    mutation: bool,
) -> OperationDefinition:
    effects = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    if mutation:
        effects = effects | {OperationEffect.UPDATED}
    request_storage = (
        OperationRequestStoragePolicy.SECURE_REFERENCE
        if sensitive_input
        else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    )
    sensitive = (
        OperationSensitiveInputPolicy.SECURE_REFERENCE if sensitive_input else OperationSensitiveInputPolicy.NONE
    )
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=lambda: executor_type(ports_factory),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=request_storage,
            sensitive_input=sensitive,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=effects,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=ACTIVITY_ASSET_REFUSAL_CODES,
    )


def _registration(
    definition: OperationDefinition,
    *,
    projection_type: type[BaseModel],
    result_projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=projection_type,
        result_projector=result_projector,
        access_resolver=resolve_activity_asset_access,
    )


def _receipt_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    refused = condition is OperationTerminalCondition.REFUSED
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not condition
        or receipt.effect is not effect
        or receipt.refusal_ref != refusal_code
        or (receipt.refusal_detail_ref is not None) != refused
        or (receipt.result_ref is not None) != (not refused)
    ):
        raise ValueError("activity-asset projection differs from its terminal receipt")


def _private_result(result: BaseModel, result_type: type[ActivityAssetOperationResult]) -> ActivityAssetOperationResult:
    if type(result) is not result_type:
        raise ValueError("invalid activity-asset operation result")
    return result_type.model_validate(result.model_dump(mode="python"), strict=True)


def _project_refusal(refusal: ActivityAssetRefusalResult | None) -> ActivityAssetRefusal | None:
    if refusal is None:
        return None
    return ActivityAssetRefusal(
        code=refusal.code,
        precondition_verdict=(
            PreconditionVerdictSnapshot.from_verdict(refusal.precondition_verdict)
            if refusal.precondition_verdict is not None
            else None
        ),
    )


def _verify_private_receipt(
    private: ActivityAssetOperationResult,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    success_effect: OperationEffect,
) -> None:
    refused = private.outcome == "refused"
    refusal_code = private.refusal.code if private.refusal is not None else None
    effect = OperationEffect.NONE if refused else success_effect
    if definition_id == ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID and not refused:
        claim_result = cast(ActivityAssetClaimResult, private).claim_result
        if claim_result is None:
            raise ValueError("successful activity-asset claim lacks its claim result")
        effect = OperationEffect.NONE if claim_result.reused_existing_claim else OperationEffect.UPDATED
    _receipt_matches(
        receipt,
        definition_id=definition_id,
        profile_id=private.profile_id,
        effect=effect,
        condition=OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED,
        refusal_code=refusal_code,
    )


def _project_create(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetCreateProjection:
    private = cast(ActivityAssetCreateResult, _private_result(result, ActivityAssetCreateResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.UPDATED,
    )
    return ActivityAssetCreateProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        history=ActivityAssetHistorySnapshot.from_domain(private.history) if private.history is not None else None,
    )


def _project_inspect(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetInspectProjection:
    private = cast(ActivityAssetInspectResult, _private_result(result, ActivityAssetInspectResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.NONE,
    )
    return ActivityAssetInspectProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        asset_id=private.asset_id,
        revisions=private.revisions,
    )


def _project_correct(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetCorrectProjection:
    private = cast(ActivityAssetCorrectResult, _private_result(result, ActivityAssetCorrectResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.UPDATED,
    )
    return ActivityAssetCorrectProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        history=ActivityAssetHistorySnapshot.from_domain(private.history) if private.history is not None else None,
    )


def _project_forecast(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetForecastProjection:
    private = cast(ActivityAssetForecastResult, _private_result(result, ActivityAssetForecastResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.NONE,
    )
    return ActivityAssetForecastProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        forecast=(
            ScheduledAmortizationChargeSnapshot.from_domain(private.forecast) if private.forecast is not None else None
        ),
    )


def _project_claim(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetClaimProjection:
    private = cast(ActivityAssetClaimResult, _private_result(result, ActivityAssetClaimResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.UPDATED,
    )
    return ActivityAssetClaimProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        claim_result=(
            ActivityAssetHistoryClaimResultSnapshot.from_domain(private.claim_result)
            if private.claim_result is not None
            else None
        ),
        claim_id=private.claim_id,
    )


def _project_filing_handoff(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ActivityAssetFilingHandoffProjection:
    private = cast(ActivityAssetFilingHandoffResult, _private_result(result, ActivityAssetFilingHandoffResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.NONE,
    )
    return ActivityAssetFilingHandoffProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        tax_year=private.tax_year,
        m130_period=private.m130_period,
        filing_handoff=(
            ActivityAssetFilingHandoffSnapshot.from_domain(private.filing_handoff)
            if private.filing_handoff is not None
            else None
        ),
    )


def build_activity_asset_create_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the guarded operation that creates one asset revision."""
    return _definition(
        definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetCreateRequest,
        result_type=ActivityAssetCreateResult,
        executor_type=ActivityAssetCreateExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=True,
    )


def build_activity_asset_create_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed create request and projection schemas."""
    return _registration(
        definition,
        projection_type=ActivityAssetCreateProjection,
        result_projector=_project_create,
    )


def build_activity_asset_inspect_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the read-only operation that returns one full revision chain."""
    return _definition(
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetInspectRequest,
        result_type=ActivityAssetInspectResult,
        executor_type=ActivityAssetInspectExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=False,
    )


def build_activity_asset_inspect_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed inspect request and projection schemas."""
    return _registration(
        definition,
        projection_type=ActivityAssetInspectProjection,
        result_projector=_project_inspect,
    )


def build_activity_asset_correct_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the guarded operation that appends one current correction."""
    return _definition(
        definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetCorrectRequest,
        result_type=ActivityAssetCorrectResult,
        executor_type=ActivityAssetCorrectExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=True,
    )


def build_activity_asset_correct_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed correction request and projection schemas."""
    return _registration(
        definition,
        projection_type=ActivityAssetCorrectProjection,
        result_projector=_project_correct,
    )


def build_activity_asset_forecast_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the non-consuming pinned-authority forecast operation."""
    return _definition(
        definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetForecastRequest,
        result_type=ActivityAssetForecastResult,
        executor_type=ActivityAssetForecastExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=False,
    )


def build_activity_asset_forecast_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed forecast request and projection schemas."""
    return _registration(
        definition,
        projection_type=ActivityAssetForecastProjection,
        result_projector=_project_forecast,
    )


def build_activity_asset_claim_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the guarded operation that records or replays a forecast claim."""
    return _definition(
        definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetClaimRequest,
        result_type=ActivityAssetClaimResult,
        executor_type=ActivityAssetClaimExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=True,
    )


def build_activity_asset_claim_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed claim request and projection schemas."""
    return _registration(
        definition,
        projection_type=ActivityAssetClaimProjection,
        result_projector=_project_claim,
    )


def build_activity_asset_filing_handoff_definition(
    ports_factory: ActivityAssetOperationPortsFactory,
) -> OperationDefinition:
    """Build the read-only M100/M130 activity-asset filing projection."""
    return _definition(
        definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetFilingHandoffRequest,
        result_type=ActivityAssetFilingHandoffResult,
        executor_type=ActivityAssetFilingHandoffExecutor,
        ports_factory=ports_factory,
        sensitive_input=False,
        mutation=False,
    )


def build_activity_asset_filing_handoff_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed filing handoff request and projection schemas."""
    return _registration(
        definition,
        projection_type=ActivityAssetFilingHandoffProjection,
        result_projector=_project_filing_handoff,
    )


__all__ = [
    "build_activity_asset_claim_definition",
    "build_activity_asset_claim_registration",
    "build_activity_asset_correct_definition",
    "build_activity_asset_correct_registration",
    "build_activity_asset_create_definition",
    "build_activity_asset_create_registration",
    "build_activity_asset_filing_handoff_definition",
    "build_activity_asset_filing_handoff_registration",
    "build_activity_asset_forecast_definition",
    "build_activity_asset_forecast_registration",
    "build_activity_asset_inspect_definition",
    "build_activity_asset_inspect_registration",
    "resolve_activity_asset_access",
]
