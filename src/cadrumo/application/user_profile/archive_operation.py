"""Human archive operations with exact worker authority and concrete effect receipts.

Remote provider admission is conservative: even a read may lazily create its
root or refresh credentials. UNKNOWN records admitted handoff, not delivery.
Neither portable recovery nor mirror output grants renewed automation authority.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
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
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import (
    HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_frontend_and_action,
    require_period_independent_replay_or_authority,
)
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
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
)
from .access_contracts import (
    AccessDenialCode,
)
from .access_errors import ProfileAccessRefusedError
from .archive_operation_ports import (
    ProfileArchiveOperationPorts,
    ProfileArchiveOperationPortsFactory,
    ProfileArchivePushReport,
)
from .bundle_export_contracts import ProfileBundleExportPurpose, ProfileBundleExportReconcileFailure
from .capsule_archive import ProfileCapsuleArchiveReceipt

PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID = "profile.archive.export"
PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID = "profile.archive.push"
PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID = "profile.archive.reconcile"
_FRONTENDS = frozenset({OperationFrontendProjection.CLI})


class ProfileArchiveExportRequest(BaseModel):
    """Protected local destination; never an archive password or plaintext payload."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    target: Path


class ProfileArchivePushRequest(BaseModel):
    """Existing mirror selection, retaining complete-manifest refusal for live limits."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    namespace_filter: str | None = None
    limit: Annotated[int, Field(ge=1)] | None = None
    dry_run: bool = False


class ProfileArchiveReconcileRequest(BaseModel):
    """Reconcile only journals owned by the admitted immutable profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ProfileArchiveExportReceiptSnapshot(ProfileCapsuleArchiveReceipt):
    """Complete existing sealed export receipt for authorized human disclosure."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    def to_receipt(self) -> ProfileCapsuleArchiveReceipt:
        """Restore the canonical human service receipt."""
        return ProfileCapsuleArchiveReceipt.model_validate(self.model_dump())


class ProfileArchiveExportProjection(BaseModel):
    """Bound human export receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    receipt: ProfileArchiveExportReceiptSnapshot

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.receipt.bucket_id != str(self.profile_id):
            raise ValueError("archive receipt differs from its profile")
        return self


class ProfileArchivePushProjection(BaseModel):
    """Complete human mirror outcome with exact selected profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    report: ProfileArchivePushReport

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.report.profile != str(self.profile_id):
            raise ValueError("mirror report differs from its profile")
        return self


class ArchiveReconciledExport(BaseModel):
    """Existing human journal outcome, excluding source capsule contents."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    operation_id: ContentDigest
    destination: str
    purpose: ProfileBundleExportPurpose


class ProfileArchiveReconcileProjection(BaseModel):
    """Complete selected-profile reconciliation rows and retained failures."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    reconciled: tuple[ArchiveReconciledExport, ...]
    failed: tuple[ProfileBundleExportReconcileFailure, ...]


class ProfileArchiveExportExecutionResult(BaseModel):
    """Encrypted human export result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ProfileArchiveExportProjection


class ProfileArchivePushExecutionResult(BaseModel):
    """Encrypted human mirror result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ProfileArchivePushProjection


class ProfileArchiveReconcileExecutionResult(BaseModel):
    """Encrypted human reconciliation result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ProfileArchiveReconcileProjection


type _ProfileArchiveRequest = ProfileArchiveExportRequest | ProfileArchivePushRequest | ProfileArchiveReconcileRequest
type _ProfileArchiveExecutionResult = (
    ProfileArchiveExportExecutionResult | ProfileArchivePushExecutionResult | ProfileArchiveReconcileExecutionResult
)


def _archive_request_payload[T: BaseModel](
    expected: str,
    request: OperationRequest[T],
    context: OperationExecutorContext,
) -> _ProfileArchiveRequest:
    payload = request.payload
    expected_type = {
        PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID: ProfileArchiveExportRequest,
        PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID: ProfileArchivePushRequest,
        PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID: ProfileArchiveReconcileRequest,
    }[expected]
    if request.definition_id != expected or type(payload) is not expected_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(
        payload, (ProfileArchiveExportRequest, ProfileArchivePushRequest, ProfileArchiveReconcileRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    require_operation_profile(request, context, payload.profile_id)
    return payload


def _archive_operation_ports(
    factory: ProfileArchiveOperationPortsFactory,
    payload: _ProfileArchiveRequest,
    operation: PinnedAuthorityOperation,
) -> ProfileArchiveOperationPorts:
    ports = factory(profile_id=payload.profile_id, operation=operation)
    if ports.profile_id != payload.profile_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _execute_archive_work[T: BaseModel](
    *,
    payload: _ProfileArchiveRequest,
    request: OperationRequest[T],
    context: OperationExecutorContext,
    ports: ProfileArchiveOperationPorts,
    tracker: LedgerCommitAttemptTracker,
    before_handoff: Callable[[], None],
) -> _ProfileArchiveExecutionResult:
    require_operation_profile(request, context, payload.profile_id)
    if isinstance(payload, ProfileArchiveExportRequest):
        receipt = ports.export(payload.target, write=tracker.call_writer)
        snapshot = ProfileArchiveExportReceiptSnapshot.model_validate(receipt.model_dump())
        return ProfileArchiveExportExecutionResult(
            projection=ProfileArchiveExportProjection(profile_id=payload.profile_id, receipt=snapshot)
        )
    if isinstance(payload, ProfileArchivePushRequest):
        report = ports.push(
            namespace_filter=payload.namespace_filter,
            limit=payload.limit,
            dry_run=payload.dry_run,
            before_handoff=before_handoff,
        )
        return ProfileArchivePushExecutionResult(
            projection=ProfileArchivePushProjection(profile_id=payload.profile_id, report=report)
        )
    outcome = ports.reconcile(write=tracker.call_writer)
    if any(row.profile_id != str(ports.profile_id) for row in outcome.reconciled):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ProfileArchiveReconcileExecutionResult(
        projection=ProfileArchiveReconcileProjection(
            profile_id=payload.profile_id,
            reconciled=tuple(
                ArchiveReconciledExport(operation_id=row.operation_id, destination=row.destination, purpose=row.purpose)
                for row in outcome.reconciled
            ),
            failed=outcome.failures,
        )
    )


def _archive_effect(
    *,
    handoff: bool,
    tracker: LedgerCommitAttemptTracker,
    failures: bool = False,
) -> OperationEffect:
    if handoff or tracker.has_uncertain_write:
        return OperationEffect.UNKNOWN
    if tracker.confirmed_write:
        return OperationEffect.PARTIAL if failures else OperationEffect.UPDATED
    return OperationEffect.NONE


async def _settle_archive_work(
    *,
    payload: _ProfileArchiveRequest,
    context: OperationExecutorContext,
    tracker: LedgerCommitAttemptTracker,
    expected: str,
    work: Callable[[], _ProfileArchiveExecutionResult],
    effect: Callable[[bool], OperationEffect],
) -> str:
    try:
        if isinstance(payload, ProfileArchivePushRequest):
            result = await asyncio.to_thread(work)
        else:
            result = await run_with_ledger_commit_fence(work, tracker=tracker, context=context, task_name=expected)
    except BaseException:
        await context.events.effect(effect(isinstance(payload, ProfileArchiveReconcileRequest)))
        raise
    if isinstance(result, ProfileArchiveExportExecutionResult) and not tracker.confirmed_write:
        raise ValueError("sealed archive receipt lacks an actual writer receipt")
    failures = isinstance(result, ProfileArchiveReconcileExecutionResult) and bool(result.projection.failed)
    await context.events.effect(effect(failures))
    return await context.operands.put(result, written_at=now())


async def _execute[T: BaseModel](
    factory: ProfileArchiveOperationPortsFactory,
    request: OperationRequest[T],
    context: OperationExecutorContext,
    expected: str,
) -> str:
    payload = _archive_request_payload(expected, request, context)
    await context.events.phase(expected)
    operation = context.authority_operation
    ports = _archive_operation_ports(factory, payload, operation)
    tracker = LedgerCommitAttemptTracker()
    handoff = False
    loop = asyncio.get_running_loop()

    async def authorize_handoff() -> None:
        nonlocal handoff
        async with context.cancellation.irreversible_section():
            require_operation_profile(request, context, payload.profile_id)
            handoff = True
            await context.events.effect(OperationEffect.UNKNOWN)

    def before_handoff() -> None:
        if not isinstance(payload, ProfileArchivePushRequest) or payload.dry_run:
            raise ValueError("provider handoff is unavailable for an archive preview")
        asyncio.run_coroutine_threadsafe(authorize_handoff(), loop).result()

    def work() -> _ProfileArchiveExecutionResult:
        return _execute_archive_work(
            payload=payload,
            request=request,
            context=context,
            ports=ports,
            tracker=tracker,
            before_handoff=before_handoff,
        )

    def effect(failures: bool = False) -> OperationEffect:
        return _archive_effect(handoff=handoff, tracker=tracker, failures=failures)

    async def settle() -> str:
        return await _settle_archive_work(
            payload=payload,
            context=context,
            tracker=tracker,
            expected=expected,
            work=work,
            effect=effect,
        )

    return await await_cancellation_complete(settle(), task_name=expected + ".settlement")


class ProfileArchiveExportExecutor:
    """Run canonical sealed recovery export through actual writer admission."""

    def __init__(self, factory: ProfileArchiveOperationPortsFactory) -> None:
        """Bind exact-profile canonical service composition."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ProfileArchiveExportRequest], context: OperationExecutorContext
    ) -> str:
        """Export the bound profile and retain its full protected receipt."""
        return await _execute(self._factory, request, context, PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID)


class ProfileArchivePushExecutor:
    """Run canonical ciphertext mirroring with short remote handoff admission."""

    def __init__(self, factory: ProfileArchiveOperationPortsFactory) -> None:
        """Bind the canonical policy-enforcing mirror port."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ProfileArchivePushRequest], context: OperationExecutorContext
    ) -> str:
        """Keep provider I/O outside COMMIT and join owned work before settling."""
        return await _execute(self._factory, request, context, PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID)


class ProfileArchiveReconcileExecutor:
    """Recover exact-profile journals through concrete local mutation admission."""

    def __init__(self, factory: ProfileArchiveOperationPortsFactory) -> None:
        """Bind scoped recovery and actual local writer admission."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ProfileArchiveReconcileRequest], context: OperationExecutorContext
    ) -> str:
        """Preserve canonical ownership and locking, then settle all actual writes."""
        return await _execute(self._factory, request, context, PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID)


def resolve_profile_archive_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize exact purpose/profile and complete reviewed destination disclosure."""
    expected = request.definition_id
    mutation = not isinstance(request.payload, ProfileArchivePushRequest) or not request.payload.dry_run
    if expected not in {
        PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
        PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
        PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
    }:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    expected_type = {
        PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID: ProfileArchiveExportRequest,
        PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID: ProfileArchivePushRequest,
        PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID: ProfileArchiveReconcileRequest,
    }[expected]
    if type(payload) is not expected_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(
        payload, (ProfileArchiveExportRequest, ProfileArchivePushRequest, ProfileArchiveReconcileRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    frontends = _FRONTENDS
    access_profile = (
        HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if mutation
        else HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
    )
    require_declared_frontend_and_action(context, frontends=frontends, actions=access_profile.actions)
    require_period_independent_replay_or_authority(context, profile_id=payload.profile_id, definition_id=expected)
    return bind_operation_access_profile(
        context, access_profile, profile_id=payload.profile_id, definition_id=expected, periods=frozenset()
    )


def _profile_archive_push_effects(
    projection: ProfileArchivePushProjection, receipt: OperationTerminalReceipt
) -> frozenset[OperationEffect]:
    report = projection.report
    if receipt.effect is OperationEffect.NONE and (
        report.pushed_by_namespace
        or report.manifest_pushed_by_namespace
        or report.failed_objects
        or report.degraded_manifests
        or report.cleanup_failed_objects
    ):
        raise ValueError("mirror provider outcomes require an admitted handoff receipt")
    return (
        frozenset({OperationEffect.NONE})
        if report.dry_run
        else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    )


def _profile_archive_reconcile_effects(
    projection: ProfileArchiveReconcileProjection, receipt: OperationTerminalReceipt
) -> frozenset[OperationEffect]:
    if (
        (receipt.effect is OperationEffect.NONE and projection.reconciled)
        or (receipt.effect is OperationEffect.UPDATED and projection.failed)
        or (receipt.effect is OperationEffect.PARTIAL and not projection.failed)
    ):
        raise ValueError("reconciliation outcomes disagree with their settled effect")
    return frozenset(OperationEffect)


def _require_archive_terminal_scope(
    *,
    receipt: OperationTerminalReceipt,
    expected: str,
    projection: ProfileArchiveExportProjection | ProfileArchivePushProjection | ProfileArchiveReconcileProjection,
    effects: frozenset[OperationEffect],
) -> None:
    if (
        receipt.identity.definition_id != expected
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in effects
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("archive result differs from its exact-purpose terminal receipt")


def project_profile_archive_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only matching protected results with honest settled effect metadata."""
    if type(result) is ProfileArchiveExportExecutionResult:
        expected = PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID
        projection: (
            ProfileArchiveExportProjection | ProfileArchivePushProjection | ProfileArchiveReconcileProjection
        ) = result.projection
        effects = frozenset({OperationEffect.UPDATED})
    elif type(result) is ProfileArchivePushExecutionResult:
        expected = PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID
        projection = result.projection
        effects = _profile_archive_push_effects(projection, receipt)
    elif type(result) is ProfileArchiveReconcileExecutionResult:
        expected = PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID
        projection = result.projection
        effects = _profile_archive_reconcile_effects(projection, receipt)
    else:
        raise ValueError("invalid archive execution result")
    _require_archive_terminal_scope(receipt=receipt, expected=expected, projection=projection, effects=effects)
    return type(projection).model_validate_json(projection.model_dump_json(), strict=True)


def _capabilities(effects: frozenset[OperationEffect]) -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=effects,
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def build_profile_archive_operation_definitions(
    factory: ProfileArchiveOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Register the complete existing human archive family without agent escalation."""
    return (
        build_single_phase_definition(
            definition_id=PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
            request_type=ProfileArchiveExportRequest,
            result_type=ProfileArchiveExportExecutionResult,
            executor_type=ProfileArchiveExportExecutor,
            build=lambda: ProfileArchiveExportExecutor(factory),
            capabilities=_capabilities(
                frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
            ),
            permitted_frontends=_FRONTENDS,
        ),
        build_single_phase_definition(
            definition_id=PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
            request_type=ProfileArchivePushRequest,
            result_type=ProfileArchivePushExecutionResult,
            executor_type=ProfileArchivePushExecutor,
            build=lambda: ProfileArchivePushExecutor(factory),
            capabilities=_capabilities(frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})),
            permitted_frontends=_FRONTENDS,
        ),
        build_single_phase_definition(
            definition_id=PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
            request_type=ProfileArchiveReconcileRequest,
            result_type=ProfileArchiveReconcileExecutionResult,
            executor_type=ProfileArchiveReconcileExecutor,
            build=lambda: ProfileArchiveReconcileExecutor(factory),
            capabilities=_capabilities(frozenset(OperationEffect)),
            permitted_frontends=_FRONTENDS,
        ),
    )


def build_profile_archive_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind closed schemas and purpose-specific exact-profile consent scopes."""
    models: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
        PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID: (ProfileArchiveExportRequest, ProfileArchiveExportProjection),
        PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID: (ProfileArchivePushRequest, ProfileArchivePushProjection),
        PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID: (
            ProfileArchiveReconcileRequest,
            ProfileArchiveReconcileProjection,
        ),
    }
    if len(definitions) != len(models) or {row.definition_id for row in definitions} != set(models):
        raise ValueError("incomplete archive operation family")
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=models[definition.definition_id][1],
            result_projector=project_profile_archive_operation_result,
            access_resolver=resolve_profile_archive_operation_access,
        )
        for definition in definitions
    )
