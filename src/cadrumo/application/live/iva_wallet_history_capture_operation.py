"""Recorded exact-profile acquisition of IVA compensation filed history."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, NonNegativeInt, model_validator

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.operations import OperationEffect
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
)
from .iva_remote_state import capture_iva_compensation_history
from .live_operation_execution import (
    own_provider_browser,
    publish_live_capture_report,
    require_exact_profile_worker,
    track_capture_session,
)
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .remote_state_models import IvaCompensationHistoryCaptureReport

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
        require_exact_profile_worker(
            payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(payload.output_root, operation=context.authority_operation)
        resources = await own_provider_browser(context, self._browser_resources_factory, acquire_phase=_PHASES[1])
        session_receipt = await track_capture_session(context, may_write=True)
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
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[2], effect=session_receipt.combine(effect)
        )


def build_iva_wallet_history_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare one recorded IVA history acquisition with process cleanup."""

    def build() -> IvaWalletHistoryCaptureExecutor:
        return IvaWalletHistoryCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return build_live_operation_definition(
        definition_id=IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
        request_type=IvaWalletHistoryCaptureRequest,
        result_type=IvaCompensationHistoryCaptureReport,
        executor_type=IvaWalletHistoryCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
    )


def resolve_iva_wallet_history_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile history access and a fresh COMMIT fence."""
    return resolve_whole_profile_capture_access(
        request,
        context,
        definition_id=IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
        payload_type=IvaWalletHistoryCaptureRequest,
    )


def build_iva_wallet_history_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind public schemas to exact whole-profile acquisition authority."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=IvaWalletHistoryCapturePublicResultV1,
        result_projector=_project_result,
        access_resolver=resolve_iva_wallet_history_capture_access,
    )
