"""Recorded exact-profile acquisition of IVA compensation filed history."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, NonNegativeInt, model_validator

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
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
)
from .iva_remote_state import capture_iva_compensation_history
from .remote_state_models import IvaCompensationHistoryCaptureReport
from .session import LiveSessionWriteReceipt

IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID = "live.iva-wallet.history-capture"
_PHASES = ("iva-history.preflight", "iva-history.acquire", "iva-history.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class IvaWalletHistoryCaptureRequest(BaseModel):
    """An exact profile and inclusive filing-year range to capture."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    output_root: Path
    year_from: FilingYear
    year_to: FilingYear


class IvaWalletHistoryCapturePublicResultV1(BaseModel):
    """Complete CLI accounting without re-emitting stored taxpayer rows."""

    model_config = _PUBLIC_CONFIG
    output_root: str
    year_from: int
    year_to: int
    captured_count: NonNegativeInt
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    casilla_count: NonNegativeInt
    calculation_observation_count: NonNegativeInt
    calculation_observation_keys: tuple[str, ...]
    reloaded_history_count: NonNegativeInt
    failed_declaration_count: NonNegativeInt
    failed_declarations: tuple[str, ...]

    @model_validator(mode="after")
    def _counts_match_rows(self) -> IvaWalletHistoryCapturePublicResultV1:
        if (
            self.captured_count != len(self.observation_paths)
            or self.calculation_observation_count != len(self.calculation_observation_keys)
            or self.failed_declaration_count != len(self.failed_declarations)
        ):
            raise ValueError("IVA history capture counts do not match their detail rows")
        return self


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Project the stored report without private reloaded-history rows."""
    del receipt
    report = IvaCompensationHistoryCaptureReport.model_validate(result, strict=True)
    if report.reloaded_history_count != len(report.reloaded_rows):
        raise ValueError("IVA history reload count does not match its stored rows")
    return IvaWalletHistoryCapturePublicResultV1(
        output_root=report.output_root,
        year_from=report.year_from,
        year_to=report.year_to,
        captured_count=report.captured_count,
        observation_paths=report.observation_paths,
        artefact_refs=report.artefact_refs,
        casilla_count=report.casilla_count,
        calculation_observation_count=report.calculation_observation_count,
        calculation_observation_keys=report.calculation_observation_keys,
        reloaded_history_count=report.reloaded_history_count,
        failed_declaration_count=report.failed_declaration_count,
        failed_declarations=report.failed_declarations,
    )


class IvaWalletHistoryCaptureExecutor:
    """Own provider process cleanup and fence every local capture write."""

    def __init__(
        self,
        composition_factory: FiledHistoryCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind immutable outer capabilities for one worker invocation."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self, request: OperationRequest[IvaWalletHistoryCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Acquire remotely, guard local writes and publish encrypted accounting."""
        payload = request.payload
        profile_id = canonical_profile_bucket_id(payload.profile_id)
        if require_active_bucket_id() != profile_id or request.subject_ref != profile_operation_subject(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(payload.output_root, operation=context.authority_operation)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])
        await context.events.effect(OperationEffect.UNKNOWN)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with resources.activate():
            report = await capture_iva_compensation_history(
                ports=composition.iva_remote_state_port,
                year_from=payload.year_from,
                year_to=payload.year_to,
                output_root=payload.output_root,
                effect_guard=context.cancellation.irreversible_section,
                on_session_write=session_receipt,
                authority_operation=context.authority_operation,
            )
        if (
            report.output_root != str(payload.output_root)
            or report.year_from != payload.year_from
            or report.year_to != payload.year_to
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        effect = (
            OperationEffect.UPDATED
            if report.captured_count or report.calculation_observation_count
            else OperationEffect.NONE
        )
        await context.events.phase(_PHASES[2])
        await context.events.effect(session_receipt.combine(effect))
        async with context.cancellation.irreversible_section():
            return await context.operands.put(report, written_at=now())


def build_iva_wallet_history_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare one recorded IVA history acquisition with process cleanup."""

    def build() -> IvaWalletHistoryCaptureExecutor:
        return IvaWalletHistoryCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
        request_type=IvaWalletHistoryCaptureRequest,
        result_type=IvaCompensationHistoryCaptureReport,
        executor_factory=OperationExecutorFactory(
            request_type=IvaWalletHistoryCaptureRequest,
            executor_type=IvaWalletHistoryCaptureExecutor,
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


def resolve_iva_wallet_history_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile history access and a fresh COMMIT fence."""
    if request.definition_id != IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, IvaWalletHistoryCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_iva_wallet_history_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind public schemas to exact whole-profile acquisition authority."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=IvaWalletHistoryCaptureRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=IvaWalletHistoryCapturePublicResultV1,
        ),
        result_projector=_project_result,
        access_resolver=resolve_iva_wallet_history_capture_access,
    )
