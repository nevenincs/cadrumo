"""Recorded exact-profile acquisition of an IVA wallet observation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.operations import OperationEffect
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .iva_remote_state import capture_iva_compensation_wallet
from .iva_remote_state_ports import IvaRemoteStatePort
from .live_operation_execution import (
    own_provider_browser,
    publish_live_capture_report,
    require_exact_profile_worker,
    track_capture_session,
)
from .live_operation_registration import build_live_operation_definition
from .remote_state_models import IvaWalletCaptureReport

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


class IvaWalletCaptureCompositionFactory(Protocol):
    """Compose the wallet capture bundle under its held authority operation."""

    def __call__(self, *, operation: PinnedAuthorityOperation) -> IvaWalletCaptureComposition:
        """Return the exact worker-local wallet composition."""
        ...


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
        require_exact_profile_worker(
            payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        period = Period.from_year_and_code(payload.target_year, payload.target_period)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        resources = await own_provider_browser(context, self._browser_resources_factory, acquire_phase=_PHASES[1])
        session_receipt = await track_capture_session(context, may_write=True)
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
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[2], effect=OperationEffect.UPDATED
        )


def build_iva_wallet_capture_definition(
    composition_factory: IvaWalletCaptureCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare recorded wallet acquisition with worker-owned browser cleanup."""

    def build() -> IvaWalletCaptureExecutor:
        return IvaWalletCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return build_live_operation_definition(
        definition_id=IVA_WALLET_CAPTURE_DEFINITION_ID,
        request_type=IvaWalletCaptureRequest,
        result_type=IvaWalletCaptureReport,
        executor_type=IvaWalletCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
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
    return resolve_ledger_commit_access(
        request, context, profile_id=request.payload.profile_id, periods=frozenset({period})
    )


def build_iva_wallet_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind request, public report and scoped profile access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=IvaWalletCapturePublicResultV1,
        result_projector=_project_result,
        access_resolver=resolve_iva_wallet_capture_access,
    )
