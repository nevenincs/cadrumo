"""Recorded exact-profile acquisition of an encrypted notification snapshot."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data_ports import FiledEffectGuard
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .notification_ports import NotificationsPorts
from .notifications import (
    PersistedNotificationsSnapshot,
    capture_notifications_with_outcome,
)
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


def _require_exact_profile(profile_id: UUID, subject_ref: str) -> str:
    """Refuse work that is not bound to this exact profile worker."""
    canonical_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != canonical_id or subject_ref != profile_operation_subject(canonical_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return canonical_id


def _require_snapshot_bucket(snapshot: PersistedNotificationsSnapshot, bucket_id: str) -> None:
    """Fail closed if local custody returns a snapshot from another profile."""
    if str(snapshot.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _project_capture(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only stored summary scalars after validating their terminal receipt."""
    report = NotificationsCaptureOperationReport.model_validate(result, strict=True)
    snapshot = report.snapshot
    expected_effect = OperationEffect.UPDATED if report.newly_persisted else OperationEffect.NONE
    if (
        receipt.identity.definition_id != NOTIFICATIONS_CAPTURE_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(snapshot.bucket_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not expected_effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
    ):
        raise ValueError("notification capture result contradicts its terminal receipt")
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
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        if (
            request.definition_id != NOTIFICATIONS_CAPTURE_DEFINITION_ID
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        browser_resources = self._browser_resources_factory()
        context.cleanup.own(browser_resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])

        @asynccontextmanager
        async def fresh_persistence_guard() -> AsyncGenerator[None]:
            await context.events.phase(_PHASES[2])
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                yield

        effect_guard: FiledEffectGuard = fresh_persistence_guard
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
        await context.events.phase(_PHASES[3])
        await context.events.effect(session_receipt.combine(effect))
        async with context.cancellation.irreversible_section():
            return await context.operands.put(report, written_at=now())


def build_notifications_capture_definition(
    composition_factory: NotificationsCaptureCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare a recorded process-owning notifications capture operation."""

    def build() -> NotificationsCaptureExecutor:
        return NotificationsCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
        request_type=NotificationsCaptureRequest,
        result_type=NotificationsCaptureOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationsCaptureRequest,
            executor_type=NotificationsCaptureExecutor,
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
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
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


def resolve_notifications_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile access and a fresh local COMMIT fence."""
    if request.definition_id != NOTIFICATIONS_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, NotificationsCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_notifications_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind safe summary output and exact-profile commit access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=NotificationsCaptureRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationsCapturePublicResultV1,
        ),
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
