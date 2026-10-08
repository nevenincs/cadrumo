"""Recorded exact-profile acquisition of an encrypted notification snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.operations import OperationEffect
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES, OperationOwnedResource
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .live_operation_execution import (
    fenced_persistence_guard,
    own_provider_browser,
    publish_live_capture_report,
    require_exact_profile_worker,
    require_live_executor_identity,
)
from .live_operation_registration import (
    build_live_operation_definition,
    require_live_capture_receipt,
    resolve_whole_profile_capture_access,
)
from .notification_ports import NotificationsPorts
from .notifications import PersistedNotificationsSnapshot, capture_notifications_with_outcome
from .session import LiveSessionWriteReceipt

NOTIFICATIONS_CAPTURE_DEFINITION_ID = "live.notifications.capture"
_PHASES = (
    "notifications-capture.preflight",
    "notifications-capture.acquire",
    "notifications-capture.persist",
    "notifications-capture.result",
)
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class NotificationsCaptureRequest(CredentialFreeOperationRequest):
    """Capture the remote notifications surface for one exact profile."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID


class NotificationsCaptureOperationReport(BaseModel):
    """Private, encrypted result retaining the capture and persistence outcome."""

    model_config = _PUBLIC_CONFIG
    snapshot: PersistedNotificationsSnapshot
    newly_persisted: bool


class NotificationsCapturePublicResultV1(BaseModel):
    """Closed summary for the existing notifications pull presentation."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    persisted_at: datetime
    row_count: NonNegativeInt
    source_url: str = Field(min_length=1)


class NotificationsCaptureComposition(Protocol):
    """The profile worker capabilities needed for authenticated notification capture."""

    @property
    def notifications_ports(self) -> NotificationsPorts:
        """Return the canonical notification query and encrypted snapshot ports."""
        ...

    @property
    def certificate_secret_backend_factory(self) -> CertificateSecretBackendFactory:
        """Return the profile-bound certificate secret backend factory."""
        ...

    @property
    def browser_session_factory(self) -> BrowserSessionFactoryPort:
        """Return the worker's authenticated browser session factory."""
        ...

    @property
    def operator_scope_ports(self) -> OperatorScopePorts:
        """Return the operator authentication scope ports."""
        ...


class NotificationsCaptureCompositionFactory(Protocol):
    """Compose notifications custody under its held authority operation."""

    def __call__(self, *, operation: PinnedAuthorityOperation) -> NotificationsCaptureComposition:
        """Return the exact worker-local notification composition."""
        ...


def _require_snapshot_bucket(snapshot: PersistedNotificationsSnapshot, bucket_id: str) -> None:
    """Fail closed if local custody returns a snapshot from another profile."""
    if str(snapshot.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


_RECEIPT_CONTRADICTION = "notification capture result contradicts its terminal receipt"


def _project_capture(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only stored summary scalars after validating their terminal receipt."""
    report = NotificationsCaptureOperationReport.model_validate(result, strict=True)
    snapshot = report.snapshot
    require_live_capture_receipt(
        receipt,
        definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
        bucket_id=str(snapshot.bucket_id),
        stored=report.newly_persisted,
        message=_RECEIPT_CONTRADICTION,
    )
    return NotificationsCapturePublicResultV1(
        bucket_id=snapshot.bucket_id,
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        persisted_at=snapshot.persisted_at,
        row_count=len(snapshot.rows),
        source_url=snapshot.source_url,
    )


class NotificationsCaptureExecutor:
    """Fetch notifications before a fresh guarded write and own browser cleanup."""

    def __init__(
        self,
        composition_factory: NotificationsCaptureCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind worker-local authentication, storage, and browser ownership."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self,
        request: OperationRequest[NotificationsCaptureRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Acquire and persist one exact-profile snapshot with honest effect state."""
        payload = request.payload
        bucket_id = require_exact_profile_worker(
            payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        require_live_executor_identity(request, context, definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID)

        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        browser_resources = await own_provider_browser(
            context, self._browser_resources_factory, acquire_phase=_PHASES[1]
        )
        effect_guard = fenced_persistence_guard(context, persist_phase=_PHASES[2])
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            browser_resources.activate(),
        ):
            outcome = await capture_notifications_with_outcome(
                bucket_id=bucket_id,
                ports=composition.notifications_ports,
                certificate_secret_backend_factory=composition.certificate_secret_backend_factory,
                browser_session_factory=composition.browser_session_factory,
                operator_scope_ports=composition.operator_scope_ports,
                effect_guard=effect_guard,
                on_session_write=session_receipt,
                authority_operation=context.authority_operation,
                operation="live-notifications-pull",
            )

        _require_snapshot_bucket(outcome.snapshot, bucket_id)
        effect = OperationEffect.UPDATED if outcome.newly_persisted else OperationEffect.NONE
        report = NotificationsCaptureOperationReport(
            snapshot=outcome.snapshot,
            newly_persisted=outcome.newly_persisted,
        )
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[3], effect=session_receipt.combine(effect)
        )


def build_notifications_capture_definition(
    composition_factory: NotificationsCaptureCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare a recorded process-owning notifications capture operation."""

    def build() -> NotificationsCaptureExecutor:
        return NotificationsCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return build_live_operation_definition(
        definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
        request_type=NotificationsCaptureRequest,
        result_type=NotificationsCaptureOperationReport,
        executor_type=NotificationsCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES,
    )


def resolve_notifications_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile access and a fresh local COMMIT fence."""
    return resolve_whole_profile_capture_access(
        request, context, definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID, payload_type=NotificationsCaptureRequest
    )


def build_notifications_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind safe summary output and exact-profile commit access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=NotificationsCapturePublicResultV1,
        result_projector=_project_capture,
        access_resolver=resolve_notifications_capture_access,
    )


__all__ = [
    "NOTIFICATIONS_CAPTURE_DEFINITION_ID",
    "NotificationsCaptureComposition",
    "NotificationsCaptureCompositionFactory",
    "NotificationsCapturePublicResultV1",
    "NotificationsCaptureRequest",
    "build_notifications_capture_definition",
    "build_notifications_capture_registration",
    "resolve_notifications_capture_access",
]
