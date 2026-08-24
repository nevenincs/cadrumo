"""Recorded supervision for the canonical filed-history pull composition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    require_active_bucket_id,
)
from ...core.time import now
from ...domain.deadlines import TaxpayerProfile
from ..operations import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations._executor import OperationEventEmitter, OperationExecutorContext
from ..storage.sync_runs import SyncRunRecordRepositoryProtocol
from ._filed_data_capture import (
    FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    FILED_HISTORY_DECLARATION_REFUSAL_CODE,
    FILED_HISTORY_DISCOVERY_REFUSAL_CODE,
    FILED_HISTORY_IVA_WALLET_REFUSAL_CODE,
    FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    FILED_HISTORY_PAIR_PROGRESS_UNIT,
    FILED_HISTORY_PAIR_REFUSAL_CODE,
    FILED_HISTORY_PHASE_DECLARATION_CAPTURE,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_FINALIZATION,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_PAIR_WALK,
    FILED_HISTORY_PHASE_PERSISTENCE,
    FILED_HISTORY_PHASE_PROVENANCE,
    FILED_HISTORY_PHASE_REGISTER_ACCESS,
    FILED_HISTORY_STAGE_REFUSAL_CODE,
    FiledHistoryOnboardingRun,
    pull_filed_history,
)

FILED_HISTORY_OPERATION_DEFINITION_ID = "live.filed-history.pull"
FILED_HISTORY_PHASE_PREFLIGHT = "filed-history.preflight"
FILED_HISTORY_PHASE_EXECUTION = "filed-history.execution"
FILED_HISTORY_PHASE_RESULT = "filed-history.result"
FILED_HISTORY_PHASE_CLEANUP = "filed-history.cleanup"
FILED_HISTORY_PHASE_SETTLEMENT = "filed-history.settlement"
_FILED_HISTORY_PHASES = (
    FILED_HISTORY_PHASE_PREFLIGHT,
    FILED_HISTORY_PHASE_EXECUTION,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_REGISTER_ACCESS,
    FILED_HISTORY_PHASE_PAIR_WALK,
    FILED_HISTORY_PHASE_DECLARATION_CAPTURE,
    FILED_HISTORY_PHASE_PERSISTENCE,
    FILED_HISTORY_PHASE_FINALIZATION,
    FILED_HISTORY_PHASE_PROVENANCE,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_RESULT,
    FILED_HISTORY_PHASE_CLEANUP,
    FILED_HISTORY_PHASE_SETTLEMENT,
)


class FiledHistoryOperationRequest(BaseModel):
    """Immutable scope submitted to one recorded filed-history pull."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    output_root: Path
    today: date | None = None
    limit: int | None = Field(default=None, ge=1)
    dry_run: bool = False


type FiledHistoryPull = Callable[
    [
        FiledHistoryOperationRequest,
        TaxpayerProfile | None,
        SyncRunRecordRepositoryProtocol,
        OperationEventEmitter,
    ],
    Awaitable[FiledHistoryOnboardingRun],
]
type FiledHistoryProfileResolver = Callable[[], TaxpayerProfile | None]
type FiledHistorySyncRunRepositoryFactory = Callable[[], SyncRunRecordRepositoryProtocol]


def _resolve_active_filed_history_profile() -> TaxpayerProfile | None:
    """Load the selected profile through its canonical internal projection."""
    from ..wizard import WizardStatusError, load_active_taxpayer_profile
    from ..workflow import workflow_state_repository

    try:
        return load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        # Filed history still has a truthful AEAT register-options path when the
        # active profile has not declared sufficient taxpayer facts yet.
        return None


async def _pull_recorded_filed_history(
    payload: FiledHistoryOperationRequest,
    profile: TaxpayerProfile | None,
    repository: SyncRunRecordRepositoryProtocol,
    events: OperationEventEmitter,
) -> FiledHistoryOnboardingRun:
    """Delegate every domain stage and write to the existing composition."""
    return await pull_filed_history(
        output_root=payload.output_root,
        profile=profile,
        today=payload.today,
        limit=payload.limit,
        dry_run=payload.dry_run,
        sync_run_repository=repository,
        events=events,
    )


def _settled_effect(run: FiledHistoryOnboardingRun) -> OperationEffect:
    """Classify only effects the canonical result proves were committed."""
    if run.dry_run:
        return OperationEffect.NONE
    failures = bool(run.refused_pairs or run.stage_failures)
    committed = bool(
        run.sync_run_ref
        or run.captured_count
        or run.genuinely_empty_pairs
        or run.iva_wallet_status == "reconciled"
        or run.notificaciones_status == "captured"
    )
    if committed:
        return OperationEffect.PARTIAL if failures else OperationEffect.UPDATED
    return OperationEffect.NONE


def _result_reference(run: FiledHistoryOnboardingRun) -> str | None:
    """Return only the canonical persisted provenance identity."""
    return run.sync_run_ref


async def _settlement_reference(
    run: FiledHistoryOnboardingRun,
    context: OperationExecutorContext,
) -> str:
    """Retain child provenance or persist a typed result when no child exists."""
    child_reference = _result_reference(run)
    if child_reference is not None:
        return child_reference
    return await context.operands.put(run, written_at=now())


class FiledHistoryOperationExecutor:
    """Run the existing filed-history service under one recorded identity."""

    def __init__(
        self,
        *,
        sync_run_repository: SyncRunRecordRepositoryProtocol,
        pull: FiledHistoryPull = _pull_recorded_filed_history,
        profile_resolver: FiledHistoryProfileResolver = _resolve_active_filed_history_profile,
    ) -> None:
        self._sync_run_repository = sync_run_repository
        self._pull = pull
        self._profile_resolver = profile_resolver

    async def execute(
        self,
        request: OperationRequest[FiledHistoryOperationRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        if require_active_bucket_id() != request.subject_ref:
            raise ValueError("filed-history operation subject must identify the active profile")
        profile = self._profile_resolver()
        await context.events.phase(FILED_HISTORY_PHASE_PREFLIGHT)
        await context.events.phase(FILED_HISTORY_PHASE_EXECUTION)
        # The delegated service contains several atomic secure writes. Until it
        # returns its typed accounting, an unexpected interruption cannot prove
        # whether none or some of those writes committed.
        if not request.payload.dry_run:
            await context.events.effect(OperationEffect.UNKNOWN)
        run = await self._pull(request.payload, profile, self._sync_run_repository, context.events)
        await context.events.phase(FILED_HISTORY_PHASE_RESULT)
        await context.events.phase(FILED_HISTORY_PHASE_CLEANUP)
        await context.events.effect(_settled_effect(run))
        await context.events.phase(FILED_HISTORY_PHASE_SETTLEMENT)
        return await _settlement_reference(run, context)


def build_filed_history_operation_definition(
    *,
    sync_run_repository_factory: FiledHistorySyncRunRepositoryFactory,
    pull: FiledHistoryPull = _pull_recorded_filed_history,
    profile_resolver: FiledHistoryProfileResolver = _resolve_active_filed_history_profile,
) -> OperationDefinition:
    """Bind entrypoint-owned persistence to the canonical operation contract."""

    def build() -> FiledHistoryOperationExecutor:
        return FiledHistoryOperationExecutor(
            sync_run_repository=sync_run_repository_factory(),
            pull=pull,
            profile_resolver=profile_resolver,
        )

    return OperationDefinition(
        definition_id=FILED_HISTORY_OPERATION_DEFINITION_ID,
        request_type=FiledHistoryOperationRequest,
        result_type=FiledHistoryOnboardingRun,
        executor_factory=OperationExecutorFactory(
            request_type=FiledHistoryOperationRequest,
            executor_type=FiledHistoryOperationExecutor,
            build=build,
        ),
        phase_codes=_FILED_HISTORY_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {
                    OperationEffect.NONE,
                    OperationEffect.UPDATED,
                    OperationEffect.PARTIAL,
                    OperationEffect.UNKNOWN,
                }
            ),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_filed_history_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the filed-history definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=definition,
        request_schema_id="live.filed-history.pull.request",
    )


__all__ = [
    "FILED_HISTORY_DECLARATION_PROGRESS_UNIT",
    "FILED_HISTORY_DECLARATION_REFUSAL_CODE",
    "FILED_HISTORY_DISCOVERY_REFUSAL_CODE",
    "FILED_HISTORY_IVA_WALLET_REFUSAL_CODE",
    "FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE",
    "FILED_HISTORY_OPERATION_DEFINITION_ID",
    "FILED_HISTORY_PAIR_PROGRESS_UNIT",
    "FILED_HISTORY_PAIR_REFUSAL_CODE",
    "FILED_HISTORY_PHASE_CLEANUP",
    "FILED_HISTORY_PHASE_DECLARATION_CAPTURE",
    "FILED_HISTORY_PHASE_DISCOVERY",
    "FILED_HISTORY_PHASE_EXECUTION",
    "FILED_HISTORY_PHASE_FINALIZATION",
    "FILED_HISTORY_PHASE_IVA_WALLET",
    "FILED_HISTORY_PHASE_NOTIFICATIONS",
    "FILED_HISTORY_PHASE_PAIR_WALK",
    "FILED_HISTORY_PHASE_PERSISTENCE",
    "FILED_HISTORY_PHASE_PREFLIGHT",
    "FILED_HISTORY_PHASE_PROVENANCE",
    "FILED_HISTORY_PHASE_REGISTER_ACCESS",
    "FILED_HISTORY_PHASE_RESULT",
    "FILED_HISTORY_PHASE_SETTLEMENT",
    "FILED_HISTORY_STAGE_REFUSAL_CODE",
    "FiledHistoryOperationExecutor",
    "FiledHistoryOperationRequest",
    "FiledHistoryPull",
    "FiledHistorySyncRunRepositoryFactory",
    "build_filed_history_operation_definition",
    "build_filed_history_operation_registration",
]
