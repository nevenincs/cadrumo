"""Recorded exact-profile acquisition of combined IVA evidence surfaces."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .errors import LiveIvaAcquisitionFailureMode
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
)
from .iva_remote_state import capture_iva_remote_state
from .remote_state_models import (
    IvaRemoteStateAcquisitionReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from .session import LiveSessionWriteReceipt

IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID = "live.iva-wallet.evidence-capture"
_PHASES = ("iva-evidence.preflight", "iva-evidence.acquire", "iva-evidence.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class IvaRemoteStateCaptureRequest(BaseModel):
    """One exact profile, filed-history span and target wallet period."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    output_root: Path
    year_from: FilingYear
    year_to: FilingYear
    target_year: FilingYear
    target_period: str = Field(min_length=1, max_length=8)
    taxpayer_nif: str | None = None

    @model_validator(mode="after")
    def _valid_range(self) -> IvaRemoteStateCaptureRequest:
        if self.year_from > self.year_to:
            raise ValueError("IVA evidence year_from exceeds year_to")
        Period.from_year_and_code(self.target_year, self.target_period)
        return self


class LiveIvaAuthOutcomePublicV1(BaseModel):
    """Closed, redacted authentication outcome for authorized frontends."""

    model_config = _PUBLIC_CONFIG
    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode
    failure_mode: LiveIvaAcquisitionFailureMode | None
    failure_type: str | None
    diagnostic_ref: str | None
    provider_kind: str | None
    reused_persisted_session: bool | None
    fresh: bool | None


class LiveIvaSurfaceOutcomePublicV1(BaseModel):
    """Closed surface outcome with redacted context stored as canonical JSON."""

    model_config = _PUBLIC_CONFIG
    surface: LiveIvaReadSurface
    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode
    failure_mode: LiveIvaAcquisitionFailureMode | None
    failure_type: str | None
    failure_context_json: str | None
    captured_count: NonNegativeInt | None
    calculation_observation_count: NonNegativeInt | None


class IvaRemoteStateCapturePublicResultV1(BaseModel):
    """Complete CLI accounting without private taxpayer observation rows."""

    model_config = _PUBLIC_CONFIG
    acquisition_manifest_id: str
    output_root: str
    year_from: FilingYear
    year_to: FilingYear
    target_year: FilingYear
    target_period: str
    auth: LiveIvaAuthOutcomePublicV1
    filed_history_succeeded: bool
    wallet_succeeded: bool
    outcomes: tuple[LiveIvaSurfaceOutcomePublicV1, LiveIvaSurfaceOutcomePublicV1]

    @model_validator(mode="after")
    def _surface_flags_match(self) -> IvaRemoteStateCapturePublicResultV1:
        if (
            self.outcomes[0].surface is not LiveIvaReadSurface.FILED_HISTORY
            or self.outcomes[1].surface is not LiveIvaReadSurface.WALLET_CARTERA
            or self.filed_history_succeeded != (self.outcomes[0].status is LiveIvaReadStatus.SUCCEEDED)
            or self.wallet_succeeded != (self.outcomes[1].status is LiveIvaReadStatus.SUCCEEDED)
        ):
            raise ValueError("IVA evidence surface outcomes disagree with their success flags")
        return self


def _public_auth(auth: LiveIvaAuthOutcome) -> LiveIvaAuthOutcomePublicV1:
    return LiveIvaAuthOutcomePublicV1(
        status=auth.status,
        outcome_mode=auth.outcome_mode,
        failure_mode=auth.failure_mode,
        failure_type=auth.failure_type,
        diagnostic_ref=auth.diagnostic_ref,
        provider_kind=auth.provider_kind,
        reused_persisted_session=auth.reused_persisted_session,
        fresh=auth.fresh,
    )


def _public_outcome(outcome: LiveIvaReadOutcome) -> LiveIvaSurfaceOutcomePublicV1:
    return LiveIvaSurfaceOutcomePublicV1(
        surface=outcome.surface,
        status=outcome.status,
        outcome_mode=outcome.outcome_mode,
        failure_mode=outcome.failure_mode,
        failure_type=outcome.failure_type,
        failure_context_json=(
            json.dumps(outcome.failure_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            if outcome.failure_context is not None
            else None
        ),
        captured_count=outcome.captured_count,
        calculation_observation_count=outcome.calculation_observation_count,
    )


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Release redacted accounting and exclude private history/wallet rows."""
    del receipt
    report = IvaRemoteStateAcquisitionReport.model_validate(result, strict=True)
    if report.acquisition_manifest_id is None or len(report.outcomes) != 2:
        raise ValueError("IVA evidence result lacks its manifest or surface outcomes")
    return IvaRemoteStateCapturePublicResultV1(
        acquisition_manifest_id=report.acquisition_manifest_id,
        output_root=report.output_root,
        year_from=report.year_from,
        year_to=report.year_to,
        target_year=report.target_year,
        target_period=report.target_period.registry_token,
        auth=_public_auth(report.auth),
        filed_history_succeeded=report.filed_history_succeeded,
        wallet_succeeded=report.wallet_succeeded,
        outcomes=(_public_outcome(report.outcomes[0]), _public_outcome(report.outcomes[1])),
    )


class IvaRemoteStateCaptureExecutor:
    """Run both remote surfaces with fresh fences and process cleanup."""

    def __init__(
        self,
        composition_factory: FiledHistoryCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind immutable provider, persistence and browser capabilities."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self, request: OperationRequest[IvaRemoteStateCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Acquire both surfaces and publish one encrypted manifest receipt."""
        payload = request.payload
        profile_id = canonical_profile_bucket_id(payload.profile_id)
        if require_active_bucket_id() != profile_id or request.subject_ref != profile_operation_subject(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = Period.from_year_and_code(payload.target_year, payload.target_period)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(payload.output_root, operation=context.authority_operation)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])
        await context.events.effect(OperationEffect.UNKNOWN)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with resources.activate():
            report = await capture_iva_remote_state(
                ports=composition.iva_remote_state_port,
                year_from=payload.year_from,
                year_to=payload.year_to,
                target_year=payload.target_year,
                target_period=period,
                taxpayer_nif=payload.taxpayer_nif,
                output_root=payload.output_root,
                effect_guard=context.cancellation.irreversible_section,
                on_session_write=session_receipt,
                authority_operation=context.authority_operation,
            )
        if (
            report.output_root != str(payload.output_root)
            or report.year_from != payload.year_from
            or report.year_to != payload.year_to
            or report.target_year != payload.target_year
            or report.target_period != period
            or not report.acquisition_manifest_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_PHASES[2])
        await context.events.effect(OperationEffect.UPDATED)
        async with context.cancellation.irreversible_section():
            return await context.operands.put(report, written_at=now())


def build_iva_remote_state_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare recorded combined IVA acquisition with worker-owned browser cleanup."""

    def build() -> IvaRemoteStateCaptureExecutor:
        return IvaRemoteStateCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
        request_type=IvaRemoteStateCaptureRequest,
        result_type=IvaRemoteStateAcquisitionReport,
        executor_factory=OperationExecutorFactory(
            request_type=IvaRemoteStateCaptureRequest,
            executor_type=IvaRemoteStateCaptureExecutor,
            build=build,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_iva_remote_state_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile IVA read authority and fresh local COMMIT fences."""
    if request.definition_id != IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, IvaRemoteStateCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_iva_remote_state_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind closed combined-IVA schemas to whole-profile disclosure access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=IvaRemoteStateCaptureRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=IvaRemoteStateCapturePublicResultV1,
        ),
        result_projector=_project_result,
        access_resolver=resolve_iva_remote_state_capture_access,
    )
