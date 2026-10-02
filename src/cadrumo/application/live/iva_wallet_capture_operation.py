"""Recorded exact-profile acquisition of an IVA wallet observation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

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
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .iva_remote_state import capture_iva_compensation_wallet
from .iva_remote_state_ports import IvaRemoteStatePort
from .remote_state_models import IvaWalletCaptureReport
from .session import LiveSessionWriteReceipt

IVA_WALLET_CAPTURE_DEFINITION_ID = "live.iva-wallet.capture"
_PHASES = ("iva-wallet.preflight", "iva-wallet.acquire", "iva-wallet.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class IvaWalletCaptureRequest(BaseModel):
    """One profile, target period and optional taxpayer identity for a wallet read."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    target_year: FilingYear
    target_period: str = Field(min_length=1, max_length=8)
    taxpayer_nif: str | None = None


class IvaWalletCapturePublicResultV1(BaseModel):
    """Closed result for the existing CLI and authorized operation frontends."""

    model_config = _PUBLIC_CONFIG
    taxpayer_ref: str
    target_year: FilingYear
    target_period: str
    observation_path: str
    decision_key: str
    row_count: NonNegativeInt
    total_pending: str
    selected_authority: str
    selected_amount: str | None
    local_recurrence_amount: str | None
    divergence: str
    blocked: bool
    captured_at: datetime


class IvaWalletCaptureComposition(Protocol):
    """Only the composed dependencies consumed by wallet acquisition."""

    @property
    def output_root(self) -> Path:
        """Return the profile-local wallet storage root."""
        ...

    @property
    def iva_remote_state_port(self) -> IvaRemoteStatePort:
        """Return the composed provider and secure storage port."""
        ...


IvaWalletCaptureCompositionFactory = Callable[[], IvaWalletCaptureComposition]


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Convert the internal report to a closed frontend schema."""
    del receipt
    report = IvaWalletCaptureReport.model_validate(result, strict=True)
    return IvaWalletCapturePublicResultV1(
        taxpayer_ref=report.taxpayer_ref,
        target_year=report.target_year,
        target_period=report.target_period.registry_token,
        observation_path=report.observation_path,
        decision_key=report.decision_key,
        row_count=report.row_count,
        total_pending=report.total_pending,
        selected_authority=report.selected_authority,
        selected_amount=report.selected_amount,
        local_recurrence_amount=report.local_recurrence_amount,
        divergence=report.divergence,
        blocked=report.blocked,
        captured_at=report.captured_at,
    )


class IvaWalletCaptureExecutor:
    """Keep provider reads outside COMMIT and own wallet persistence under it."""

    def __init__(
        self,
        composition_factory: IvaWalletCaptureCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind immutable provider, storage and cleanup capabilities."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self, request: OperationRequest[IvaWalletCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Capture and persist one wallet report with exact-profile authority."""
        payload = request.payload
        profile_id = canonical_profile_bucket_id(payload.profile_id)
        if require_active_bucket_id() != profile_id or request.subject_ref != profile_operation_subject(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = Period.from_year_and_code(payload.target_year, payload.target_period)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory()
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])
        await context.events.effect(OperationEffect.UNKNOWN)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with resources.activate():
            report = await capture_iva_compensation_wallet(
                ports=composition.iva_remote_state_port,
                target_year=payload.target_year,
                target_period=period,
                taxpayer_nif=payload.taxpayer_nif,
                output_root=composition.output_root,
                effect_guard=context.cancellation.irreversible_section,
                on_session_write=session_receipt,
                authority_operation=context.authority_operation,
            )
        if report.target_year != payload.target_year or report.target_period != period:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_PHASES[2])
        await context.events.effect(OperationEffect.UPDATED)
        async with context.cancellation.irreversible_section():
            return await context.operands.put(report, written_at=now())


def build_iva_wallet_capture_definition(
    composition_factory: IvaWalletCaptureCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare recorded wallet acquisition with worker-owned browser cleanup."""

    def build() -> IvaWalletCaptureExecutor:
        return IvaWalletCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=IVA_WALLET_CAPTURE_DEFINITION_ID,
        request_type=IvaWalletCaptureRequest,
        result_type=IvaWalletCaptureReport,
        executor_factory=OperationExecutorFactory(
            request_type=IvaWalletCaptureRequest,
            executor_type=IvaWalletCaptureExecutor,
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


def resolve_iva_wallet_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require target-period read authority and a fresh local COMMIT fence."""
    if request.definition_id != IVA_WALLET_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, IvaWalletCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    period = Period.from_year_and_code(request.payload.target_year, request.payload.target_period)
    resolved = resolve_ledger_read_access(
        request, context, profile_id=request.payload.profile_id, periods=frozenset({period})
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_iva_wallet_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind request, public report and scoped profile access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=IvaWalletCaptureRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=IvaWalletCapturePublicResultV1
        ),
        result_projector=_project_result,
        access_resolver=resolve_iva_wallet_capture_access,
    )
